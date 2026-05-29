# V0.2_COMPLETION_AUDIT_2026-05-28

- generated_by: export v02-audit
- reviewer: Codex
- business_date: 2026-05-28

## Checklist

| key | item | status | evidence | note |
|---|---|---|---|---|
| mapping_version | 映射表已版本化入库 | PASS | a_share_chain_mapping_version rows=1 |  |
| evidence_registry | evidence_registry 可查询 | PASS | evidence_registry rows=20617 |  |
| core_pool_coverage | 核心池公司具备证据覆盖 | PASS | core=29, covered=29, coverage=100.00% | 阈值按 v0.2 收尾阶段采用 80% |
| counter_evidence | 空白/反证项可查询 | PASS | counter_evidence rows=53 |  |
| tushare_runs | Tushare 当日有运行记录 | PASS | source_run_log(tushare,2026-05-28) rows=187 |  |
| source_run_log | source_run_log 有当日记录 | PASS | source_run_log(2026-05-28) rows=228 |  |
| dq_report | data_quality_report 流程已执行 | PASS | dq_report run rows=21 |  |
| five_segments_scored | 五条主线可评分 | PASS | theme_opportunity_score(2026-05-28) rows=5 |  |
| stage_present | 每条主线有 stage | PASS | stage_present=5/5 |  |
| segment_pos_neg_evidence | 每条主线有正证据与反证维度 | PASS | segments=5, with_positive=5, with_counter=5 | 反证覆盖阈值按 v0.2 收尾阶段采用 60% |
| confidence_score | 每条主线有 confidence_score | PASS | theme_opportunity_score confidence=5/5 |  |
| briefing_generated | Markdown 日报可生成 | PASS | briefing_path=data/briefings/2026-05-28.md |  |
| briefing_sections | 日报包含复盘/反证/观察模块 | PASS | required sections: 昨日判断复盘, 反证与风险, 明日观察 |  |
| review_rows | review 命令有当日产出 | PASS | signal_review_result(2026-05-28) rows=95 |  |
| ci_first_run | 首轮 CI 真网验收留痕 | PASS | docs/CI_FIRST_RUN.md status=PASS, run_id=present, workflow_url=present | 外部依赖：需在 GitHub Actions 执行 workflow_dispatch 后回填 |

## Summary

- required_pass: 15/15 (PASS)
- note: CI 首轮留痕依赖外部仓库权限与 secrets。
