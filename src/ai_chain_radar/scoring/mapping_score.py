from __future__ import annotations

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.scoring import EvidenceItem, ScoreOutput


class MappingScore:
    def score(self, repo: Repository, segment: str, score_date: str) -> ScoreOutput:
        df = repo.query_dataframe(
            """
            SELECT
              count(*) AS cnt,
              avg(
                CASE purity_level
                  WHEN 'high' THEN 90
                  WHEN 'medium' THEN 70
                  WHEN 'low' THEN 50
                  WHEN 'concept' THEN 35
                  ELSE 20
                END
              ) AS purity
            FROM a_share_chain_mapping
            WHERE segment = ?
            """,
            [segment],
        )
        cnt = int(df.iloc[0]["cnt"]) if not df.empty else 0
        purity = (
            float(df.iloc[0]["purity"])
            if not df.empty and df.iloc[0]["purity"] is not None
            else 30.0
        )
        score = max(0.0, min(100.0, purity))
        return ScoreOutput(
            score=score,
            confidence=80.0 if cnt > 0 else 30.0,
            evidence=[EvidenceItem(source="a_share_chain_mapping", message=f"symbol_count={cnt}")],
            warnings=[] if cnt > 0 else ["缺少A股映射样本，置信度下降"],
        )
