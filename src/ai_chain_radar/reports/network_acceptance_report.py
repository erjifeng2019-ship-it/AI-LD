from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.settings import get_settings


def export_network_acceptance_report(
    repo: Repository,
    acceptance_date: str,
    target_date: str | None = None,
    reviewer: str = "Codex",
    ui_url: str = "http://127.0.0.1:8000/ui",
    ui_screenshot_path: str = "",
    max_log_rows: int = 60,
) -> dict[str, Any]:
    business_date = (target_date or acceptance_date).strip()
    settings = get_settings()
    credential_availability = {
        "TUSHARE_TOKEN": bool(settings.tushare_token.strip()),
        "FINMIND_TOKEN": bool(settings.finmind_token.strip()),
        "SEC_USER_AGENT": bool(settings.sec_user_agent.strip()),
        "OPENDART_API_KEY": bool(settings.opendart_api_key.strip()),
    }

    latest_source_df = repo.query_dataframe(
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
    latest_source_rows = latest_source_df.to_dict(orient="records")

    run_rows_df = repo.query_dataframe(
        """
        SELECT source, job_name, status, rows_read, rows_written, started_at, params_json
        FROM source_run_log
        WHERE cast(started_at as date) = cast(? as date)
        ORDER BY started_at ASC, source ASC, job_name ASC
        """,
        [acceptance_date],
    )
    run_rows = run_rows_df.to_dict(orient="records")

    if run_rows_df.empty:
        run_rows_df = repo.query_dataframe(
            """
            SELECT source, job_name, status, rows_read, rows_written, started_at, params_json
            FROM source_run_log
            ORDER BY started_at DESC
            LIMIT 50
            """
        )
        run_rows = list(reversed(run_rows_df.to_dict(orient="records")))

    total_run_rows = len(run_rows)
    if max_log_rows > 0 and total_run_rows > max_log_rows:
        run_rows = run_rows[-max_log_rows:]

    review_df = repo.query_dataframe(
        """
        SELECT
          count(*) AS cnt,
          avg(precision) AS avg_precision,
          avg(recall) AS avg_recall
        FROM signal_review_summary
        WHERE review_date = ?
        """,
        [business_date],
    )
    review_count = (
        int(review_df.iloc[0]["cnt"])
        if not review_df.empty and review_df.iloc[0]["cnt"]
        else 0
    )
    review_precision = (
        float(review_df.iloc[0]["avg_precision"])
        if not review_df.empty and review_df.iloc[0]["avg_precision"] is not None
        else None
    )
    review_recall = (
        float(review_df.iloc[0]["avg_recall"])
        if not review_df.empty and review_df.iloc[0]["avg_recall"] is not None
        else None
    )

    score_df = repo.query_dataframe(
        "SELECT count(*) AS cnt FROM theme_opportunity_score WHERE score_date = ?",
        [business_date],
    )
    score_count = (
        int(score_df.iloc[0]["cnt"])
        if not score_df.empty and score_df.iloc[0]["cnt"]
        else 0
    )

    briefing_path = Path("data/briefings") / f"{business_date}.md"
    has_briefing = briefing_path.exists()

    required_sources = {"tushare", "finmind", "sec", "opendart"}
    latest_status_by_source = {
        str(item.get("source", "")): str(item.get("status", "")) for item in latest_source_rows
    }
    source_eval: list[dict[str, str]] = []
    overall_pass = True
    for src in sorted(required_sources):
        key_map = {
            "tushare": "TUSHARE_TOKEN",
            "finmind": "FINMIND_TOKEN",
            "sec": "SEC_USER_AGENT",
            "opendart": "OPENDART_API_KEY",
        }
        cred_key = key_map[src]
        has_cred = credential_availability[cred_key]
        status = latest_status_by_source.get(src, "missing")
        if not has_cred:
            evaluation = "acceptable_missing_credentials"
        else:
            evaluation = "pass" if status in {"ok", "empty", "partial", "skipped"} else "fail"
        if evaluation == "fail":
            overall_pass = False
        source_eval.append(
            {
                "source": src,
                "credential": "available" if has_cred else "missing",
                "latest_status": status,
                "evaluation": evaluation,
            }
        )

    if score_count <= 0 or not has_briefing:
        overall_pass = False

    lines: list[str] = []
    lines.append(f"# NETWORK_ACCEPTANCE_{acceptance_date}")
    lines.append("")
    lines.append("基于 source_run_log 与当前仓库产物的自动化验收记录。")
    lines.append("")
    lines.append("## 验收信息")
    lines.append("")
    lines.append(f"- 验收日期: {acceptance_date}")
    lines.append(f"- 业务日期: {business_date}")
    lines.append(f"- 验收人: {reviewer}")
    lines.append("- 环境:")
    lines.append(f"  - Python: {sys.version.split()[0]}")
    lines.append(f"  - OS: {platform.platform()}")
    lines.append(f"  - AI_CHAIN_ENV: {settings.ai_chain_env}")
    lines.append("")
    lines.append("## 凭据可用性")
    for key, available in credential_availability.items():
        lines.append(f"- {key}: {'available' if available else 'missing'}")
    lines.append("")
    lines.append("## Source 完成态判断")
    for item in source_eval:
        lines.append(
            "- "
            f"{item['source']}: credential={item['credential']}, "
            f"latest_status={item['latest_status']}, evaluation={item['evaluation']}"
        )
    lines.append("")
    lines.append("## 命令执行记录（按验收日期）")
    if total_run_rows > len(run_rows):
        lines.append(
            f"- note: total rows={total_run_rows}, showing latest {len(run_rows)} rows only."
        )
    if not run_rows:
        lines.append("- no source_run_log rows")
    else:
        for idx, row in enumerate(run_rows, start=1):
            params_text = str(row.get("params_json", "")).strip()
            if len(params_text) > 240:
                params_text = f"{params_text[:237]}..."
            lines.append(
                f"{idx}. `{row.get('source')}/{row.get('job_name')}` "
                f"status={row.get('status')} read={row.get('rows_read')} "
                f"written={row.get('rows_written')} started_at={row.get('started_at')}"
            )
            if params_text:
                lines.append(f"   - params: `{params_text}`")
    lines.append("")
    lines.append("## 关键证据")
    lines.append(f"- theme_opportunity_score rows ({business_date}): {score_count}")
    if review_count > 0:
        lines.append(
            "- signal_review_summary "
            f"({business_date}): cnt={review_count}, "
            f"avg_precision={review_precision:.4f}, avg_recall={review_recall:.4f}"
        )
    else:
        lines.append(f"- signal_review_summary ({business_date}): cnt=0")
    lines.append(
        f"- briefing file: {'exists' if has_briefing else 'missing'} "
        f"({briefing_path.as_posix()})"
    )
    lines.append(f"- UI URL: {ui_url}")
    if ui_screenshot_path.strip():
        lines.append(f"- UI screenshot: {ui_screenshot_path.strip()}")
    lines.append("")
    lines.append("## 结论")
    lines.append(f"- 完成态判定: {'通过' if overall_pass else '部分通过/需复核'}")
    if overall_pass:
        lines.append("- 说明: 可用凭据源已通过或可接受降级，评分与简报产物存在。")
    else:
        lines.append("- 说明: 存在失败源或关键产物缺失，请按 source_run_log 与产物检查。")

    out_path = Path("docs") / f"NETWORK_ACCEPTANCE_{acceptance_date}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "path": str(out_path),
        "overall_pass": overall_pass,
        "score_count": score_count,
        "review_count": review_count,
        "has_briefing": has_briefing,
        "source_eval": source_eval,
    }
