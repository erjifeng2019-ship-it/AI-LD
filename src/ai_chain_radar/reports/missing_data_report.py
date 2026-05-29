from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_chain_radar.db.repository import Repository


def build_missing_data_report(repo: Repository, report_date: str) -> dict[str, Any]:
    expected_df = repo.query_dataframe(
        """
        SELECT symbol, market, chain_segment
        FROM global_anchor_security
        ORDER BY chain_segment, symbol
        """
    )
    actual_df = repo.query_dataframe(
        """
        SELECT symbol, market
        FROM global_anchor_price_daily
        WHERE trade_date = ?
        """,
        [report_date],
    )
    actual_set = {
        (str(row.symbol), str(row.market)) for row in actual_df.itertuples(index=False)
    }

    missing_anchors: list[dict[str, str]] = []
    for row in expected_df.itertuples(index=False):
        key = (str(row.symbol), str(row.market))
        if key in actual_set:
            continue
        missing_anchors.append(
            {
                "symbol": str(row.symbol),
                "market": str(row.market),
                "segment": str(row.chain_segment or ""),
            }
        )

    latest_runs = repo.query_dataframe(
        """
        SELECT source, status, rows_read, rows_written, started_at
        FROM (
          SELECT
            source, status, rows_read, rows_written, started_at,
            row_number() OVER (PARTITION BY source ORDER BY started_at DESC) AS rn
          FROM source_run_log
        ) t
        WHERE rn = 1
        ORDER BY source
        """
    )
    source_status = latest_runs.to_dict(orient="records")
    payload = {
        "report_date": report_date,
        "expected_anchor_count": int(len(expected_df)),
        "actual_anchor_count": int(len(actual_df)),
        "missing_anchor_count": int(len(missing_anchors)),
        "missing_anchors": missing_anchors[:200],
        "source_status": source_status,
    }
    out_dir = Path("data/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"missing_data_{report_date}.json"
    md_path = out_dir / f"missing_data_{report_date}.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    lines = [
        f"# Missing Data Report - {report_date}",
        "",
        f"- expected_anchor_count: {payload['expected_anchor_count']}",
        f"- actual_anchor_count: {payload['actual_anchor_count']}",
        f"- missing_anchor_count: {payload['missing_anchor_count']}",
        "",
        "## Missing Anchors",
    ]
    if missing_anchors:
        for item in missing_anchors[:50]:
            lines.append(f"- {item['symbol']} ({item['market']}) / {item['segment']}")
    else:
        lines.append("- none")
    lines.extend(["", "## Latest Source Status"])
    if source_status:
        for item in source_status:
            lines.append(
                f"- {item.get('source')}: {item.get('status')} "
                f"(read={item.get('rows_read')}, written={item.get('rows_written')})"
            )
    else:
        lines.append("- no run logs")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload["json_path"] = str(json_path)
    payload["markdown_path"] = str(md_path)
    return payload
