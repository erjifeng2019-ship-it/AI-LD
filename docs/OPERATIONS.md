# OPERATIONS

## 初始化
```bash
uv sync
uv run ai-chain init-db
uv run ai-chain load-taxonomy
```

## 每日流程（串行）
```bash
uv run ai-chain import mapping --file data/seeds/AI_semiconductor_A_share_mapping_v1.csv
uv run ai-chain sync tushare --date YYYY-MM-DD --no-prefer-cache
uv run ai-chain sync finmind --start YYYY-MM-DD --end YYYY-MM-DD --symbols 2330
uv run ai-chain sync sec --tickers NVDA,AVGO,MU
uv run ai-chain sync opendart --symbols 005930,000660 --date YYYY-MM-DD
uv run ai-chain extract evidence --date YYYY-MM-DD
uv run ai-chain score-market-confirmation --date YYYY-MM-DD
uv run ai-chain score --date YYYY-MM-DD
uv run ai-chain review --date YYYY-MM-DD --lookback 10
uv run ai-chain dq report --date YYYY-MM-DD
uv run ai-chain brief --date YYYY-MM-DD --format md
```

## 一键串行（PowerShell）
```powershell
.\run_all.ps1 -Date 2026-05-28
```
> Note: `run_all.ps1` auto-loads `.env` and preserves existing non-empty env vars.

环境变量（PowerShell 当前会话）：
```powershell
$env:AI_CHAIN_ENV = "local"
$env:TUSHARE_TOKEN = "<your_token>"
$env:FINMIND_TOKEN = "<your_token>"
$env:SEC_USER_AGENT = "your_email@example.com"
$env:OPENDART_API_KEY = "<your_key>"
```

可选参数：
```powershell
.\run_all.ps1 `
  -Date 2026-05-28 `
  -FinmindStart 2026-01-01 `
  -FinmindEnd 2026-05-28 `
  -FinmindSymbols 2330 `
  -SecTickers NVDA `
  -OpenDartSymbols 005930 `
  -StopApiBeforeRun `
  -PreferCache `
  -SkipValidate
```

说明：
- 脚本强制串行，不并发访问同一 DuckDB 文件。
- 默认先跑 `ruff/mypy/pytest`，加 `-SkipValidate` 可跳过。
- 结尾会输出三类摘要：
  - 最新 `source_run_log` 明细；
  - 凭据可用性（只显示 available/missing，不打印密钥）；
  - 最新 `missing_credentials` 数据源与最新 `ok` 数据源清单。
- 若检测到 API 正在运行，脚本会提示潜在 DuckDB 锁竞争；可用 `-StopApiBeforeRun` 自动清理旧 API 进程后再跑全链路。

## v0.2 一键收尾（推荐）
```powershell
.\scripts\close_v02.ps1 -Date 2026-05-28 -StopApiBeforeRun
```
说明：
- 内部顺序：`run_all.ps1 -> export network-acceptance -> export v02-audit`
- 任一步骤失败即停止并返回非零退出码（避免“部分失败但仍显示完成”）。
- 自动产物：
  - `docs/NETWORK_ACCEPTANCE_YYYY-MM-DD.md`
  - `docs/V0_2_COMPLETION_AUDIT_YYYY-MM-DD.md`
  - `docs/CI_FIRST_RUN.md`

可选连带 CI 首轮留痕：
```powershell
.\scripts\close_v02.ps1 `
  -Date 2026-05-28 `
  -StopApiBeforeRun `
  -DispatchCiFirstRun `
  -CiRepo <owner/repo>
```
- 若仅预演 CI，不触发 workflow：
  - `.\scripts\close_v02.ps1 -Date 2026-05-28 -DispatchCiFirstRun -CiDryRunOnly`
  - 该链路会刷新 `docs/CI_FIRST_RUN.md` 为 `PENDING`，用于先验证本地收尾脚本与回填逻辑。

## 前端 Dashboard
```bash
uv run uvicorn ai_chain_radar.api.app:app --reload --port 8000
```

打开：
```text
http://127.0.0.1:8000/ui
```

页面包含：
- Health
- Source Status（来自最新 run log）
- Credential Availability（只展示是否可用）
- Data Freshness（latest run time + latest review date + source 计数）
- CI First Run（status/repo/run_id/workflow_url/reason/note）
- Review Summary（latest review date 下的 segment precision/recall 截面）
- Review Trend（最近多个 review_date 的 segment precision/recall 变化）
- Latest Scores / Latest Briefing / Segments / Anchors

## FastAPI 只读接口
- `GET /health`
- `GET /segments`
- `GET /anchors`
- `GET /scores/latest`
- `GET /scores/{date}`
- `GET /briefings/latest`
- `GET /briefings/{date}`
- `GET /symbols/{symbol}/mapping`
- `GET /events/latest`
- `GET /evidence/latest`
- `GET /review/{date}`
- `GET /review-summary/{date}`

## 联调验证（有凭据时）
```bash
pytest -m integration
```
- 说明：测试隔离策略已调整为“非 integration 清空凭据、integration 保留凭据”。
- 若仅部分凭据存在，相关用例会部分 skip（例如 `TUSHARE_TOKEN` 缺失时只跳过 Tushare 集成用例）。
- Windows 一键执行（自动加载 `.env`）：
  - `.\scripts\run_integration_with_env.ps1`

验收记录模板：
- `docs/NETWORK_ACCEPTANCE_TEMPLATE.md`

## 故障处理
- `missing_credentials`：检查 `.env` 是否配置对应凭据。
- DuckDB 文件锁冲突：
  - 首选：保持 `sync/score/brief` 串行，避免多条写命令并发。
  - API 建议通过 `.\scripts\start_api_single.ps1` 启动单实例。
  - 全链路执行时可加 `.\run_all.ps1 -StopApiBeforeRun ...`。
  - 可配置 `AI_CHAIN_DB_OPEN_RETRY_SECONDS`（默认 8 秒）缓解短时文件锁争用。
- 外部接口异常：状态应为 `failed` 并写入 `source_run_log`，保留 raw 数据用于复现。

## 反证规则运维
- 规则存储于 `counter_evidence_rule`，仅 `enabled=TRUE` 规则参与评分。
- `condition_expr` 使用安全表达式（比较、`and/or/not`、`abs/min/max`）。
- 命中规则后会：
  - 写入 `theme_opportunity_score.invalid_conditions_json`
  - 下调 `risk_score` 与 `final_score`
  - 在 `/briefings/{date}` 与 `/ui` 日报风险区展示

## Intraday 评分
- `score-market-confirmation` 与 `score` 支持 `--intraday`：
  - `uv run ai-chain score-market-confirmation --date YYYY-MM-DD --intraday`
  - `uv run ai-chain score --date YYYY-MM-DD --intraday`
- 含义：拥挤度计算会启用分项热度（成交/涨停/资金）合成，适合盘中或临近收盘场景。

## 文本清洗（离线）
- 预览模式（只扫描，不落库）：
  - `uv run ai-chain db clean-text`
- 应用模式（写回修复文本）：
  - `uv run ai-chain db clean-text --apply`
- 说明：该命令针对历史库中的标题/claim 等文本列做编码修复，不改变业务结构。

## CI 可选 integration
- 已提供 GitHub Actions 模板：
  - `.github/workflows/integration-optional.yml`
- 触发方式：
  - `workflow_dispatch` 手动触发
  - 每周定时触发
- Windows 自动触发并回填首轮留痕：
  - `.\scripts\ci_first_run_dispatch.ps1 -Repo <owner/repo>`
  - 仅预演（不触发）：`.\scripts\ci_first_run_dispatch.ps1 -DryRunOnly`
  - 可选无交互认证：先设置 `GH_TOKEN` 环境变量再执行脚本
  - 脚本会自动加载仓库根目录 `.env`（仅填充当前进程缺失变量），可在 `.env` 放置 `GH_TOKEN` 与 `GITHUB_REPOSITORY`。
- `workflow_dispatch` 可选输入：
  - `run_pipeline`：是否在 CI 中执行 `sync -> score -> brief` 再导出验收文档
  - `target_date`：业务日期（默认 yesterday UTC）
  - `acceptance_date`：验收文档日期（默认 today UTC）
  - `max_log_rows`：验收文档中 `source_run_log` 最大展示条数
- 依赖 secrets：
  - `TUSHARE_TOKEN`
  - `FINMIND_TOKEN`
  - `SEC_USER_AGENT`
- `OPENDART_API_KEY`
- 产物：
  - `docs/NETWORK_ACCEPTANCE_YYYY-MM-DD.md`
  - `data/briefings/YYYY-MM-DD.md`（若 pipeline 执行成功）
  - workflow artifact: `ai-chain-acceptance-YYYY-MM-DD`
  - 首轮留痕：回填 `docs/CI_FIRST_RUN.md` 并更新 `status: PASS/FAIL`
  - `v02-audit` 的 CI gate 通过条件为：`status: PASS` 且 `run_id/workflow_url` 非空。

## v0.2 additional commands
- Global anchors sync (optional network):
  - `uv run ai-chain sync global-anchors --date YYYY-MM-DD --dry-run`
  - `uv run ai-chain sync global-anchors --date YYYY-MM-DD`
- Manual global prices import:
  - `uv run ai-chain import global-prices --file data/manual/global_anchor_prices_YYYY-MM-DD.csv`
- Missing data report:
  - `uv run ai-chain dq missing --date YYYY-MM-DD`
- Daily alert:
  - `uv run ai-chain alert --date YYYY-MM-DD`
- Scoring calibration:
  - `uv run ai-chain calibrate scoring --window 60`
- Weekly report export:
  - `uv run ai-chain export weekly-report --date YYYY-MM-DD`
- Network acceptance export (auto-generate evidence doc):
  - `uv run ai-chain export network-acceptance --date YYYY-MM-DD --target-date YYYY-MM-DD`
  - optional: `--ui-screenshot <path> --max-log-rows 40`
- v0.2 completion audit export:
  - `uv run ai-chain export v02-audit --date YYYY-MM-DD`
  - local-only (不校验 CI gate): `uv run ai-chain export v02-audit --date YYYY-MM-DD --no-include-ci-gate`

## v0.2 workflow-compatible command forms
- Premarket:
  - `uv run ai-chain sync tushare --date YYYY-MM-DD --events-only`
  - `uv run ai-chain brief --date YYYY-MM-DD --mode premarket --format md`
- Intraday:
  - `uv run ai-chain sync tushare --date YYYY-MM-DD --realtime`
  - `uv run ai-chain score market-confirmation --date YYYY-MM-DD --intraday`
- Global anchor score only:
  - `uv run ai-chain score global-anchors --date YYYY-MM-DD`
  - alias: `uv run ai-chain score-global-anchors --date YYYY-MM-DD`

## API startup recommendation (DuckDB lock hygiene)
- Prefer single-entry startup script:
  - `.\scripts\start_api_single.ps1`
- The script will:
  - clean stale API python processes for this app,
  - start one API instance,
  - run `/health` check and fail fast if startup is invalid.
- `run_all.ps1` 预检日志中的 `process_trees=1, raw_processes=2` 在 Windows 上可视为正常单实例（venv launcher + child interpreter）。
- Keep CLI write operations serialized. Do not run multiple write commands in parallel against the same DuckDB file.
