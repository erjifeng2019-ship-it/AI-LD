from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pandas as pd

from ai_chain_radar.db.repository import Repository


def build_data_quality_report(repo: Repository, report_date: str) -> int:
    df = repo.query_dataframe(
        """
        SELECT source, job_name, status, rows_read, rows_written
        FROM source_run_log
        WHERE cast(started_at AS DATE) = ?
        QUALIFY row_number() OVER (PARTITION BY source, job_name ORDER BY started_at DESC) = 1
        ORDER BY source, job_name
        """,
        [report_date],
    )
    if df.empty:
        return 0

    now = datetime.now(UTC).replace(tzinfo=None)
    rows: list[dict] = []
    for row in df.itertuples(index=False):
        rows.append(
            {
                "report_id": f"dq_{report_date}_{uuid4().hex[:12]}",
                "report_date": report_date,
                "source": row.source,
                "job_name": row.job_name,
                "status": row.status,
                "rows_read": int(row.rows_read or 0),
                "rows_written": int(row.rows_written or 0),
                "note": _status_note(str(row.status)),
                "created_at": now,
            }
        )

    out_df = pd.DataFrame(rows)
    return repo.upsert_dataframe("data_quality_report", out_df, keys=["report_id"])


def _status_note(status: str) -> str:
    if status == "ok":
        return "data synchronized"
    if status == "empty":
        return "no rows returned under current filters"
    if status == "missing_credentials":
        return "credentials required"
    if status == "failed":
        return "job failed, inspect source_run_log.error_message"
    return "status recorded"

