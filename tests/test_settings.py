from __future__ import annotations

from ai_chain_radar.settings import get_settings


def test_settings_defaults():
    settings = get_settings()
    assert settings.timezone == "Asia/Shanghai"
    assert str(settings.db_path).endswith(".duckdb")
