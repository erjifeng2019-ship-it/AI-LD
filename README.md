# AI Chain Radar

AI 产业链风口雷达（MVP / v0.2）。
当前阶段目标：在本地稳定跑通“数据同步 -> 证据抽取 -> 评分 -> 复盘 -> 简报 -> 验收归档”闭环。

## 快速开始
```bash
uv sync
uv run ai-chain init-db
uv run ai-chain load-taxonomy
uv run ai-chain --help
```

## 核心命令
```bash
uv run ai-chain import mapping --file data/seeds/AI_semiconductor_A_share_mapping_v1.csv
uv run ai-chain sync tushare --date 2026-05-29 --no-prefer-cache
uv run ai-chain extract evidence --date 2026-05-29
uv run ai-chain score --date 2026-05-29
uv run ai-chain review --date 2026-05-29 --lookback 10
uv run ai-chain brief --date 2026-05-29 --format md
uv run ai-chain export network-acceptance --date 2026-05-29 --target-date 2026-05-28 --max-log-rows 40
uv run ai-chain export v02-audit --date 2026-05-29
```

## v0.2 工作流兼容命令
```bash
# 盘前：仅同步事件类数据
uv run ai-chain sync tushare --date 2026-05-29 --events-only
uv run ai-chain brief --date 2026-05-29 --mode premarket --format md

# 盘中：确认分独立计算
uv run ai-chain score market-confirmation --date 2026-05-29 --intraday

# 全局锚点分独立查看
uv run ai-chain score global-anchors --date 2026-05-29
```

## API 启动（推荐）
```powershell
.\scripts\start_api_single.ps1
```
全链路执行时若担心 DuckDB 锁竞争，可使用：
```powershell
.\run_all.ps1 -Date 2026-05-28 -StopApiBeforeRun
```

## v0.2 一键收尾
```powershell
.\scripts\close_v02.ps1 -Date 2026-05-28 -StopApiBeforeRun
```
产物：
- `docs/NETWORK_ACCEPTANCE_YYYY-MM-DD.md`
- `docs/V0_2_COMPLETION_AUDIT_YYYY-MM-DD.md`
- `docs/CI_FIRST_RUN.md`

可选：同时触发首轮 CI 留痕（需已登录 `gh`）
```powershell
.\scripts\close_v02.ps1 `
  -Date 2026-05-28 `
  -StopApiBeforeRun `
  -DispatchCiFirstRun `
  -CiRepo <owner/repo>
```

## 质量检查
```bash
uv run ruff check .
uv run mypy src
uv run pytest
```

## 维护命令
```bash
uv run ai-chain db clean-text          # 预览
uv run ai-chain db clean-text --apply  # 应用
.\scripts\run_integration_with_env.ps1 # Windows: 加载 .env 后跑 integration
```

## CI 验收闭环
- Workflow: `.github/workflows/integration-optional.yml`
- `workflow_dispatch` 输入：
  - `run_pipeline`
  - `target_date`
  - `acceptance_date`
  - `max_log_rows`
- 产物：
  - `docs/NETWORK_ACCEPTANCE_YYYY-MM-DD.md`
  - `data/briefings/YYYY-MM-DD.md`（当 pipeline 执行成功）
- 首轮 CI 留痕文件：
  - `docs/CI_FIRST_RUN.md`（执行后将 `status` 更新为 `PASS` 或 `FAIL`）
  - 自动触发并回填（Windows）：
    - `.\scripts\ci_first_run_dispatch.ps1 -Repo <owner/repo>`
    - 预演：`.\scripts\ci_first_run_dispatch.ps1 -DryRunOnly`
    - 可选：设置 `GH_TOKEN` 以无交互方式执行

## 说明
- 无凭据的数据源会记为 `missing_credentials`，不会中断全流程。
- 每次同步/导入/抽取都会写 `source_run_log`。
- `/ui` 可查看 Source Status、Credential Availability、Data Freshness、Review Summary/Trend。
- 简报包含 `evidence_id` 引用与证据质量摘要。
- DuckDB 连接支持短时重试（`AI_CHAIN_DB_OPEN_RETRY_SECONDS`，默认 8 秒）以缓解瞬时文件锁争用。
