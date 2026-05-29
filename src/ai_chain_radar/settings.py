from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    ai_chain_env: str = Field(default="local", alias="AI_CHAIN_ENV")
    ai_chain_db_path: str = Field(
        default="data/warehouse/ai_chain.duckdb", alias="AI_CHAIN_DB_PATH"
    )
    ai_chain_db_open_retry_seconds: float = Field(
        default=8.0, alias="AI_CHAIN_DB_OPEN_RETRY_SECONDS"
    )
    ai_chain_timezone: str = Field(default="Asia/Shanghai", alias="AI_CHAIN_TIMEZONE")
    tushare_token: str = Field(default="", alias="TUSHARE_TOKEN")
    finmind_token: str = Field(default="", alias="FINMIND_TOKEN")
    sec_user_agent: str = Field(default="", alias="SEC_USER_AGENT")
    opendart_api_key: str = Field(default="", alias="OPENDART_API_KEY")
    jquants_email: str = Field(default="", alias="JQUANTS_EMAIL")
    jquants_password: str = Field(default="", alias="JQUANTS_PASSWORD")
    jquants_refresh_token: str = Field(default="", alias="JQUANTS_REFRESH_TOKEN")
    fred_api_key: str = Field(default="", alias="FRED_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    fmp_api_key: str = Field(default="", alias="FMP_API_KEY")
    tiingo_api_key: str = Field(default="", alias="TIINGO_API_KEY")
    polygon_api_key: str = Field(default="", alias="POLYGON_API_KEY")

    @property
    def db_path(self) -> Path:
        return Path(self.ai_chain_db_path)

    @property
    def timezone(self) -> str:
        return self.ai_chain_timezone


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid yaml object from {path}")
    return data
