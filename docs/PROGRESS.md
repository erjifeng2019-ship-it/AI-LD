# PROGRESS

## 当前阶段（v0.2）

### 已完成
- [x] `import mapping`：支持 CSV/XLSX 导入、版本表、历史快照。
- [x] `evidence_registry`：支持自动抽取、查询、人工补录。
- [x] `review`：支持 T+1/T+3/T+5/T+10 复盘与 summary 聚合。
- [x] 评分链路：`counter_evidence_rule` 命中后写入 `invalid_conditions_json` 并惩罚 `risk_score/final_score`。
- [x] 评分新增 `confidence_score`（主线级），并写入 `theme_opportunity_score`。
- [x] 日报：支持 `evidence_id` 引用、证据质量摘要、风险标签、复盘摘要。
- [x] 证据提取增强：映射表中文环节自动归一到五条主线 `segment_id`，反证覆盖可按主线统计。
- [x] UI：显示 Source Status、Credential Availability、Data Freshness、Review Summary、Review Trend。
- [x] UI：新增 CI First Run 面板，显示 `status/repo/run_id/workflow_url/reason/note`，可直接解释为何 v0.2 仍卡在 `ci_first_run` gate。
- [x] CLI v0.2 兼容命令形态：
  - `sync tushare --events-only`
  - `sync tushare --realtime`
  - `score market-confirmation --intraday`
  - `score global-anchors`
  - `brief --mode premarket`
- [x] DuckDB 锁冲突收敛：
  - API 改为请求级短连接并显式关闭；
  - 提供单实例启动脚本 `scripts/start_api_single.ps1`。
  - 连接层新增短时重试（`AI_CHAIN_DB_OPEN_RETRY_SECONDS`）；
  - `run_all.ps1` 新增 API 预检与 `-StopApiBeforeRun`。
- [x] 验收自动归档：
  - 新增 `export network-acceptance`；
  - 自动生成 `docs/NETWORK_ACCEPTANCE_YYYY-MM-DD.md`；
  - 支持 `--max-log-rows` 控制日志体积。
- [x] CI 可选集成回归：
  - `.github/workflows/integration-optional.yml` 支持手动输入与定时触发；
  - 自动上传验收文档与相关产物 artifact。
- [x] 新增 v0.2 完成态审计导出：
  - `export v02-audit`
  - 自动生成 `docs/V0_2_COMPLETION_AUDIT_YYYY-MM-DD.md`
  - CI 首轮 gate 通过条件：`docs/CI_FIRST_RUN.md` 的 `status: PASS` 且 `run_id/workflow_url` 非空。
- [x] 新增 CI 首轮留痕自动触发脚本：
  - `scripts/ci_first_run_dispatch.ps1`
  - 支持 `-Repo <owner/repo>` 直接触发 `workflow_dispatch` 并自动回填 `docs/CI_FIRST_RUN.md`。
  - 支持 `GH_TOKEN` 无交互认证模式。
  - 支持自动加载仓库根目录 `.env`（缺失变量填充）读取 `GH_TOKEN/GITHUB_REPOSITORY`。
- [x] 新增 v0.2 一键收尾脚本：
  - `scripts/close_v02.ps1`
  - 串行执行 `run_all -> network_acceptance -> v02_audit`，并支持可选 CI 首轮触发。
- [x] 收尾脚本参数稳定性修复：
  - 修复 `close_v02.ps1` 调用 `ci_first_run_dispatch.ps1` 时的参数错绑（`RunPipeline` 布尔参数转换失败）。
  - `-DispatchCiFirstRun -CiDryRunOnly` 现可正常执行并刷新 `docs/CI_FIRST_RUN.md`。
- [x] 收尾脚本失败即停补强：
  - `close_v02.ps1` 新增原生命令退出码校验，避免某一步失败后误报“收尾完成”。
  - 修复函数参数名与 PowerShell 自动变量冲突问题（避免 Python 被误拉起交互模式）。

### 当前质量状态
- [x] `python -m ruff check .`
- [x] `python -m mypy src`
- [x] `python -m pytest`（`42 passed, 5 skipped`）
- [x] `python -m pytest -m integration`（`1 passed, 5 skipped, 40 deselected`）
- [x] `GET /ui` 页面校验包含 `CI First Run` 面板（页面内容检查通过）
- [x] `.\run_all.ps1 -Date 2026-05-28 -SkipValidate -StopApiBeforeRun`（全链路成功）
- [x] `python -m ai_chain_radar.cli export network-acceptance --date 2026-05-29 --target-date 2026-05-28 --max-log-rows 60`（`overall_pass=True`）
- [x] `python -m ai_chain_radar.cli export v02-audit --date 2026-05-28`（`required_pass=14/15`，仅 CI 首轮 gate 未完成）
- [x] `.\scripts\close_v02.ps1 -Date 2026-05-28 -SkipValidate -StopApiBeforeRun`（一键收尾成功，产物齐全）
- [x] `.\scripts\close_v02.ps1 -Date 2026-05-28 -SkipValidate -StopApiBeforeRun -DispatchCiFirstRun -CiDryRunOnly`（CI dry-run 链路成功）

## 下一步（继续自动推进）
1. 在 CI secrets 完备后执行一次 workflow_dispatch，归档首轮 CI 产物与结论。
2. 将首轮 CI 产物回填到 `docs/NETWORK_ACCEPTANCE_*.md` 与 `docs/DECISIONS.md`。
3. 继续收敛剩余文档细节（以两份计划文档为准，不扩 scope）。

> 当前外部阻塞证据（本机）：`gh auth status` 返回未登录；已通过 `scripts/ci_first_run_dispatch.ps1` 固化到 `docs/CI_FIRST_RUN.md`。
