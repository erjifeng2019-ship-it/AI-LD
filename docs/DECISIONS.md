# DECISIONS

## 2026-05-28
1. MVP 数据库继续使用 DuckDB，不引入 ORM，优先可读可调试 SQL。
2. 所有 source adapter 均先落 raw，再 normalize 入库；每次运行统一写 `source_run_log`。
3. 高重复数据（如 `top_inst`）采用“入库前按主键聚合去重 + upsert”。
4. Tushare 默认 cache-first，支持 `--no-prefer-cache` 强制真网刷新。
5. SEC `companyfacts` 与 OpenDART `corp_code` 先走最小结构化闭环。

## 2026-05-29
1. 收尾阶段保持 CLI/FastAPI 契约稳定，不引入公开 API 破坏性变化。
2. `/ui` 由服务端注入运行状态（latest run log + credential availability）以解释空数据原因。
3. `run_all.ps1` 作为主串行编排入口，输出凭据可用性与 source 状态摘要。
4. 落地 `mapping_importer` / `evidence_registry` / `signal_review_*`，打通“导入 -> 证据 -> 评分 -> 复盘”。
5. 评分链路接入 `counter_evidence_rule`，命中后写 `invalid_conditions_json` 并惩罚风险分与总分。
6. 日报与评分结果引入 `evidence_id` 引用，形成可追溯证据链。
7. 交易确认评分支持 `--intraday`。
8. CLI 对齐 v0.2 workflow 形态：`events-only`、`realtime`、`score market-confirmation`、`score global-anchors`、`brief --mode premarket`。
9. API 常驻下 DuckDB 锁冲突收敛为“请求级短连接 + 显式关闭”，并提供单实例启动脚本。
10. 新增自动验收归档：
   - `export network-acceptance`
   - `--max-log-rows` 控制日志体积
11. `integration-optional` workflow 升级为“integration + 可选 pipeline + 自动验收导出 + artifact 上传 + workflow summary”闭环。
12. 新增 `scripts/run_ci_acceptance.sh` 统一 CI 端验收编排，单个 source 失败不阻断验收汇总。
13. DuckDB 锁争用治理策略更新为：API 读连接默认 `read_only`，数据库连接加入短时重试（`AI_CHAIN_DB_OPEN_RETRY_SECONDS`），`run_all.ps1` 增加 API 预检与 `-StopApiBeforeRun` 选项。
14. 评分结果新增 `confidence_score` 字段并入库到 `theme_opportunity_score`，用于 v0.2 完成态验收与风险沟通。
15. evidence 抽取阶段新增主线归一规则（中文环节 -> 五条主线 `segment_id`），确保正反证据可按主线统计。
16. 新增 `export v02-audit` 自动化完成审计，CI 首轮 gate 以 `docs/CI_FIRST_RUN.md` 的 `status: PASS` 为准。
17. 新增 `scripts/close_v02.ps1` 作为 v0.2 收尾统一入口，默认执行本地闭环并可选触发 CI 首轮留痕。
18. `scripts/ci_first_run_dispatch.ps1` 支持 `GH_TOKEN` 无交互认证，未认证场景必须回填 `CI_FIRST_RUN.md` 的阻塞说明，避免误判为已触发。
19. 修复 `close_v02.ps1` 传参策略：从字符串数组切换为命名参数哈希表 splat，避免 `RunPipeline` 出现布尔参数类型转换异常。
20. API 进程预检输出升级为 `process_trees + raw_processes`，用于区分“单实例双进程（launcher+child）”与真实多实例占用。
21. `close_v02.ps1` 增加原生命令退出码检查，收尾链路改为失败即停，防止验收产物在中间步骤失败时被误当作成功。
22. `close_v02.ps1` 内部参数命名避开 PowerShell 自动变量冲突，避免 Python 命令在极端情况下落入交互模式。
23. `ci_first_run_dispatch.ps1` 与主流程一致：自动加载仓库根目录 `.env`（仅填充当前进程缺失变量），以支持 `GH_TOKEN/GITHUB_REPOSITORY` 的无交互触发。
24. `v02-audit` 的 CI gate 收紧为“双条件”：`CI_FIRST_RUN.md` 中 `status: PASS` 且 `run_id/workflow_url` 留痕完整，避免仅改状态字段导致的误通过。
25. `/ui` 增加 CI First Run 状态面板（仅展示已有文档字段，不新增公开 API），用于解释当前是否具备首轮 CI 真网验收证据。
26. `/ui` 的 CI First Run 面板追加展示 `note` 字段（来自 `CI_FIRST_RUN.md` 的 Notes），用于直观看到阻塞原因（如 gh 未登录/仓库未解析）。
