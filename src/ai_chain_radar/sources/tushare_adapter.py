from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha1
from typing import Any

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.settings import get_settings
from ai_chain_radar.sources.base import BaseSourceAdapter, SourceRequest, SyncResult


class TushareAdapter(BaseSourceAdapter):
    source_name = "tushare"
    datasets = [
        "stock_basic",
        "stock_company",
        "daily",
        "daily_basic",
        "fina_mainbz",
        "income",
        "fina_indicator",
        "anns_d",
        "research_report",
        "report_rc",
        "limit_list_d",
        "top_list",
        "top_inst",
        "moneyflow",
        "margin_detail",
        "hk_daily",
        "hk_mins",
    ]

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def sync(self, request: SourceRequest) -> list[SyncResult]:
        settings = get_settings()
        targets = [request.dataset] if request.dataset else self.datasets
        results: list[SyncResult] = []
        prefer_raw_cache = bool(request.extra.get("prefer_raw_cache", True))

        for dataset in targets:
            started_at = datetime.now(UTC).replace(tzinfo=None)
            if dataset in {"fina_mainbz", "income", "fina_indicator", "hk_mins"}:
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="skipped",
                        error_message=(
                            f"{dataset} requires symbol/period/freq scoped pulls; "
                            "bulk mode is not enabled in MVP."
                        ),
                        started_at=started_at,
                    )
                )
                continue
            if request.dry_run and not settings.tushare_token:
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="missing_credentials",
                        error_message="Missing TUSHARE_TOKEN, configure it in .env",
                        started_at=started_at,
                    )
                )
                continue
            if request.dry_run:
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status="skipped",
                        rows_read=0,
                        rows_written=0,
                        error_message="dry-run enabled, skipped network fetch",
                        started_at=started_at,
                    )
                )
                continue
            try:
                rows: list[dict[str, Any]] | None = None
                raw_path: str | None = None
                date_label = request.date or "latest"
                if prefer_raw_cache:
                    cached = self._load_raw_jsonl(dataset, date_label)
                    if cached is not None:
                        rows, raw_path = cached
                if rows is None:
                    if not settings.tushare_token:
                        results.append(
                            self._new_result(
                                dataset=dataset,
                                request=request,
                                status="missing_credentials",
                                error_message="Missing TUSHARE_TOKEN, configure it in .env",
                                started_at=started_at,
                            )
                        )
                        continue
                    rows = self._fetch_rows_real(dataset=dataset, request=request)
                    raw_path = self._save_raw_jsonl(dataset, date_label, rows)
                written = self._normalize_and_write(dataset, rows, request.date or "1970-01-01")
                if len(rows) > 0 and written == 0:
                    status = "partial"
                elif written > 0:
                    status = "ok"
                else:
                    status = "empty"
                results.append(
                    self._new_result(
                        dataset=dataset,
                        request=request,
                        status=status,
                        rows_read=len(rows),
                        rows_written=written,
                        raw_path=raw_path,
                        started_at=started_at,
                    )
                )
            except Exception as exc:
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

    def _fetch_rows_real(self, dataset: str, request: SourceRequest) -> list[dict[str, Any]]:
        try:
            import tushare as ts  # type: ignore
        except Exception as exc:  # pragma: no cover - runtime dependency branch
            raise RuntimeError("tushare package is required for real sync") from exc

        settings = get_settings()
        pro = ts.pro_api(settings.tushare_token)
        trade_date = (request.date or "").replace("-", "")
        params = self._build_query_params(dataset=dataset, trade_date=trade_date)
        call = getattr(pro, dataset, None)
        if callable(call):
            data = call(**params)
        else:
            data = pro.query(dataset, **params)
        if data is None or data.empty:
            return []
        return data.fillna("").to_dict(orient="records")

    def _build_query_params(self, dataset: str, trade_date: str) -> dict[str, Any]:
        if dataset == "stock_basic":
            return {"exchange": "", "list_status": "L", "fields": "ts_code,name"}
        if dataset == "stock_company":
            return {"exchange": "SZSE", "fields": "ts_code,chairman,manager,main_business"}
        if dataset == "anns_d":
            return {"ann_date": trade_date} if trade_date else {}
        if dataset == "research_report":
            return {"trade_date": trade_date} if trade_date else {}
        if dataset == "report_rc":
            return {"report_date": trade_date} if trade_date else {}
        if dataset in {
            "daily",
            "daily_basic",
            "limit_list_d",
            "top_list",
            "top_inst",
            "moneyflow",
            "margin_detail",
            "hk_daily",
        }:
            return {"trade_date": trade_date} if trade_date else {}
        return {"trade_date": trade_date} if trade_date else {}

    def _normalize_and_write(self, dataset: str, rows: list[dict[str, Any]], date: str) -> int:
        if not rows:
            return 0
        if dataset in {"stock_basic", "stock_company"}:
            frame = pd.DataFrame(
                [
                    {
                        "ts_code": item["ts_code"],
                        "name": item.get("name", item["ts_code"]),
                        "segment": "unknown",
                        "sub_segment": "unknown",
                        "product": "unknown",
                        "global_anchor_links": "",
                        "purity_level": "concept",
                        "is_core": False,
                        "is_second_order": False,
                        "is_concept_only": True,
                        "last_verified_at": datetime.now(UTC).replace(tzinfo=None),
                    }
                    for item in rows
                ]
            )
            return self.repo.upsert_dataframe(
                "a_share_chain_mapping", frame, keys=["ts_code", "segment", "sub_segment"]
            )
        if dataset == "anns_d":
            return self._write_anns_d(rows=rows, fallback_date=date)
        if dataset == "research_report":
            return self._write_research_report(rows=rows, fallback_date=date)
        if dataset == "report_rc":
            return self._write_report_rc(rows=rows, fallback_date=date)

        frame = pd.DataFrame(
            [
                {
                    "trade_date": self._normalize_trade_date(item.get("trade_date"), fallback=date),
                    "ts_code": item.get("ts_code", ""),
                    "segment": "unknown",
                    "pct_chg": item.get("pct_chg", item.get("pct_change")),
                    "amount": self._normalize_amount(item),
                    "source": "tushare",
                    "ingested_at": datetime.now(UTC).replace(tzinfo=None),
                }
                for item in rows
                if item.get("ts_code")
            ]
        )
        if frame.empty:
            return 0
        frame = (
            frame.groupby(["trade_date", "ts_code", "segment"], as_index=False, dropna=False)
            .agg(
                {
                    "pct_chg": "max",
                    "amount": "sum",
                    "source": "first",
                    "ingested_at": "max",
                }
            )
            .sort_values(by=["trade_date", "ts_code"])
        )
        return self.repo.upsert_dataframe(
            "a_share_market_confirmation", frame, keys=["trade_date", "ts_code", "segment"]
        )

    def _write_anns_d(self, rows: list[dict[str, Any]], fallback_date: str) -> int:
        ingested_at = datetime.now(UTC).replace(tzinfo=None)
        payload: list[dict[str, Any]] = []
        for item in rows:
            ts_code = str(item.get("ts_code", "")).strip()
            if not ts_code:
                continue
            ann_date = self._normalize_trade_date(item.get("ann_date"), fallback=fallback_date)
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            ann_id = self._stable_id(ann_date, ts_code, title, url)
            payload.append(
                {
                    "ann_id": ann_id,
                    "ann_date": ann_date,
                    "ts_code": ts_code,
                    "name": str(item.get("name", "")).strip(),
                    "title": title,
                    "url": url,
                    "source": "tushare",
                    "ingested_at": ingested_at,
                }
            )
        if not payload:
            return 0
        frame = pd.DataFrame(payload)
        return self.repo.upsert_dataframe("a_share_announcement_event", frame, keys=["ann_id"])

    def _write_research_report(self, rows: list[dict[str, Any]], fallback_date: str) -> int:
        ingested_at = datetime.now(UTC).replace(tzinfo=None)
        payload: list[dict[str, Any]] = []
        for item in rows:
            trade_date = self._normalize_trade_date(item.get("trade_date"), fallback=fallback_date)
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            inst = str(item.get("inst_csname", "")).strip()
            report_id = self._stable_id(trade_date, title, url, inst)
            payload.append(
                {
                    "report_id": report_id,
                    "trade_date": trade_date,
                    "ts_code": str(item.get("ts_code", "")).strip(),
                    "name": str(item.get("name", "")).strip(),
                    "title": title,
                    "report_type": str(item.get("report_type", "")).strip(),
                    "author": str(item.get("author", "")).strip(),
                    "inst_csname": inst,
                    "ind_name": str(item.get("ind_name", "")).strip(),
                    "url": url,
                    "source": "tushare",
                    "ingested_at": ingested_at,
                }
            )
        if not payload:
            return 0
        frame = pd.DataFrame(payload)
        return self.repo.upsert_dataframe(
            "a_share_research_report_event", frame, keys=["report_id"]
        )

    def _write_report_rc(self, rows: list[dict[str, Any]], fallback_date: str) -> int:
        ingested_at = datetime.now(UTC).replace(tzinfo=None)
        payload: list[dict[str, Any]] = []
        for item in rows:
            report_date = self._normalize_trade_date(
                item.get("report_date"), fallback=fallback_date
            )
            ts_code = str(item.get("ts_code", "")).strip()
            report_title = str(item.get("report_title", "")).strip()
            org_name = str(item.get("org_name", "")).strip()
            author_name = str(item.get("author_name", "")).strip()
            quarter = str(item.get("quarter", "")).strip()
            rating_id = self._stable_id(
                report_date, ts_code, report_title, org_name, author_name, quarter
            )
            payload.append(
                {
                    "rating_id": rating_id,
                    "report_date": report_date,
                    "ts_code": ts_code,
                    "name": str(item.get("name", "")).strip(),
                    "report_title": report_title,
                    "report_type": str(item.get("report_type", "")).strip(),
                    "classify": str(item.get("classify", "")).strip(),
                    "org_name": org_name,
                    "author_name": author_name,
                    "quarter": quarter,
                    "op_rt": self._to_float(item.get("op_rt")),
                    "op_pr": self._to_float(item.get("op_pr")),
                    "tp": self._to_float(item.get("tp")),
                    "np": self._to_float(item.get("np")),
                    "eps": self._to_float(item.get("eps")),
                    "pe": self._to_float(item.get("pe")),
                    "rd": self._to_float(item.get("rd")),
                    "roe": self._to_float(item.get("roe")),
                    "ev_ebitda": self._to_float(item.get("ev_ebitda")),
                    "rating": str(item.get("rating", "")).strip(),
                    "max_price": self._to_float(item.get("max_price")),
                    "min_price": self._to_float(item.get("min_price")),
                    "source": "tushare",
                    "ingested_at": ingested_at,
                }
            )
        if not payload:
            return 0
        frame = pd.DataFrame(payload)
        return self.repo.upsert_dataframe("a_share_report_rating_event", frame, keys=["rating_id"])

    def _normalize_trade_date(self, value: Any, fallback: str) -> str:
        text = str(value or fallback).strip()
        if len(text) == 8 and text.isdigit():
            return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
        return text

    def _normalize_amount(self, item: dict[str, Any]) -> float | None:
        raw = item.get("amount")
        if raw in (None, ""):
            raw = item.get("net_buy")
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return None
            try:
                return float(text)
            except ValueError:
                return None
        return None

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

    def _stable_id(self, *parts: str) -> str:
        token = "|".join(part.strip() for part in parts)
        return sha1(token.encode("utf-8")).hexdigest()
