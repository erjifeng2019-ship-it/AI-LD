from __future__ import annotations

import os

import pytest

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.sources.base import SourceRequest
from ai_chain_radar.sources.finmind_adapter import FinMindAdapter
from ai_chain_radar.sources.opendart_adapter import OpenDartAdapter
from ai_chain_radar.sources.sec_adapter import SecAdapter
from ai_chain_radar.sources.tushare_adapter import TushareAdapter


@pytest.mark.integration
def test_tushare_integration_daily():
    if not os.getenv("TUSHARE_TOKEN"):
        pytest.skip("TUSHARE_TOKEN missing")
    repo = Repository()
    repo.init_db()
    adapter = TushareAdapter(repo)
    results = adapter.sync(SourceRequest(dataset="daily", date="2026-05-28"))
    assert len(results) == 1
    assert results[0].status in {"ok", "empty", "failed"}


@pytest.mark.integration
def test_finmind_integration_month_revenue():
    if not os.getenv("FINMIND_TOKEN"):
        pytest.skip("FINMIND_TOKEN missing")
    repo = Repository()
    repo.init_db()
    adapter = FinMindAdapter(repo)
    results = adapter.sync(
        SourceRequest(
            dataset="TaiwanStockMonthRevenue",
            start="2026-01-01",
            end="2026-05-28",
            symbols=["2330"],
        )
    )
    assert len(results) == 1
    assert results[0].status in {"ok", "empty", "failed"}


@pytest.mark.integration
def test_sec_integration_submissions():
    if not os.getenv("SEC_USER_AGENT"):
        pytest.skip("SEC_USER_AGENT missing")
    repo = Repository()
    repo.init_db()
    adapter = SecAdapter(repo)
    results = adapter.sync(SourceRequest(dataset="submissions", symbols=["NVDA"]))
    assert len(results) == 1
    assert results[0].status in {"ok", "empty", "failed"}


@pytest.mark.integration
def test_sec_integration_companyfacts():
    if not os.getenv("SEC_USER_AGENT"):
        pytest.skip("SEC_USER_AGENT missing")
    repo = Repository()
    repo.init_db()
    adapter = SecAdapter(repo)
    results = adapter.sync(SourceRequest(dataset="companyfacts", symbols=["NVDA"]))
    assert len(results) == 1
    assert results[0].status in {"ok", "empty", "failed"}


@pytest.mark.integration
def test_opendart_integration_disclosures():
    if not os.getenv("OPENDART_API_KEY"):
        pytest.skip("OPENDART_API_KEY missing")
    repo = Repository()
    repo.init_db()
    adapter = OpenDartAdapter(repo)
    results = adapter.sync(
        SourceRequest(
            dataset="disclosures",
            symbols=["005930"],
            start="2026-01-01",
            end="2026-05-28",
        )
    )
    assert len(results) == 1
    assert results[0].status in {"ok", "empty", "failed"}


@pytest.mark.integration
def test_opendart_integration_corp_code():
    if not os.getenv("OPENDART_API_KEY"):
        pytest.skip("OPENDART_API_KEY missing")
    repo = Repository()
    repo.init_db()
    adapter = OpenDartAdapter(repo)
    results = adapter.sync(SourceRequest(dataset="corp_code", symbols=["005930"]))
    assert len(results) == 1
    assert results[0].status in {"ok", "empty", "failed"}
