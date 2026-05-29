from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ai_chain_radar.db.repository import Repository


def _briefing_has_review_sections(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    must_have = ["昨日判断复盘", "反证与风险", "明日观察"]
    return all(token in text for token in must_have)


def _ci_first_run_status(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    text = path.read_text(encoding="utf-8")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.lower().startswith("status:"):
            continue
        return line.split(":", 1)[1].strip().upper()
    return "UNKNOWN"


def _ci_first_run_value(path: Path, key: str) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    needle = key.strip().lower() + ":"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.lower().startswith(needle):
            continue
        return line.split(":", 1)[1].strip()
    return ""


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, float) and math.isnan(value):
        return 0
    return int(value)


def export_v02_completion_audit(
    repo: Repository,
    date: str,
    reviewer: str = "Codex",
    include_ci_gate: bool = True,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add_check(
        key: str,
        title: str,
        passed: bool,
        evidence: str,
        required: bool = True,
        note: str = "",
    ) -> None:
        checks.append(
            {
                "key": key,
                "title": title,
                "passed": passed,
                "evidence": evidence,
                "required": required,
                "note": note,
            }
        )

    mapping_version_df = repo.query_dataframe(
        "SELECT count(*) AS c FROM a_share_chain_mapping_version"
    )
    mapping_version_count = _safe_int(mapping_version_df.iloc[0]["c"])
    add_check(
        "mapping_version",
        "映射表已版本化入库",
        mapping_version_count > 0,
        f"a_share_chain_mapping_version rows={mapping_version_count}",
    )

    evidence_df = repo.query_dataframe("SELECT count(*) AS c FROM evidence_registry")
    evidence_count = _safe_int(evidence_df.iloc[0]["c"])
    add_check(
        "evidence_registry",
        "evidence_registry 可查询",
        evidence_count > 0,
        f"evidence_registry rows={evidence_count}",
    )

    coverage_df = repo.query_dataframe(
        """
        WITH core AS (
          SELECT DISTINCT ts_code
          FROM a_share_chain_mapping
          WHERE coalesce(is_core, FALSE) = TRUE
        ),
        covered AS (
          SELECT DISTINCT entity_id AS ts_code
          FROM evidence_registry
          WHERE entity_id IS NOT NULL AND trim(entity_id) <> ''
        )
        SELECT
          (SELECT count(*) FROM core) AS core_cnt,
          (
            SELECT count(*)
            FROM core c
            INNER JOIN covered d ON c.ts_code = d.ts_code
          ) AS covered_cnt
        """
    )
    core_cnt = _safe_int(coverage_df.iloc[0]["core_cnt"])
    covered_cnt = _safe_int(coverage_df.iloc[0]["covered_cnt"])
    coverage_ratio = (covered_cnt / core_cnt) if core_cnt > 0 else 0.0
    add_check(
        "core_pool_coverage",
        "核心池公司具备证据覆盖",
        core_cnt > 0 and coverage_ratio >= 0.8,
        f"core={core_cnt}, covered={covered_cnt}, coverage={coverage_ratio:.2%}",
        note="阈值按 v0.2 收尾阶段采用 80%",
    )

    counter_df = repo.query_dataframe(
        """
        SELECT count(*) AS c
        FROM evidence_registry
        WHERE coalesce(is_counter_evidence, FALSE)=TRUE
        """
    )
    counter_count = _safe_int(counter_df.iloc[0]["c"])
    add_check(
        "counter_evidence",
        "空白/反证项可查询",
        counter_count > 0,
        f"counter_evidence rows={counter_count}",
    )

    tushare_df = repo.query_dataframe(
        """
        SELECT count(*) AS c
        FROM source_run_log
        WHERE source='tushare' AND cast(started_at as date)=cast(? as date)
        """,
        [date],
    )
    tushare_runs = _safe_int(tushare_df.iloc[0]["c"])
    add_check(
        "tushare_runs",
        "Tushare 当日有运行记录",
        tushare_runs > 0,
        f"source_run_log(tushare,{date}) rows={tushare_runs}",
    )

    run_log_df = repo.query_dataframe(
        "SELECT count(*) AS c FROM source_run_log WHERE cast(started_at as date)=cast(? as date)",
        [date],
    )
    run_log_rows = _safe_int(run_log_df.iloc[0]["c"])
    add_check(
        "source_run_log",
        "source_run_log 有当日记录",
        run_log_rows > 0,
        f"source_run_log({date}) rows={run_log_rows}",
    )

    dq_df = repo.query_dataframe(
        """
        SELECT count(*) AS c
        FROM source_run_log
        WHERE source='dq_report'
          AND (
            cast(started_at as date)=cast(? as date)
            OR params_json LIKE ?
          )
        """,
        [date, f'%\"date\": \"{date}\"%'],
    )
    dq_rows = _safe_int(dq_df.iloc[0]["c"])
    add_check(
        "dq_report",
        "data_quality_report 流程已执行",
        dq_rows > 0,
        f"dq_report run rows={dq_rows}",
    )

    score_df = repo.query_dataframe(
        "SELECT count(*) AS c FROM theme_opportunity_score WHERE score_date=cast(? as date)",
        [date],
    )
    score_rows = _safe_int(score_df.iloc[0]["c"])
    add_check(
        "five_segments_scored",
        "五条主线可评分",
        score_rows >= 5,
        f"theme_opportunity_score({date}) rows={score_rows}",
    )

    stage_df = repo.query_dataframe(
        """
        SELECT
          count(*) AS total_cnt,
          sum(CASE WHEN stage IS NOT NULL AND trim(stage)<>'' THEN 1 ELSE 0 END) AS stage_cnt
        FROM theme_opportunity_score
        WHERE score_date=cast(? as date)
        """,
        [date],
    )
    total_cnt = _safe_int(stage_df.iloc[0]["total_cnt"])
    stage_cnt = _safe_int(stage_df.iloc[0]["stage_cnt"])
    add_check(
        "stage_present",
        "每条主线有 stage",
        total_cnt > 0 and stage_cnt == total_cnt,
        f"stage_present={stage_cnt}/{total_cnt}",
    )

    seg_evidence_df = repo.query_dataframe(
        """
        WITH scored AS (
          SELECT DISTINCT segment
          FROM theme_opportunity_score
          WHERE score_date=cast(? as date)
        ),
        pos AS (
          SELECT segment, count(*) AS c
          FROM evidence_registry
          WHERE coalesce(is_counter_evidence, FALSE)=FALSE
          GROUP BY segment
        ),
        neg AS (
          SELECT segment, count(*) AS c
          FROM evidence_registry
          WHERE coalesce(is_counter_evidence, FALSE)=TRUE
          GROUP BY segment
        )
        SELECT
          count(*) AS seg_cnt,
          sum(CASE WHEN coalesce(p.c,0)>0 THEN 1 ELSE 0 END) AS seg_with_pos,
          sum(CASE WHEN coalesce(n.c,0)>0 THEN 1 ELSE 0 END) AS seg_with_neg
        FROM scored s
        LEFT JOIN pos p ON s.segment=p.segment
        LEFT JOIN neg n ON s.segment=n.segment
        """,
        [date],
    )
    seg_cnt = _safe_int(seg_evidence_df.iloc[0]["seg_cnt"])
    seg_pos = _safe_int(seg_evidence_df.iloc[0]["seg_with_pos"])
    seg_neg = _safe_int(seg_evidence_df.iloc[0]["seg_with_neg"])
    add_check(
        "segment_pos_neg_evidence",
        "每条主线有正证据与反证维度",
        seg_cnt > 0 and seg_pos == seg_cnt and seg_neg >= max(1, int(seg_cnt * 0.6)),
        f"segments={seg_cnt}, with_positive={seg_pos}, with_counter={seg_neg}",
        note="反证覆盖阈值按 v0.2 收尾阶段采用 60%",
    )

    confidence_df = repo.query_dataframe(
        """
        SELECT
          count(*) AS total_cnt,
          sum(CASE WHEN confidence_score IS NOT NULL THEN 1 ELSE 0 END) AS conf_cnt
        FROM theme_opportunity_score
        WHERE score_date=cast(? as date)
        """,
        [date],
    )
    conf_total = _safe_int(confidence_df.iloc[0]["total_cnt"])
    conf_cnt = _safe_int(confidence_df.iloc[0]["conf_cnt"])
    add_check(
        "confidence_score",
        "每条主线有 confidence_score",
        conf_total > 0 and conf_cnt == conf_total,
        f"theme_opportunity_score confidence={conf_cnt}/{conf_total}",
    )

    briefing_path = Path("data/briefings") / f"{date}.md"
    briefing_exists = briefing_path.exists()
    add_check(
        "briefing_generated",
        "Markdown 日报可生成",
        briefing_exists,
        f"briefing_path={briefing_path.as_posix()}",
    )
    add_check(
        "briefing_sections",
        "日报包含复盘/反证/观察模块",
        _briefing_has_review_sections(briefing_path),
        "required sections: 昨日判断复盘, 反证与风险, 明日观察",
    )

    review_df = repo.query_dataframe(
        "SELECT count(*) AS c FROM signal_review_result WHERE review_date=cast(? as date)",
        [date],
    )
    review_rows = _safe_int(review_df.iloc[0]["c"])
    add_check(
        "review_rows",
        "review 命令有当日产出",
        review_rows > 0,
        f"signal_review_result({date}) rows={review_rows}",
    )

    if include_ci_gate:
        ci_doc = Path("docs") / "CI_FIRST_RUN.md"
        ci_status = _ci_first_run_status(ci_doc)
        ci_run_id = _ci_first_run_value(ci_doc, "- run_id")
        ci_workflow_url = _ci_first_run_value(ci_doc, "- workflow_url")
        ci_has_evidence = bool(ci_run_id) and bool(ci_workflow_url)
        add_check(
            "ci_first_run",
            "首轮 CI 真网验收留痕",
            ci_status == "PASS" and ci_has_evidence,
            (
                f"{ci_doc.as_posix()} status={ci_status}, "
                f"run_id={'present' if ci_run_id else 'missing'}, "
                f"workflow_url={'present' if ci_workflow_url else 'missing'}"
            ),
            note="外部依赖：需在 GitHub Actions 执行 workflow_dispatch 后回填",
        )

    required_checks = [c for c in checks if c["required"]]
    passed_required = [c for c in required_checks if c["passed"]]
    overall_pass = len(required_checks) == len(passed_required)

    lines: list[str] = []
    lines.append(f"# V0.2_COMPLETION_AUDIT_{date}")
    lines.append("")
    lines.append("- generated_by: export v02-audit")
    lines.append(f"- reviewer: {reviewer}")
    lines.append(f"- business_date: {date}")
    lines.append("")
    lines.append("## Checklist")
    lines.append("")
    lines.append("| key | item | status | evidence | note |")
    lines.append("|---|---|---|---|---|")
    for item in checks:
        status = "PASS" if item["passed"] else "FAIL"
        evidence = str(item["evidence"]).replace("|", "\\|")
        note = str(item["note"]).replace("|", "\\|")
        lines.append(
            f"| {item['key']} | {item['title']} | {status} | {evidence} | {note} |"
        )

    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- required_pass: {len(passed_required)}/{len(required_checks)} "
        f"({'PASS' if overall_pass else 'PARTIAL'})"
    )
    if not overall_pass:
        failed_keys = [item["key"] for item in required_checks if not item["passed"]]
        lines.append(f"- failed_items: {', '.join(failed_keys)}")
    lines.append("- note: CI 首轮留痕依赖外部仓库权限与 secrets。")

    out_path = Path("docs") / f"V0_2_COMPLETION_AUDIT_{date}.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "path": str(out_path),
        "overall_pass": overall_pass,
        "required_total": len(required_checks),
        "required_passed": len(passed_required),
        "checks": checks,
    }
