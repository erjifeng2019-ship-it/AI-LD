from __future__ import annotations

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.scoring import EvidenceItem, ScoreOutput


class BottleneckScore:
    def score(self, repo: Repository, segment: str, score_date: str) -> ScoreOutput:
        df = repo.query_dataframe(
            """
            SELECT count(*) AS cnt
            FROM us_sec_filing_event
            WHERE filing_date = ?
              AND impact_segments LIKE ?
            """,
            [score_date, f"%{segment}%"],
        )
        cnt = int(df.iloc[0]["cnt"]) if not df.empty else 0
        score = max(0.0, min(100.0, 45.0 + cnt * 6.0))
        return ScoreOutput(
            score=score,
            confidence=65.0 if cnt > 0 else 35.0,
            evidence=[EvidenceItem(source="us_sec_filing_event", message=f"filing_hits={cnt}")],
        )
