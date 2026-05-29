from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.evidence.rules import CounterEvidenceRuleEngine
from ai_chain_radar.scoring.bottleneck_score import BottleneckScore
from ai_chain_radar.scoring.global_anchor_score import GlobalAnchorScore
from ai_chain_radar.scoring.mapping_score import MappingScore
from ai_chain_radar.scoring.risk_score import RiskScore
from ai_chain_radar.scoring.trading_confirmation_score import TradingConfirmationScore
from ai_chain_radar.settings import load_yaml
from ai_chain_radar.text_normalize import normalize_text


class OpportunityScore:
    def __init__(self) -> None:
        self.global_anchor = GlobalAnchorScore()
        self.bottleneck = BottleneckScore()
        self.mapping = MappingScore()
        self.trading = TradingConfirmationScore()
        self.risk = RiskScore()
        self.rule_engine = CounterEvidenceRuleEngine()

    def run(
        self, repo: Repository, score_date: str, weights_path: str = "configs/scoring_weights.yml"
    ) -> int:
        weights = load_yaml(weights_path)["weights"]
        segments_df = repo.query_dataframe(
            "SELECT segment_id, segment_name FROM ai_chain_segment ORDER BY 1"
        )
        if segments_df.empty:
            return 0

        rows = []
        for _, row in segments_df.iterrows():
            segment = str(row["segment_id"])
            segment_name = str(row["segment_name"])

            ga = self.global_anchor.score(repo, segment, score_date)
            bn = self.bottleneck.score(repo, segment, score_date)
            mp = self.mapping.score(repo, segment, score_date)
            tc = self.trading.score(repo, segment, score_date)
            eop = ga.score * 0.4 + bn.score * 0.3 + mp.score * 0.3
            crowding = max(0.0, min(100.0, tc.score))
            rk = self.risk.score(crowding)

            base_final_score = (
                ga.score * weights["global_anchor_score"]
                + bn.score * weights["bottleneck_score"]
                + eop * weights["earnings_order_price_score"]
                + mp.score * weights["a_share_mapping_score"]
                + tc.score * weights["a_share_confirmation_score"]
                + rk.score * weights["risk_adjustment"] / 100
            )
            metrics = {
                "global_anchor_score": ga.score,
                "bottleneck_score": bn.score,
                "earnings_order_price_score": eop,
                "a_share_mapping_score": mp.score,
                "a_share_confirmation_score": tc.score,
                "crowding_score": crowding,
                "risk_score": rk.score,
                "base_final_score": base_final_score,
                "ga_score": ga.score,
                "bn_score": bn.score,
                "eop_score": eop,
                "mp_score": mp.score,
                "tc_score": tc.score,
            }
            rule_eval = self.rule_engine.evaluate(repo=repo, segment=segment, metrics=metrics)
            adjusted_risk_score = max(0.0, min(100.0, rk.score - rule_eval.total_penalty * 2.0))
            final_score = max(0.0, min(100.0, base_final_score - rule_eval.total_penalty))
            stage = _stage_from_score(final_score)

            evidence = [
                {"source": item.source, "message": item.message}
                for item in [*ga.evidence, *bn.evidence, *mp.evidence, *tc.evidence, *rk.evidence]
            ]
            segment_evidence_refs = _segment_evidence_refs(
                repo=repo,
                segment=segment,
                score_date=score_date,
            )
            evidence.extend(
                segment_evidence_refs
            )
            for hit in rule_eval.hits:
                evidence.append(
                    {
                        "source": "counter_evidence_rule",
                        "message": (
                            f"{hit.rule_id} ({hit.severity}) hit: {hit.condition_expr}; "
                            f"penalty={hit.penalty:.1f}"
                        ),
                    }
                )

            invalid_conditions = [*mp.warnings, *rule_eval.labels]
            confidence_score = _confidence_score(
                ga_score=ga.score,
                bn_score=bn.score,
                mp_score=mp.score,
                tc_score=tc.score,
                segment_evidence_refs=segment_evidence_refs,
                penalty=rule_eval.total_penalty,
            )
            rows.append(
                {
                    "score_date": score_date,
                    "segment": segment,
                    "industry_score": bn.score,
                    "bottleneck_score": bn.score,
                    "global_anchor_score": ga.score,
                    "earnings_order_price_score": eop,
                    "a_share_mapping_score": mp.score,
                    "a_share_confirmation_score": tc.score,
                    "crowding_score": crowding,
                    "risk_score": adjusted_risk_score,
                    "confidence_score": confidence_score,
                    "final_score": final_score,
                    "stage": stage,
                    "conclusion": f"{segment_name} 当前处于 {stage} 阶段",
                    "evidence_json": json.dumps(evidence, ensure_ascii=False),
                    "invalid_conditions_json": json.dumps(invalid_conditions, ensure_ascii=False),
                    "created_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )

        out_df = pd.DataFrame(rows)
        repo.upsert_dataframe("theme_opportunity_score", out_df, keys=["score_date", "segment"])
        return len(out_df)


def _stage_from_score(score: float) -> str:
    if score >= 85:
        return "main_rally"
    if score >= 70:
        return "start"
    if score >= 55:
        return "warming_up"
    if score >= 40:
        return "observe"
    return "not_started"


def _segment_evidence_refs(repo: Repository, segment: str, score_date: str) -> list[dict[str, Any]]:
    df = repo.query_dataframe(
        """
        SELECT
          evidence_id,
          source_name,
          source_type,
          claim,
          evidence_level,
          confidence,
          is_counter_evidence
        FROM evidence_registry
        WHERE evidence_date <= ?
          AND (
            segment = ?
            OR coalesce(segment, '') = ''
          )
        ORDER BY
          CASE WHEN segment = ? THEN 0 ELSE 1 END,
          evidence_date DESC NULLS LAST,
          confidence DESC NULLS LAST
        LIMIT 8
        """,
        [score_date, segment, segment],
    )
    if df.empty:
        return []
    refs: list[dict[str, Any]] = []
    for item in df.itertuples(index=False):
        claim = str(item.claim or "").strip()
        if len(claim) > 120:
            claim = f"{claim[:117]}..."
        claim = normalize_text(claim)
        refs.append(
            {
                "source": str(item.source_name or item.source_type or "evidence_registry"),
                "message": claim,
                "evidence_id": str(item.evidence_id),
                "evidence_level": str(item.evidence_level or ""),
                "is_counter_evidence": bool(item.is_counter_evidence),
            }
        )
    return refs


def _confidence_score(
    *,
    ga_score: float,
    bn_score: float,
    mp_score: float,
    tc_score: float,
    segment_evidence_refs: list[dict[str, Any]],
    penalty: float,
) -> float:
    component_scores = [ga_score, bn_score, mp_score, tc_score]
    data_completeness = sum(1 for score in component_scores if score > 0.0) / len(component_scores)
    ref_count = len(segment_evidence_refs)
    a_level_count = sum(
        1
        for ref in segment_evidence_refs
        if str(ref.get("evidence_level", "")).strip().upper().startswith("A")
    )
    counter_count = sum(
        1 for ref in segment_evidence_refs if bool(ref.get("is_counter_evidence", False))
    )
    base = (
        35.0 * data_completeness
        + 30.0 * min(1.0, ref_count / 6.0)
        + 20.0 * min(1.0, a_level_count / 3.0)
        + 15.0 * (1.0 if counter_count > 0 else 0.4)
    )
    penalty_factor = max(0.0, 1.0 - min(1.0, penalty / 30.0))
    return max(0.0, min(100.0, base * penalty_factor))
