from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_chain_radar.db.repository import Repository


def export_scoring_calibration(
    repo: Repository, window: int = 60, end_date: str | None = None
) -> dict[str, Any]:
    if end_date:
        date_filter_sql = "WHERE review_date <= ?"
        params: list[Any] = [end_date, max(1, window)]
    else:
        date_filter_sql = ""
        params = [max(1, window)]

    summary_df = repo.query_dataframe(
        f"""
        WITH recent_dates AS (
          SELECT DISTINCT review_date
          FROM signal_review_summary
          {date_filter_sql}
          ORDER BY review_date DESC
          LIMIT ?
        )
        SELECT
          segment,
          count(*) AS day_count,
          sum(sample_count) AS sample_count,
          avg(precision) AS avg_precision,
          avg(recall) AS avg_recall,
          avg(avg_forward_return_3d) AS avg_forward_return_3d,
          avg(avg_forward_return_10d) AS avg_forward_return_10d
        FROM signal_review_summary
        WHERE review_date IN (SELECT review_date FROM recent_dates)
        GROUP BY segment
        ORDER BY avg_precision DESC, avg_recall DESC, sample_count DESC
        """,
        params,
    )
    if summary_df.empty:
        return {"rows": 0, "path": "", "end_date": end_date or ""}

    latest_df = repo.query_dataframe(
        "SELECT max(review_date) AS review_date FROM signal_review_summary"
    )
    resolved_end_date = (
        end_date
        or (
            str(latest_df.iloc[0]["review_date"])
            if not latest_df.empty and latest_df.iloc[0]["review_date"] is not None
            else "latest"
        )
    )
    safe_end_date = resolved_end_date.split(" ")[0].replace(":", "-")
    out_dir = Path("data/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"calibration_scoring_{safe_end_date}.md"

    lines = [
        f"# Scoring Calibration Report - {resolved_end_date}",
        "",
        f"- window_days: {max(1, window)}",
        f"- segment_count: {len(summary_df)}",
        "",
        "| segment | day_count | sample_count | avg_precision | avg_recall | "
        "avg_ret_3d | avg_ret_10d |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_df.itertuples(index=False):
        avg_precision = float(row.avg_precision or 0.0)
        avg_recall = float(row.avg_recall or 0.0)
        avg_ret_3d = float(row.avg_forward_return_3d or 0.0)
        avg_ret_10d = float(row.avg_forward_return_10d or 0.0)
        lines.append(
            f"| {row.segment} | {int(row.day_count or 0)} | {int(row.sample_count or 0)} | "
            f"{avg_precision:.4f} | {avg_recall:.4f} | {avg_ret_3d:.4f} | {avg_ret_10d:.4f} |"
        )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"rows": int(len(summary_df)), "path": str(out_path), "end_date": safe_end_date}
