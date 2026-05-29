from __future__ import annotations

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.scoring import EvidenceItem, ScoreOutput


class GlobalAnchorScore:
    def score(self, repo: Repository, segment: str, score_date: str) -> ScoreOutput:
        df = repo.query_dataframe(
            """
            SELECT avg(coalesce(pct_chg, 0)) AS avg_pct
            FROM global_anchor_price_daily AS p
            JOIN global_anchor_security AS s
              ON p.symbol = s.symbol AND p.market = s.market
            WHERE p.trade_date = ? AND s.chain_segment = ?
            """,
            [score_date, segment],
        )
        avg_pct = (
            float(df.iloc[0]["avg_pct"])
            if not df.empty and df.iloc[0]["avg_pct"] is not None
            else 0.0
        )
        score = max(0.0, min(100.0, 50.0 + avg_pct * 8.0))
        return ScoreOutput(
            score=score,
            confidence=70.0 if avg_pct != 0 else 40.0,
            evidence=[
                EvidenceItem(source="global_anchor_price_daily", message=f"avg_pct={avg_pct:.2f}")
            ],
        )
