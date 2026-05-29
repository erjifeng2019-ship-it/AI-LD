from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pandas as pd

from ai_chain_radar.db.repository import Repository


def build_review_summary(repo: Repository, review_date: str) -> int:
    detail = repo.query_dataframe(
        """
        SELECT
          segment,
          original_score,
          was_confirmed,
          was_false_positive,
          was_false_negative,
          forward_return_3d,
          forward_return_10d
        FROM signal_review_result
        WHERE review_date = ?
        """,
        [review_date],
    )
    if detail.empty:
        return 0

    detail["predicted_positive"] = detail["original_score"] >= 70.0
    detail["actual_positive"] = detail["was_confirmed"].fillna(False)

    rows: list[dict] = []
    now = datetime.now(UTC).replace(tzinfo=None)
    for seg, seg_df in detail.groupby("segment"):
        tp = int(((seg_df["predicted_positive"]) & (seg_df["actual_positive"])).sum())
        fp = int(((seg_df["predicted_positive"]) & (~seg_df["actual_positive"])).sum())
        fn = int((~seg_df["predicted_positive"] & (seg_df["actual_positive"])).sum())
        precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        rows.append(
            {
                "summary_id": f"rvs_{uuid4().hex[:12]}",
                "review_date": review_date,
                "segment": seg,
                "sample_count": int(len(seg_df)),
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
                "precision": precision,
                "recall": recall,
                "avg_forward_return_3d": float(seg_df["forward_return_3d"].mean()),
                "avg_forward_return_10d": float(seg_df["forward_return_10d"].mean()),
                "created_at": now,
            }
        )
    out_df = pd.DataFrame(rows)
    return repo.upsert_dataframe("signal_review_summary", out_df, keys=["summary_id"])

