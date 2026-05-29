from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

import pandas as pd


@dataclass
class SourceRequest:
    dataset: str | None = None
    date: str | None = None
    start: str | None = None
    end: str | None = None
    symbols: list[str] = field(default_factory=list)
    dry_run: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_params(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "date": self.date,
            "start": self.start,
            "end": self.end,
            "symbols": self.symbols,
            "dry_run": self.dry_run,
            **self.extra,
        }


@dataclass
class SyncResult:
    run_id: str
    source: str
    dataset: str
    params: dict[str, Any]
    rows_read: int
    rows_written: int
    status: str
    started_at: datetime
    ended_at: datetime
    error_message: str | None = None
    raw_path: str | None = None


class SourceAdapter(Protocol):
    source_name: str

    def sync(self, request: SourceRequest) -> list[SyncResult]: ...


class BaseSourceAdapter:
    source_name: str = "base"

    def _new_result(
        self,
        dataset: str,
        request: SourceRequest,
        status: str,
        rows_read: int = 0,
        rows_written: int = 0,
        error_message: str | None = None,
        raw_path: str | None = None,
        started_at: datetime | None = None,
    ) -> SyncResult:
        start = started_at or datetime.now(UTC).replace(tzinfo=None)
        return SyncResult(
            run_id=uuid4().hex,
            source=self.source_name,
            dataset=dataset,
            params=request.to_params(),
            rows_read=rows_read,
            rows_written=rows_written,
            status=status,
            started_at=start,
            ended_at=datetime.now(UTC).replace(tzinfo=None),
            error_message=error_message,
            raw_path=raw_path,
        )

    def _save_raw_jsonl(self, dataset: str, date_label: str, rows: list[dict[str, Any]]) -> str:
        out_dir = Path("data/raw") / self.source_name / dataset
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{date_label}.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return str(out_path)

    def _raw_jsonl_path(self, dataset: str, date_label: str) -> Path:
        return Path("data/raw") / self.source_name / dataset / f"{date_label}.jsonl"

    def _load_raw_jsonl(
        self, dataset: str, date_label: str
    ) -> tuple[list[dict[str, Any]], str] | None:
        path = self._raw_jsonl_path(dataset, date_label)
        if not path.exists():
            return None
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                text = line.strip()
                if not text:
                    continue
                rows.append(json.loads(text))
        return rows, str(path)

    def _frame(self, rows: list[dict[str, Any]]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)
