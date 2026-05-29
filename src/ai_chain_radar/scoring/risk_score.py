from __future__ import annotations

from ai_chain_radar.features.crowding import crowding_bucket
from ai_chain_radar.scoring import EvidenceItem, ScoreOutput


class RiskScore:
    def score(self, crowding_raw: float) -> ScoreOutput:
        bucket = crowding_bucket(crowding_raw)
        adj = {"low": 5.0, "medium": 0.0, "high": -8.0, "extreme": -15.0}[bucket]
        mapped = max(0.0, min(100.0, 50.0 + adj * 2))
        return ScoreOutput(
            score=mapped,
            confidence=60.0,
            evidence=[
                EvidenceItem(source="crowding", message=f"bucket={bucket}, adjustment={adj}")
            ],
        )
