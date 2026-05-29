from __future__ import annotations

import json

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.scoring.opportunity_score import OpportunityScore
from ai_chain_radar.taxonomy.mapping import load_taxonomy


def test_counter_evidence_rule_affects_score_and_risk() -> None:
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

    scorer = OpportunityScore()
    scorer.run(repo, "2026-05-28")
    baseline = repo.query_dataframe(
        """
        SELECT final_score, risk_score
        FROM theme_opportunity_score
        WHERE score_date = '2026-05-28' AND segment = 'optics_cpo_16t'
        """
    ).iloc[0]
    baseline_final = float(baseline["final_score"])
    baseline_risk = float(baseline["risk_score"])

    repo.query_dataframe(
        """
        INSERT INTO counter_evidence_rule (
          rule_id, segment, rule_name, rule_type, condition_expr,
          severity, description, enabled, updated_at
        ) VALUES (
          'risk-rule-weak-confirm', NULL, '弱确认惩罚', 'threshold',
          'a_share_confirmation_score < 90', 'high',
          '确认度低于阈值，可能是跟风而非主升。', TRUE, now()
        )
        """
    )
    scorer.run(repo, "2026-05-28")

    current = repo.query_dataframe(
        """
        SELECT final_score, risk_score, invalid_conditions_json, evidence_json
        FROM theme_opportunity_score
        WHERE score_date = '2026-05-28' AND segment = 'optics_cpo_16t'
        """
    ).iloc[0]
    assert float(current["final_score"]) < baseline_final
    assert float(current["risk_score"]) < baseline_risk

    invalid = json.loads(str(current["invalid_conditions_json"]))
    assert "弱确认惩罚" in " ".join(invalid)

    evidence = json.loads(str(current["evidence_json"]))
    assert any(item.get("source") == "counter_evidence_rule" for item in evidence)
