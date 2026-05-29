from __future__ import annotations

import json

from ai_chain_radar.briefing.renderer import render_daily_briefing
from ai_chain_radar.db.repository import Repository
from ai_chain_radar.evidence.extractor import extract_evidence_for_date
from ai_chain_radar.scoring.opportunity_score import OpportunityScore
from ai_chain_radar.taxonomy.mapping import load_taxonomy


def test_briefing_generation() -> None:
    repo = Repository()
    repo.init_db()
    load_taxonomy(repo)
    repo.query_dataframe(
        """
        INSERT INTO global_anchor_price_daily (
          trade_date, symbol, market, close, pct_chg, source, ingested_at
        ) VALUES
          ('2026-05-28', 'MU', 'US', 120, 2.5, 'test', now())
        """
    )
    repo.query_dataframe(
        """
        INSERT INTO a_share_chain_mapping (
          ts_code, name, segment, sub_segment, source_evidence, notes, evidence_level, is_latest
        ) VALUES (
          '300308.SZ', '中际旭创', 'optics_cpo_16t', 'cpo_optics',
          'https://example.com/mapping', 'CPO主链映射', 'A2', TRUE
        )
        """
    )
    extract_evidence_for_date(repo, "2026-05-28")
    repo.query_dataframe(
        """
        INSERT INTO counter_evidence_rule (
          rule_id, segment, rule_name, rule_type, condition_expr,
          severity, description, enabled, updated_at
        ) VALUES (
          'brief-risk-rule-1', NULL, '确认不足惩罚', 'threshold',
          'a_share_confirmation_score < 90', 'high',
          'A股确认度偏弱，需警惕跟涨失败。', TRUE, now()
        )
        """
    )
    OpportunityScore().run(repo, "2026-05-28")
    out = render_daily_briefing(repo, "2026-05-28")
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "2026-05-28" in content
    assert "确认不足惩罚" in content
    assert "evidence_id" in content
    assert "证据质量摘要" in content

    score_row = repo.query_dataframe(
        """
        SELECT evidence_json
        FROM theme_opportunity_score
        WHERE score_date = '2026-05-28' AND segment = 'optics_cpo_16t'
        """
    ).iloc[0]
    evidence_items = json.loads(str(score_row["evidence_json"]))
    assert any(str(item.get("evidence_id", "")).startswith("map_") for item in evidence_items)
