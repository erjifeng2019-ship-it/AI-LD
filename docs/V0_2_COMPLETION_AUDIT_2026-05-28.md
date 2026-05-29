# V0.2_COMPLETION_AUDIT_2026-05-28

- generated_by: export v02-audit
- reviewer: test
- business_date: 2026-05-28

## Checklist

| key | item | status | evidence | note |
|---|---|---|---|---|
| mapping_version | 映射表已版本化入库 | FAIL | a_share_chain_mapping_version rows=0 |  |
| evidence_registry | evidence_registry 可查询 | FAIL | evidence_registry rows=0 |  |
| core_pool_coverage | 核心池公司具备证据覆盖 | FAIL | core=0, covered=0, coverage=0.00% | 阈值按 v0.2 收尾阶段采用 80% |
| counter_evidence | 空白/反证项可查询 | FAIL | counter_evidence rows=0 |  |
| tushare_runs | Tushare 当日有运行记录 | FAIL | source_run_log(tushare,2026-05-28) rows=0 |  |
| source_run_log | source_run_log 有当日记录 | FAIL | source_run_log(2026-05-28) rows=0 |  |
| dq_report | data_quality_report 流程已执行 | FAIL | dq_report run rows=0 |  |
| five_segments_scored | 五条主线可评分 | FAIL | theme_opportunity_score(2026-05-28) rows=0 |  |
| stage_present | 每条主线有 stage | FAIL | stage_present=0/0 |  |
| segment_pos_neg_evidence | 每条主线有正证据与反证维度 | FAIL | segments=0, with_positive=0, with_counter=0 | 反证覆盖阈值按 v0.2 收尾阶段采用 60% |
| confidence_score | 每条主线有 confidence_score | FAIL | theme_opportunity_score confidence=0/0 |  |
| briefing_generated | Markdown 日报可生成 | PASS | briefing_path=data/briefings/2026-05-28.md |  |
| briefing_sections | 日报包含复盘/反证/观察模块 | PASS | required sections: 昨日判断复盘, 反证与风险, 明日观察 |  |
| review_rows | review 命令有当日产出 | FAIL | signal_review_result(2026-05-28) rows=0 |  |

## Summary

- required_pass: 2/14 (PARTIAL)
- failed_items: mapping_version, evidence_registry, core_pool_coverage, counter_evidence, tushare_runs, source_run_log, dq_report, five_segments_scored, stage_present, segment_pos_neg_evidence, confidence_score, review_rows
- note: CI 首轮留痕依赖外部仓库权限与 secrets。
