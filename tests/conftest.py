from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_chain_radar.settings import get_settings


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest):
    db_path = tmp_path / "test.duckdb"
    monkeypatch.setenv("AI_CHAIN_DB_PATH", str(db_path))
    monkeypatch.setenv("AI_CHAIN_TIMEZONE", "Asia/Shanghai")
    # Defaults: no credentials for non-integration tests.
    if request.node.get_closest_marker("integration") is None:
        monkeypatch.delenv("TUSHARE_TOKEN", raising=False)
        monkeypatch.delenv("FINMIND_TOKEN", raising=False)
        monkeypatch.delenv("SEC_USER_AGENT", raising=False)
        monkeypatch.delenv("OPENDART_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    if db_path.exists():
        os.remove(db_path)
