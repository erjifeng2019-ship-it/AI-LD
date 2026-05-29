from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_chain_radar.db.repository import Repository


def export_weekly_report(repo: Repository, end_date: str) -> dict[str, Any]:
    score_df = repo.query_dataframe(
        """
        WITH recent_dates AS (
          SELECT DISTINCT score_date
          FROM theme_opportunity_score
          WHERE score_date <= ?
          ORDER BY score_date DESC
          LIMIT 5
        )
        SELECT
          segment,
          count(*) AS day_count,
          avg(final_score) AS avg_final_score,
          max(final_score) AS max_final_score,
          avg(a_share_confirmation_score) AS avg_confirmation_score,
          avg(crowding_score) AS avg_crowding_score
        FROM theme_opportunity_score
        WHERE score_date IN (SELECT score_date FROM recent_dates)
        GROUP BY segment
        ORDER BY avg_final_score DESC
        """,
        [end_date],
    )
    review_df = repo.query_dataframe(
        """
        WITH recent_dates AS (
          SELECT DISTINCT review_date
          FROM signal_review_summary
          WHERE review_date <= ?
          ORDER BY review_date DESC
          LIMIT 5
        )
        SELECT
          segment,
          avg(precision) AS avg_precision,
          avg(recall) AS avg_recall,
          sum(sample_count) AS sample_count
        FROM signal_review_summary
        WHERE review_date IN (SELECT review_date FROM recent_dates)
        GROUP BY segment
        ORDER BY avg_precision DESC, avg_recall DESC
        """,
        [end_date],
    )

    out_dir = Path("data/reports/weekly")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"weekly_report_{end_date}.md"

    lines = [f"# Weekly Report - {end_date}", ""]
    lines.append("## Segment Score Summary")
    if score_df.empty:
        lines.append("- no score data")
    else:
        lines.append(
            "| segment | day_count | avg_final_score | max_final_score | "
            "avg_confirmation | avg_crowding |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|")
        for row in score_df.itertuples(index=False):
            avg_final = float(row.avg_final_score or 0.0)
            max_final = float(row.max_final_score or 0.0)
            avg_confirm = float(row.avg_confirmation_score or 0.0)
            avg_crowd = float(row.avg_crowding_score or 0.0)
            lines.append(
                f"| {row.segment} | {int(row.day_count or 0)} | {avg_final:.2f} | "
                f"{max_final:.2f} | {avg_confirm:.2f} | {avg_crowd:.2f} |"
            )

    lines.extend(["", "## Review Calibration Snapshot"])
    if review_df.empty:
        lines.append("- no review summary data")
    else:
        lines.append("| segment | avg_precision | avg_recall | sample_count |")
        lines.append("|---|---:|---:|---:|")
        for row in review_df.itertuples(index=False):
            avg_precision = float(row.avg_precision or 0.0)
            avg_recall = float(row.avg_recall or 0.0)
            sample_count = int(row.sample_count or 0)
            lines.append(
                f"| {row.segment} | {avg_precision:.4f} | {avg_recall:.4f} | "
                f"{sample_count} |"
            )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "path": str(out_path),
        "score_rows": int(len(score_df)),
        "review_rows": int(len(review_df)),
    }
