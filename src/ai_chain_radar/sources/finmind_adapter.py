from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.settings import get_settings
from ai_chain_radar.sources.base import BaseSourceAdapter, SourceRequest, SyncResult


class FinMindAdapter(BaseSourceAdapter):
    source_name = "finmind"
    datasets = [
        "TaiwanStockPrice",
        "TaiwanStockMonthRevenue",
        "TaiwanStockFinancialStatements",
        "TaiwanStockInstitutionalInvestorsBuySell",
    ]

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def sync(self, request: SourceRequest) -> list[SyncResult]:
        settings = get_settings()
        targets = [request.dataset] if request.dataset else self.datasets
        results: list[SyncResult] = []

        if request.dry_run:
            for dataset in targets:
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="skipped",
                        rows_read=0,
                        rows_written=0,
                        error_message="dry-run enabled, skipped network fetch",
                    )
                )
            return results

        for dataset in targets:
            started_at = datetime.now(UTC).replace(tzinfo=None)
            try:
                rows = self._fetch_rows_real(
                    dataset=dataset,
                    request=request,
                    token=settings.finmind_token or None,
                )
                raw_path = self._save_raw_jsonl(
                    dataset, request.end or request.date or "latest", rows
                )
                written = self._normalize_and_write(dataset, rows)
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="ok" if written > 0 else "empty",
                        rows_read=len(rows),
                        rows_written=written,
                        raw_path=raw_path,
                        started_at=started_at,
                    )
                )
            except Exception as exc:
                # FinMind 文档允许不带 token 调用，但额度更低；此时失败按缺凭据处理。
                if not settings.finmind_token:
                    results.append(
                        self._new_result(
                            dataset=dataset,
                            request=request,
                            status="missing_credentials",
                            error_message=(
                                "FINMIND_TOKEN missing and public quota request failed. "
                                "Configure FINMIND_TOKEN in .env."
                            ),
                            started_at=started_at,
                        )
                    )
                    continue
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="failed",
                        error_message=str(exc),
                        started_at=started_at,
                    )
                )
        return results

    def _fetch_rows_real(
        self, dataset: str, request: SourceRequest, token: str | None
    ) -> list[dict[str, Any]]:
        query = {"dataset": dataset}
        if token:
            query["token"] = token
        if request.start:
            query["start_date"] = request.start
        if request.end:
            query["end_date"] = request.end
        if request.symbols:
            query["data_id"] = request.symbols[0]
        url = "https://api.finmindtrade.com/api/v4/data?" + urlencode(query)
        req = Request(url=url, method="GET")
        with urlopen(req, timeout=20) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        data = payload.get("data")
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def _mock_rows(self, dataset: str, request: SourceRequest) -> list[dict[str, Any]]:
        if dataset == "TaiwanStockMonthRevenue":
            return [
                {
                    "revenue_month": "2026-04",
                    "symbol": "2330",
                    "company_name": "TSMC",
                    "revenue": 236_000_000_000,
                },
                {
                    "revenue_month": "2026-05",
                    "symbol": "2330",
                    "company_name": "TSMC",
                    "revenue": 245_000_000_000,
                },
            ]
        if dataset == "TaiwanStockPrice":
            return [
                {
                    "trade_date": request.end or "2026-05-28",
                    "symbol": "2330",
                    "market": "TW",
                    "close": 835.0,
                },
            ]
        return [{"symbol": "2330", "value": 1}]

    def _normalize_and_write(self, dataset: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        if dataset == "TaiwanStockMonthRevenue":
            frame = pd.DataFrame(rows)
            if frame.empty:
                return 0
            empty_col = pd.Series([""] * len(frame))
            frame["symbol"] = (
                frame["stock_id"].astype(str)
                if "stock_id" in frame.columns
                else frame.get("symbol", empty_col).astype(str)
            )
            if "revenue_year" in frame.columns and "revenue_month" in frame.columns:
                frame["revenue_month"] = (
                    frame["revenue_year"].astype(str)
                    + "-"
                    + frame["revenue_month"].astype(str).str.zfill(2)
                )
            else:
                frame["revenue_month"] = frame.get("revenue_month", empty_col).astype(str)
            frame["company_name"] = frame.get("company_name", empty_col).astype(str)
            frame = frame[
                (frame["symbol"].astype(str).str.len() > 0)
                & (frame["revenue_month"].astype(str).str.len() > 0)
            ]
            if frame.empty:
                return 0
            frame = frame.sort_values(["symbol", "revenue_month"])
            frame["revenue_mom"] = frame.groupby("symbol")["revenue"].pct_change() * 100
            frame["revenue_yoy"] = None
            frame["cumulative_revenue"] = frame.groupby("symbol")["revenue"].cumsum()
            frame["cumulative_yoy"] = None
            frame["source"] = "finmind"
            frame["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)
            keep_cols = [
                "revenue_month",
                "symbol",
                "company_name",
                "revenue",
                "revenue_mom",
                "revenue_yoy",
                "cumulative_revenue",
                "cumulative_yoy",
                "source",
                "ingested_at",
            ]
            frame = frame[keep_cols]
            return self.repo.upsert_dataframe(
                "taiwan_monthly_revenue", frame, keys=["revenue_month", "symbol"]
            )

        if dataset == "TaiwanStockPrice":
            frame = pd.DataFrame(rows)
            if frame.empty:
                return 0
            empty_col = pd.Series([""] * len(frame))
            frame["trade_date"] = (
                frame["date"].astype(str)
                if "date" in frame.columns
                else frame.get("trade_date", empty_col).astype(str)
            )
            frame["symbol"] = (
                frame["stock_id"].astype(str)
                if "stock_id" in frame.columns
                else frame.get("symbol", empty_col).astype(str)
            )
            frame["market"] = "TW"
            frame["open"] = (
                frame["open"].apply(self._to_float)
                if "open" in frame.columns
                else frame.get("close", 0).apply(self._to_float)
            )
            frame["high"] = (
                frame["max"].apply(self._to_float)
                if "max" in frame.columns
                else frame.get("high", 0).apply(self._to_float)
            )
            frame["low"] = (
                frame["min"].apply(self._to_float)
                if "min" in frame.columns
                else frame.get("low", 0).apply(self._to_float)
            )
            frame["close"] = frame["close"].apply(self._to_float)
            frame["spread"] = (
                frame["spread"].apply(self._to_float) if "spread" in frame.columns else 0.0
            )
            frame["pre_close"] = frame["close"] - frame["spread"].fillna(0.0)
            frame["pct_chg"] = frame.apply(
                lambda row: (
                    (row["spread"] / row["pre_close"] * 100.0)
                    if row["pre_close"] not in (None, 0)
                    else 0.0
                ),
                axis=1,
            )
            frame["volume"] = (
                frame["Trading_Volume"].apply(self._to_float)
                if "Trading_Volume" in frame.columns
                else 0.0
            )
            frame["amount"] = (
                frame["Trading_money"].apply(self._to_float)
                if "Trading_money" in frame.columns
                else 0.0
            )
            frame["relative_strength_5d"] = 0.0
            frame["relative_strength_20d"] = 0.0
            frame["source"] = "finmind"
            frame["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)
            keep_cols = [
                "trade_date",
                "symbol",
                "market",
                "open",
                "high",
                "low",
                "close",
                "pre_close",
                "pct_chg",
                "volume",
                "amount",
                "relative_strength_5d",
                "relative_strength_20d",
                "source",
                "ingested_at",
            ]
            frame = frame[keep_cols]
            frame = frame[
                (frame["trade_date"].astype(str).str.len() > 0)
                & (frame["symbol"].astype(str).str.len() > 0)
            ]
            if frame.empty:
                return 0
            return self.repo.upsert_dataframe(
                "global_anchor_price_daily", frame, keys=["trade_date", "symbol", "market"]
            )
        if dataset == "TaiwanStockInstitutionalInvestorsBuySell":
            frame = pd.DataFrame(rows)
            if frame.empty:
                return 0
            empty_col = pd.Series([""] * len(frame))
            frame["trade_date"] = (
                frame["date"].astype(str)
                if "date" in frame.columns
                else frame.get("trade_date", empty_col).astype(str)
            )
            frame["symbol"] = (
                frame["stock_id"].astype(str)
                if "stock_id" in frame.columns
                else frame.get("symbol", empty_col).astype(str)
            )
            frame["investor_type"] = (
                frame["name"].astype(str)
                if "name" in frame.columns
                else frame.get("investor_type", empty_col).astype(str)
            )
            frame["buy_shares"] = frame.get("buy", 0).apply(self._to_float)
            frame["sell_shares"] = frame.get("sell", 0).apply(self._to_float)
            frame["net_shares"] = frame["buy_shares"].fillna(0.0) - frame["sell_shares"].fillna(0.0)
            frame["source"] = "finmind"
            frame["ingested_at"] = datetime.now(UTC).replace(tzinfo=None)
            keep_cols = [
                "trade_date",
                "symbol",
                "investor_type",
                "buy_shares",
                "sell_shares",
                "net_shares",
                "source",
                "ingested_at",
            ]
            frame = frame[keep_cols]
            frame = frame[
                (frame["trade_date"].astype(str).str.len() > 0)
                & (frame["symbol"].astype(str).str.len() > 0)
                & (frame["investor_type"].astype(str).str.len() > 0)
            ]
            if frame.empty:
                return 0
            return self.repo.upsert_dataframe(
                "taiwan_institutional_flow",
                frame,
                keys=["trade_date", "symbol", "investor_type"],
            )
        return 0

    def _to_float(self, value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                return float(text)
            except ValueError:
                return None
        return None
