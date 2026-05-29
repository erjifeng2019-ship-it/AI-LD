from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd

from ai_chain_radar.db.repository import Repository


@dataclass
class GlobalPriceImportResult:
    import_id: str
    row_count: int
    checksum: str
    source_file: str
    trade_date: str


class GlobalPriceImporter:
    REQUIRED_COLUMNS = {"trade_date", "symbol", "market", "close"}
    COLUMN_ALIASES = {
        "date": "trade_date",
        "ticker": "symbol",
        "exchange": "market",
        "prev_close": "pre_close",
        "pct_change": "pct_chg",
        "turnover": "amount",
    }

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def import_file(self, file_path: str | Path, notes: str = "") -> GlobalPriceImportResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Global price file not found: {path}")

        raw_bytes = path.read_bytes()
        checksum = hashlib.sha256(raw_bytes).hexdigest()
        import_id = f"gap_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        imported_at = datetime.now(UTC).replace(tzinfo=None)

        raw_df = self._read_tabular(path)
        frame = self._normalize(raw_df, imported_at=imported_at)
        if frame.empty:
            raise ValueError("No valid global anchor price rows found.")

        written = self.repo.upsert_dataframe(
            "global_anchor_price_daily",
            frame,
            keys=["trade_date", "symbol", "market"],
        )
        trade_date = str(frame["trade_date"].iloc[0])
        markets = sorted(set(frame["market"].astype(str).tolist()))
        self.repo.upsert_dataframe(
            "global_anchor_manual_price_import",
            pd.DataFrame(
                [
                    {
                        "import_id": import_id,
                        "source_file": str(path),
                        "market": ",".join(markets),
                        "imported_at": imported_at,
                        "row_count": written,
                        "checksum": checksum,
                        "notes": notes or "imported by ai-chain import global-prices",
                    }
                ]
            ),
            keys=["import_id"],
        )
        return GlobalPriceImportResult(
            import_id=import_id,
            row_count=written,
            checksum=checksum,
            source_file=str(path),
            trade_date=trade_date,
        )

    def _read_tabular(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path)
        if suffix in {".xlsx", ".xlsm", ".xls"}:
            return pd.read_excel(path)
        raise ValueError(f"Unsupported file type: {suffix}")

    def _normalize(self, df: pd.DataFrame, imported_at: datetime) -> pd.DataFrame:
        work = df.copy()
        rename_map: dict[str, str] = {}
        for col in work.columns:
            key = str(col).strip().lower()
            if key in self.COLUMN_ALIASES:
                rename_map[col] = self.COLUMN_ALIASES[key]
        work = work.rename(columns=rename_map)

        missing = sorted(col for col in self.REQUIRED_COLUMNS if col not in work.columns)
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        work["trade_date"] = work["trade_date"].apply(self._normalize_date)
        work["symbol"] = work["symbol"].astype(str).str.strip().str.upper()
        work["market"] = work["market"].astype(str).str.strip().str.upper()
        work["open"] = work.get("open", pd.Series([None] * len(work))).apply(self._to_float)
        work["high"] = work.get("high", pd.Series([None] * len(work))).apply(self._to_float)
        work["low"] = work.get("low", pd.Series([None] * len(work))).apply(self._to_float)
        work["close"] = work["close"].apply(self._to_float)
        work["pre_close"] = work.get("pre_close", pd.Series([None] * len(work))).apply(
            self._to_float
        )
        work["pct_chg"] = work.get("pct_chg", pd.Series([None] * len(work))).apply(self._to_float)
        work["volume"] = work.get("volume", pd.Series([None] * len(work))).apply(self._to_float)
        work["amount"] = work.get("amount", pd.Series([None] * len(work))).apply(self._to_float)
        work["relative_strength_5d"] = work.get(
            "relative_strength_5d", pd.Series([None] * len(work))
        ).apply(self._to_float)
        work["relative_strength_20d"] = work.get(
            "relative_strength_20d", pd.Series([None] * len(work))
        ).apply(self._to_float)
        work["source"] = (
            work.get("source", pd.Series(["manual"] * len(work))).astype(str).str.strip()
        )
        work["ingested_at"] = imported_at

        work = work[
            (work["trade_date"].astype(str).str.len() == 10)
            & (work["symbol"].astype(str).str.len() > 0)
            & (work["market"].astype(str).str.len() > 0)
            & work["close"].notna()
        ]
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
        return work[keep_cols].drop_duplicates(
            subset=["trade_date", "symbol", "market"],
            keep="last",
        )

    def _normalize_date(self, value: object) -> str:
        text = str(value or "").strip()
        if len(text) == 8 and text.isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
        return text

    def _to_float(self, value: object) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
