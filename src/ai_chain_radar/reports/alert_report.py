from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_chain_radar.db.repository import Repository


def build_alert_report(repo: Repository, report_date: str) -> dict[str, Any]:
    scores = repo.query_dataframe(
        """
        SELECT
          segment,
          final_score,
          a_share_confirmation_score,
          crowding_score,
          invalid_conditions_json
        FROM theme_opportunity_score
        WHERE score_date = ?
        ORDER BY final_score DESC
        """,
        [report_date],
    )
    alerts: list[dict[str, Any]] = []
    for row in scores.itertuples(index=False):
        segment = str(row.segment)
        final_score = float(row.final_score or 0.0)
        confirm_score = float(row.a_share_confirmation_score or 0.0)
        crowding = float(row.crowding_score or 0.0)
        if final_score >= 70 and confirm_score < 45:
            alerts.append(
                {
                    "segment": segment,
                    "level": "high",
                    "type": "unconfirmed_rally",
                    "message": (
                        f"{segment}: final_score={final_score:.2f}, "
                        f"confirmation={confirm_score:.2f}"
                    ),
                }
            )
        if crowding >= 85:
            alerts.append(
                {
                    "segment": segment,
                    "level": "high",
                    "type": "crowding",
                    "message": f"{segment}: crowding_score={crowding:.2f}",
                }
            )
        raw_invalid = str(row.invalid_conditions_json or "").strip()
        if raw_invalid and raw_invalid not in {"[]", "{}"}:
            try:
                parsed = json.loads(raw_invalid)
            except json.JSONDecodeError:
                parsed = [raw_invalid]
            if isinstance(parsed, list):
                for item in parsed[:3]:
                    text = str(item).strip()
                    if text:
                        alerts.append(
                            {
                                "segment": segment,
                                "level": "medium",
                                "type": "counter_evidence",
                                "message": text,
                            }
                        )

    out_dir = Path("data/alerts")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{report_date}.md"
    lines = [f"# Alerts - {report_date}", ""]
    if not alerts:
        lines.append("- no alerts")
    else:
        for item in alerts:
            lines.append(
                f"- [{item['level']}] {item['segment']} / {item['type']}: {item['message']}"
            )
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"alert_count": len(alerts), "path": str(out_path)}
