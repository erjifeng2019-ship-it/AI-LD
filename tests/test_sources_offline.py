from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.sources.base import SourceRequest
from ai_chain_radar.sources.finmind_adapter import FinMindAdapter
from ai_chain_radar.sources.opendart_adapter import OpenDartAdapter
from ai_chain_radar.sources.sec_adapter import SecAdapter
from ai_chain_radar.sources.tushare_adapter import TushareAdapter


def test_sources_return_missing_credentials_by_default(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo = Repository()
    repo.init_db()

    tushare = TushareAdapter(repo)
    tushare_results = tushare.sync(SourceRequest(dry_run=True))
    assert len(tushare_results) > 0
    assert all(item.status in {"missing_credentials", "skipped"} for item in tushare_results)

    for adapter_cls in [SecAdapter, OpenDartAdapter]:
        adapter = adapter_cls(repo)
        results = adapter.sync(SourceRequest(dry_run=True))
        assert len(results) > 0
        assert all(item.status == "missing_credentials" for item in results)

    finmind = FinMindAdapter(repo)
    finmind_results = finmind.sync(SourceRequest(dry_run=True))
    assert len(finmind_results) > 0
    assert all(
        item.status in {"missing_credentials", "failed", "skipped"} for item in finmind_results
    )


def test_tushare_prefers_local_raw_cache_without_token(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    raw_dir = tmp_path / "data" / "raw" / "tushare" / "daily"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "2026-05-28.jsonl"
    row = {
        "trade_date": "20260528",
        "ts_code": "300308.SZ",
        "pct_chg": 1.2,
        "amount": 123456.0,
    }
    raw_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    repo = Repository()
    repo.init_db()
    adapter = TushareAdapter(repo)
    results = adapter.sync(SourceRequest(dataset="daily", date="2026-05-28"))
    assert len(results) == 1
    assert results[0].status == "ok"
    assert results[0].rows_read == 1
    assert results[0].rows_written == 1
    out = repo.query_dataframe(
        "SELECT trade_date, ts_code FROM a_share_market_confirmation WHERE ts_code='300308.SZ'"
    )
    assert len(out) == 1


@pytest.mark.parametrize(
    ("dataset", "row", "table_name"),
    [
        (
            "anns_d",
            {
                "ann_date": "20260528",
                "ts_code": "300308.SZ",
                "name": "X",
                "title": "公告A",
                "url": "https://example.com/a",
            },
            "a_share_announcement_event",
        ),
        (
            "research_report",
            {
                "trade_date": "20260528",
                "title": "研报A",
                "report_type": "个股研报",
                "author": "A",
                "name": "Y",
                "ts_code": "300308.SZ",
                "inst_csname": "机构A",
                "ind_name": "行业A",
                "url": "https://example.com/r",
            },
            "a_share_research_report_event",
        ),
        (
            "report_rc",
            {
                "ts_code": "300308.SZ",
                "name": "Y",
                "report_date": "20260528",
                "report_title": "评级A",
                "report_type": "点评",
                "classify": "首评",
                "org_name": "机构A",
                "author_name": "作者A",
                "quarter": "2026Q4",
                "op_rt": 1.0,
                "op_pr": 2.0,
                "tp": 3.0,
                "np": 4.0,
                "eps": 5.0,
                "pe": 6.0,
                "rd": 7.0,
                "roe": 8.0,
                "ev_ebitda": 9.0,
                "rating": "买入",
                "max_price": 10.0,
                "min_price": 11.0,
            },
            "a_share_report_rating_event",
        ),
    ],
)
def test_tushare_structured_tables_from_local_raw(
    tmp_path: Path, monkeypatch, dataset: str, row: dict[str, object], table_name: str
):
    monkeypatch.chdir(tmp_path)
    raw_dir = tmp_path / "data" / "raw" / "tushare" / dataset
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "2026-05-28.jsonl"
    raw_path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")

    repo = Repository()
    repo.init_db()
    adapter = TushareAdapter(repo)
    results = adapter.sync(SourceRequest(dataset=dataset, date="2026-05-28"))
    assert len(results) == 1
    assert results[0].status == "ok"
    assert results[0].rows_read == 1
    assert results[0].rows_written == 1
    out = repo.query_dataframe(f"SELECT COUNT(*) AS c FROM {table_name}")
    assert int(out.iloc[0]["c"]) == 1


def test_sec_companyfacts_structured_write(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "test-agent test@example.com")
    repo = Repository()
    repo.init_db()
    adapter = SecAdapter(repo)

    def fake_fetch(dataset: str, tickers: list[str]):
        assert dataset == "companyfacts"
        assert tickers == ["NVDA"]
        return [
            {
                "fact_id": "fact-1",
                "cik": "1045810",
                "symbol": "NVDA",
                "company_name": "NVIDIA CORP",
                "metric_name": "revenue",
                "xbrl_tag": "Revenues",
                "unit": "USD",
                "period_end": "2026-03-31",
                "filed_date": "2026-05-01",
                "fiscal_year": "2026",
                "fiscal_period": "Q1",
                "form_type": "10-Q",
                "value": 123.0,
                "source": "sec",
            }
        ]

    monkeypatch.setattr(adapter, "_fetch_rows_real", fake_fetch)
    results = adapter.sync(SourceRequest(dataset="companyfacts", symbols=["NVDA"]))
    assert len(results) == 1
    assert results[0].status == "ok"
    assert results[0].rows_written == 1
    out = repo.query_dataframe("SELECT COUNT(*) AS c FROM us_sec_company_fact")
    assert int(out.iloc[0]["c"]) == 1


def test_opendart_corp_code_structured_write(monkeypatch):
    monkeypatch.setenv("OPENDART_API_KEY", "test-key")
    repo = Repository()
    repo.init_db()
    adapter = OpenDartAdapter(repo)

    def fake_fetch(dataset: str, symbols: list[str], request):
        assert dataset == "corp_code"
        assert symbols == ["005930"]
        return [
            {
                "corp_code": "00126380",
                "stock_code": "005930",
                "corp_name": "Samsung Electronics",
                "modify_date": "20260528",
            }
        ]

    monkeypatch.setattr(adapter, "_fetch_rows_real", fake_fetch)
    results = adapter.sync(SourceRequest(dataset="corp_code", symbols=["005930"]))
    assert len(results) == 1
    assert results[0].status == "ok"
    assert results[0].rows_written == 1
    out = repo.query_dataframe("SELECT COUNT(*) AS c FROM korea_corp_code_master")
    assert int(out.iloc[0]["c"]) == 1


def test_finmind_institutional_flow_structured_write(monkeypatch):
    monkeypatch.setenv("FINMIND_TOKEN", "test-token")
    repo = Repository()
    repo.init_db()
    adapter = FinMindAdapter(repo)

    def fake_fetch(dataset: str, request, token: str | None):
        assert dataset == "TaiwanStockInstitutionalInvestorsBuySell"
        assert token == "test-token"
        return [
            {
                "date": "2026-05-28",
                "stock_id": "2330",
                "name": "Foreign_Investor",
                "buy": 1000,
                "sell": 700,
            }
        ]

    monkeypatch.setattr(adapter, "_fetch_rows_real", fake_fetch)
    results = adapter.sync(SourceRequest(dataset="TaiwanStockInstitutionalInvestorsBuySell"))
    assert len(results) == 1
    assert results[0].status == "ok"
    assert results[0].rows_written == 1
    out = repo.query_dataframe("SELECT COUNT(*) AS c FROM taiwan_institutional_flow")
    assert int(out.iloc[0]["c"]) == 1
