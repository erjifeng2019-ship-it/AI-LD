from __future__ import annotations

from ai_chain_radar.db.repository import Repository


def test_schema_tables_created():
    repo = Repository()
    repo.init_db()
    tables = repo.query_dataframe("SHOW TABLES")
    names = set(tables["name"].tolist())
    required = {
        "source_run_log",
        "global_anchor_security",
        "global_anchor_price_daily",
        "taiwan_monthly_revenue",
        "taiwan_institutional_flow",
        "us_sec_filing_event",
        "us_sec_company_fact",
        "korea_disclosure_event",
        "korea_corp_code_master",
        "industry_cycle_metric",
        "ai_chain_segment",
        "a_share_chain_mapping",
        "a_share_market_confirmation",
        "a_share_announcement_event",
        "a_share_research_report_event",
        "a_share_report_rating_event",
        "theme_opportunity_score",
        "daily_ai_chain_briefing",
        "a_share_chain_mapping_history",
        "a_share_chain_mapping_version",
        "evidence_registry",
        "signal_review_result",
        "signal_review_summary",
        "counter_evidence_rule",
        "segment_market_confirmation_daily",
        "data_quality_report",
    }
    assert required.issubset(names)
