from __future__ import annotations

import time
from pathlib import Path

import duckdb

from ai_chain_radar.settings import get_settings


def _is_transient_db_lock_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    lock_hints = [
        "cannot open file",
        "being used by another process",
        "another process is using this file",
        "进程无法访问",
        "另一个程序正在使用此文件",
    ]
    return any(token in msg for token in lock_hints)


def get_connection(
    path: str | Path | None = None, *, read_only: bool = False
) -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    db_path = Path(path or settings.db_path)
    if not read_only:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    retry_seconds = max(0.0, float(getattr(settings, "ai_chain_db_open_retry_seconds", 0.0)))
    deadline = time.monotonic() + retry_seconds
    while True:
        try:
            return duckdb.connect(str(db_path), read_only=read_only)
        except Exception as exc:
            if not _is_transient_db_lock_error(exc) or time.monotonic() >= deadline:
                raise
            time.sleep(0.2)
