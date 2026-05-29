from __future__ import annotations

from pathlib import Path

import pytest

import ai_chain_radar.db.duckdb as duckdb_module


class _StubSettings:
    def __init__(self, db_path: Path, retry_seconds: float = 1.0) -> None:
        self.db_path = db_path
        self.ai_chain_db_open_retry_seconds = retry_seconds


def test_get_connection_retries_for_transient_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    settings = _StubSettings(tmp_path / "retry.duckdb", retry_seconds=1.0)
    monkeypatch.setattr(duckdb_module, "get_settings", lambda: settings)
    monkeypatch.setattr(duckdb_module.time, "sleep", lambda *_: None)

    calls: list[tuple[str, bool]] = []
    fake_conn = object()

    def _fake_connect(path: str, *, read_only: bool = False):
        calls.append((path, read_only))
        if len(calls) == 1:
            raise RuntimeError("Cannot open file: 另一个程序正在使用此文件")
        return fake_conn

    monkeypatch.setattr(duckdb_module.duckdb, "connect", _fake_connect)
    conn = duckdb_module.get_connection(path=settings.db_path, read_only=False)
    assert conn is fake_conn
    assert len(calls) == 2
    assert calls[0][1] is False


def test_get_connection_no_retry_for_read_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    settings = _StubSettings(tmp_path / "readonly.duckdb", retry_seconds=0.0)
    monkeypatch.setattr(duckdb_module, "get_settings", lambda: settings)

    calls = 0

    def _fake_connect(path: str, *, read_only: bool = False):
        nonlocal calls
        calls += 1
        raise RuntimeError("Cannot open file: another process is using this file")

    monkeypatch.setattr(duckdb_module.duckdb, "connect", _fake_connect)
    with pytest.raises(RuntimeError):
        duckdb_module.get_connection(path=settings.db_path, read_only=True)
    assert calls == 1
