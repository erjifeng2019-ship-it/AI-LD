from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.sources.base import BaseSourceAdapter, SourceRequest, SyncResult


class GlobalAnchorAdapter(BaseSourceAdapter):
    source_name = "global_anchors"
    dataset_name = "prices"

    _TW_SYMBOL_MAP = {
        "TSMC": "2330.TW",
        "ASE": "3711.TW",
        "GUC": "3443.TW",
        "ALCHIP": "3661.TW",
        "WIWYNN": "6669.TW",
        "QUANTA": "2382.TW",
        "WISTRON": "3231.TW",
        "UNIMICRON": "3037.TW",
        "KINSUS": "3189.TW",
        "ACCTON": "2345.TW",
        "DELTA": "2308.TW",
        "LOTES": "3533.TW",
    }

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def sync(self, request: SourceRequest) -> list[SyncResult]:
        dataset = request.dataset or self.dataset_name
        if request.dry_run:
            return [
                self._new_result(
                    dataset=dataset,
                    request=request,
                    status="skipped",
                    error_message="dry-run enabled, skipped network fetch",
                )
            ]

        started_at = datetime.now(UTC).replace(tzinfo=None)
        trade_date = request.date or datetime.now(UTC).strftime("%Y-%m-%d")
        anchors = self.repo.query_dataframe(
            """
            SELECT symbol, market
            FROM global_anchor_security
            ORDER BY symbol, market
            """
        )
        if anchors.empty:
            return [
                self._new_result(
                    dataset=dataset,
                    request=request,
                    status="empty",
                    error_message=(
                        "global_anchor_security is empty, "
                        "run `ai-chain load-taxonomy` first"
                    ),
                    started_at=started_at,
                )
            ]

        rows: list[dict[str, Any]] = []
        for row in anchors.itertuples(index=False):
            parsed = self._fetch_stooq_daily(
                symbol=str(row.symbol),
                market=str(row.market),
                expected_date=trade_date,
            )
            if parsed is not None:
                rows.append(parsed)

        if not rows:
            return [
                self._new_result(
                    dataset=dataset,
                    request=request,
                    status="empty",
                    rows_read=0,
                    rows_written=0,
                    error_message="no global anchor rows fetched for current date/window",
                    started_at=started_at,
                )
            ]

        raw_path = self._save_raw_jsonl(dataset, trade_date, rows)
        frame = pd.DataFrame(rows)
        written = self.repo.upsert_dataframe(
            "global_anchor_price_daily",
            frame,
            keys=["trade_date", "symbol", "market"],
        )
        return [
            self._new_result(
                dataset=dataset,
                request=request,
                status="ok" if written > 0 else "empty",
                rows_read=len(rows),
                rows_written=written,
                raw_path=raw_path,
                started_at=started_at,
            )
        ]

    def _fetch_stooq_daily(
        self, symbol: str, market: str, expected_date: str
    ) -> dict[str, Any] | None:
        stooq_symbol = self._to_stooq_symbol(symbol=symbol, market=market)
        if not stooq_symbol:
            return None

        query = urlencode({"s": stooq_symbol, "i": "d"})
        req = Request(url=f"https://stooq.com/q/d/l/?{query}", method="GET")
        with urlopen(req, timeout=15) as resp:  # noqa: S310
            text = resp.read().decode("utf-8", errors="ignore")
        csv_rows = list(csv.DictReader(io.StringIO(text)))
        if not csv_rows:
            return None

        pick = csv_rows[-1]
        trade_date = str(pick.get("Date", "")).strip() or expected_date
        close = self._to_float(pick.get("Close"))
        if close is None:
            return None
        return {
            "trade_date": trade_date,
            "symbol": symbol,
            "market": market,
            "open": self._to_float(pick.get("Open")),
            "high": self._to_float(pick.get("High")),
            "low": self._to_float(pick.get("Low")),
            "close": close,
            "pre_close": None,
            "pct_chg": None,
            "volume": self._to_float(pick.get("Volume")),
            "amount": None,
            "relative_strength_5d": None,
            "relative_strength_20d": None,
            "source": "stooq",
            "ingested_at": datetime.now(UTC).replace(tzinfo=None),
        }

    def _to_stooq_symbol(self, symbol: str, market: str) -> str:
        sym = symbol.strip().upper()
        mkt = market.strip().upper()
        if mkt == "US":
            return f"{sym}.US"
        if mkt == "TW":
            if sym.isdigit():
                return f"{sym}.TW"
            mapped = self._TW_SYMBOL_MAP.get(sym)
            return mapped or ""
        if mkt == "HK":
            return f"{sym}.HK"
        if mkt == "JP":
            return f"{sym}.JP"
        if mkt == "KR":
            return f"{sym}.KR"
        return ""

    def _to_float(self, value: object) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value or "").strip()
        if not text or text.lower() in {"null", "none", "nan"}:
            return None
        try:
            return float(text)
        except ValueError:
            return None
