from __future__ import annotations

import pandas as pd

from ai_chain_radar.db.repository import Repository


def list_segments(repo: Repository) -> pd.DataFrame:
    return repo.query_dataframe(
        """
        SELECT segment_id, segment_name, parent_segment, cycle_stage, key_global_anchors
        FROM ai_chain_segment
        ORDER BY segment_id
        """
    )
