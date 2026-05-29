from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pandas as pd

from ai_chain_radar.db.repository import Repository


@dataclass
class ManualEvidenceInput:
    claim: str
    segment: str
    sub_segment: str = ""
    evidence_level: str = "C"
    entity_id: str = ""
    entity_name: str = ""
    source_name: str = "manual"
    source_url: str = ""
    is_positive: bool = True
    notes: str = ""


class EvidenceRegistry:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    def list_latest(self, limit: int = 50, segment: str | None = None) -> pd.DataFrame:
        safe_limit = max(1, min(limit, 500))
        if segment:
            return self.repo.query_dataframe(
                """
                SELECT *
                FROM evidence_registry
                WHERE segment = ?
                ORDER BY evidence_date DESC NULLS LAST, ingested_at DESC
                LIMIT ?
                """,
                [segment, safe_limit],
            )
        return self.repo.query_dataframe(
            """
            SELECT *
            FROM evidence_registry
            ORDER BY evidence_date DESC NULLS LAST, ingested_at DESC
            LIMIT ?
            """,
            [safe_limit],
        )

    def add_manual(self, item: ManualEvidenceInput) -> str:
        now = datetime.now(UTC).replace(tzinfo=None)
        evidence_id = f"manual_{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        df = pd.DataFrame(
            [
                {
                    "evidence_id": evidence_id,
                    "evidence_date": now.date().isoformat(),
                    "source_type": "manual_note",
                    "source_name": item.source_name,
                    "source_url": item.source_url,
                    "source_file": "",
                    "source_title": "manual_note",
                    "entity_type": "a_share",
                    "entity_id": item.entity_id,
                    "entity_name": item.entity_name,
                    "segment": item.segment,
                    "sub_segment": item.sub_segment,
                    "evidence_level": item.evidence_level,
                    "claim": item.claim,
                    "excerpt": item.claim,
                    "numeric_value": None,
                    "numeric_unit": "",
                    "confidence": 0.6,
                    "is_positive": item.is_positive,
                    "is_counter_evidence": not item.is_positive,
                    "ingested_at": now,
                    "verified_by": "manual",
                    "notes": item.notes,
                }
            ]
        )
        self.repo.upsert_dataframe("evidence_registry", df, keys=["evidence_id"])
        return evidence_id

