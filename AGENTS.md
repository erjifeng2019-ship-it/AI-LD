# AGENTS.md

> 本文件是 Codex / 工程 Agent 在本仓库内自主工作的最高优先级项目说明。  
> 目标：让 Agent 在无人持续指挥的情况下，按阶段完成 AI 产业链风口雷达 MVP。  
> 默认语言：中文。代码、函数、变量名使用英文；注释可用中文或英文，但必须清晰。

---

## 1. 项目使命

构建一个本地可运行的 **AI 产业链风口雷达**：

```text
全球核心地标行情/披露
  ↓
产业链环节识别
  ↓
A股映射与纯度判断
  ↓
A股盘面与资金确认
  ↓
风口评分
  ↓
中文 Markdown 日报
```

第一阶段只追求 **命令行闭环**：

```bash
ai-chain init-db
ai-chain sync ...
ai-chain score --date YYYY-MM-DD
ai-chain brief --date YYYY-MM-DD --format md
```

---

## 2. 自主推进规则

当用户没有给出更具体任务时，按以下顺序自主推进：

```text
M0 仓库骨架
M1 DuckDB/schema/repository
M2 Tushare adapter
M3 taxonomy 和种子数据
M4 FinMind adapter
M5 SEC adapter
M6 OpenDART adapter
M7 scoring
M8 briefing
M9 FastAPI
```

不要等待确认。若遇到不确定点，选择最稳妥、最小可行方案，并在 `docs/DECISIONS.md` 记录假设。

---

## 3. 不可违反的规则

```text
1. 不要把任何 token、API key、邮箱、账号密码写进代码或测试 fixture。
2. 不要在日志中打印环境变量值。
3. 测试默认不得访问真实网络。
4. 外部 API 缺失时，实现 adapter 接口、dry-run、fixtures 和错误提示。
5. 每个数据源运行都必须写 source_run_log。
6. 每条结论必须有 evidence 或明确标记为 low confidence。
7. LLM 只做辅助摘要/抽取，不能直接决定评分。
8. 不输出确定性买卖建议。
9. 每次修改必须保持 `pytest` 和 `ruff` 可通过，除非在提交说明中明确标注原因。
10. 修改 schema 时，必须同步更新 docs 和 tests。
```

---

## 4. 推荐技术栈

```text
Python: 3.11+
Package manager: uv
CLI: typer
Config: pydantic-settings + yaml
DB: DuckDB MVP
Data: pandas
API: FastAPI
Templates: Jinja2
Testing: pytest
Lint: ruff
Typing: mypy
```

---

## 5. 仓库结构目标

若仓库为空，创建如下结构：

```text
.
├── AGENTS.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── configs/
│   ├── settings.yml
│   ├── source_priority.yml
│   ├── scoring_weights.yml
│   ├── keywords.yml
│   ├── chains/segments.yml
│   └── universe/
│       ├── global_anchors.yml
│       └── a_share_seed.yml
├── data/
│   ├── raw/.gitkeep
│   ├── processed/.gitkeep
│   ├── warehouse/.gitkeep
│   └── briefings/.gitkeep
├── docs/
│   ├── AI_CHAIN_RADAR_ARCHITECTURE_EXECUTION_PLAN.md
│   ├── DATA_SOURCES.md
│   ├── SCORING_MODEL.md
│   ├── OPERATIONS.md
│   └── DECISIONS.md
├── src/ai_chain_radar/
│   ├── __init__.py
│   ├── cli.py
│   ├── settings.py
│   ├── db/
│   ├── sources/
│   ├── taxonomy/
│   ├── features/
│   ├── scoring/
│   ├── briefing/
│   └── api/
└── tests/
    ├── fixtures/
    ├── test_settings.py
    ├── test_schema.py
    ├── test_scoring.py
    └── test_briefing.py
```

---

## 6. 开发命令约定

优先使用：

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy src
uv run ai-chain --help
```

如果 `uv` 不可用，允许使用：

```bash
python -m venv .venv
pip install -e ".[dev]"
pytest
ruff check .
```

---

## 7. 环境变量约定

创建 `.env.example`，但不要创建真实 `.env`：

```bash
AI_CHAIN_ENV=local
AI_CHAIN_DB_PATH=data/warehouse/ai_chain.duckdb
AI_CHAIN_TIMEZONE=Asia/Shanghai

TUSHARE_TOKEN=
FINMIND_TOKEN=
SEC_USER_AGENT="your-company your-email@example.com"
OPENDART_API_KEY=
JQUANTS_EMAIL=
JQUANTS_PASSWORD=
JQUANTS_REFRESH_TOKEN=
FRED_API_KEY=

OPENAI_API_KEY=
FMP_API_KEY=
TIINGO_API_KEY=
POLYGON_API_KEY=
```

读取环境变量时必须：

```text
1. 缺失时 graceful skip；
2. 不打印原值；
3. 在 source_run_log 写明 missing_credentials；
4. CLI 输出如何配置 `.env`。
```

---

## 8. 数据源 Adapter 规范

所有 adapter 继承统一接口：

```python
class SourceAdapter(Protocol):
    source_name: str

    def healthcheck(self) -> SourceHealth:
        ...

    def fetch(self, request: SourceRequest) -> SourceResult:
        ...

    def normalize(self, raw: SourceResult) -> NormalizedResult:
        ...

    def sync(self, request: SourceRequest) -> SyncResult:
        ...
```

结果对象必须包含：

```text
source
dataset
params
rows_read
rows_written
status
started_at
ended_at
error_message
raw_path
```

状态枚举：

```text
ok
empty
partial
failed
missing_credentials
schema_changed
rate_limited
skipped
```

---

## 9. MVP 数据源任务

### 9.1 TushareAdapter

优先实现这些 dataset：

```text
stock_basic
stock_company
daily
daily_basic
fina_mainbz
income
fina_indicator
anns_d
research_report
report_rc
limit_list_d
top_list
top_inst
moneyflow
margin_detail
hk_daily
hk_mins
```

行为要求：

```text
1. 无 TUSHARE_TOKEN 时，不报错退出，返回 missing_credentials。
2. 支持 --dry-run。
3. 保存原始响应到 data/raw/tushare/{dataset}/{date}.jsonl 或 parquet。
4. 标准化写入对应表。
5. row_count=0 不等于失败。
```

### 9.2 FinMindAdapter

优先实现：

```text
TaiwanStockPrice
TaiwanStockMonthRevenue
TaiwanStockFinancialStatements
TaiwanStockInstitutionalInvestorsBuySell
```

行为要求：

```text
1. 无 FINMIND_TOKEN 时允许尝试公开额度，失败则 missing_credentials。
2. 月营收必须计算 MoM/YoY。
3. 先支持全量拉指定 symbol，再支持 universe 批量。
```

### 9.3 SecAdapter

优先实现：

```text
submissions
companyfacts
filing metadata
10-K / 10-Q / 8-K keyword extraction
```

行为要求：

```text
1. 必须设置 SEC_USER_AGENT。
2. 尊重 SEC 限速；实现简单 rate limiter。
3. 保存原始 JSON。
4. 关键词抽取必须输出 impact_segments 和 evidence snippets。
```

### 9.4 OpenDartAdapter

优先实现：

```text
corp_code
list disclosures
financial statements if available
document download metadata
keyword extraction
```

行为要求：

```text
1. 无 OPENDART_API_KEY 时 missing_credentials。
2. Samsung / SK hynix 作为第一批 seed。
3. 保存原始响应。
```

---

## 10. 数据库任务

创建 `src/ai_chain_radar/db/schema.sql`，至少包含：

```text
source_run_log
global_anchor_security
global_anchor_price_daily
taiwan_monthly_revenue
us_sec_filing_event
korea_disclosure_event
industry_cycle_metric
ai_chain_segment
a_share_chain_mapping
a_share_market_confirmation
theme_opportunity_score
daily_ai_chain_briefing
```

Repository 必须提供：

```python
init_db()
upsert_dataframe(table_name: str, df: pd.DataFrame, keys: list[str])
write_run_log(run_log: SourceRunLog)
query_dataframe(sql: str, params: dict | None = None)
```

MVP 可以使用 DuckDB 原生 SQL；不要过早引入复杂 ORM。

---

## 11. Taxonomy 任务

创建：

```text
configs/chains/segments.yml
configs/universe/global_anchors.yml
configs/universe/a_share_seed.yml
```

第一版只覆盖五条主线：

```text
hbm_storage
cowos_advanced_packaging
optics_cpo_16t
pcb_connector
liquid_cooling_power
```

每个 segment 必须包含：

```yaml
id:
name:
parent:
description:
global_anchors:
a_share_segments:
positive_keywords:
negative_keywords:
confirmation_rules:
invalidation_rules:
```

---

## 12. Scoring 任务

### 12.1 必须实现的 scorer

```text
GlobalAnchorScore
BottleneckScore
MappingScore
TradingConfirmationScore
RiskScore
OpportunityScore
```

### 12.2 输入输出

每个 scorer：

```python
def score(input: ScoreInput) -> ScoreOutput:
    ...
```

`ScoreOutput` 必须包含：

```text
score: 0-100
confidence: 0-100
evidence: list[EvidenceItem]
warnings: list[str]
```

### 12.3 OpportunityScore 权重

默认：

```yaml
global_anchor_score: 0.20
bottleneck_score: 0.20
earnings_order_price_score: 0.15
a_share_mapping_score: 0.15
a_share_confirmation_score: 0.20
risk_adjustment: 0.10
```

风险调整允许为负分。

---

## 13. Briefing 任务

实现：

```bash
ai-chain brief --date YYYY-MM-DD --format md
```

生成路径：

```text
data/briefings/YYYY-MM-DD.md
```

简报必须包含：

```text
1. 今日总判断
2. 当前最强环节
3. 下一潜在风口
4. 全球核心地标变化
5. 台湾/韩国/日本/美国证据
6. A股映射与确认
7. 风险与反证
8. 明日观察点
```

简报中每个 segment 必须有：

```text
最终分
产业景气分
A股映射纯度分
A股交易确认分
拥挤度
证据
反证
确认条件
失效条件
```

---

## 14. CLI 任务

`src/ai_chain_radar/cli.py` 必须提供：

```bash
ai-chain --help
ai-chain init-db
ai-chain load-taxonomy
ai-chain show segments
ai-chain sync tushare --date YYYY-MM-DD [--dry-run]
ai-chain sync finmind --start YYYY-MM-DD --end YYYY-MM-DD [--symbols ...]
ai-chain sync sec --tickers NVDA,AVGO,MU
ai-chain sync opendart --symbols 005930,000660
ai-chain score --date YYYY-MM-DD
ai-chain brief --date YYYY-MM-DD --format md
```

所有命令失败时必须给出可操作错误，不允许 traceback 直接暴露给普通用户；测试环境可以打开 verbose。

---

## 15. FastAPI 任务

MVP 后再做。接口：

```text
GET /health
GET /segments
GET /anchors
GET /scores/latest
GET /scores/{date}
GET /briefings/latest
GET /briefings/{date}
GET /symbols/{symbol}/mapping
```

不要在 API 层实现业务逻辑；API 只读数据库和已生成结果。

---

## 16. 测试要求

### 16.1 必须有的测试

```text
test_settings.py
test_schema.py
test_repository.py
test_source_run_log.py
test_taxonomy_loader.py
test_scoring.py
test_briefing.py
test_cli_help.py
```

### 16.2 网络测试规则

```text
1. 默认测试不得访问真实网络。
2. 外部响应保存到 tests/fixtures。
3. 需要真实 API 的测试必须加 marker：@pytest.mark.integration
4. CI 默认跳过 integration。
```

### 16.3 验收命令

每个阶段完成后运行：

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

如 mypy 初期阻碍过大，可先配置为宽松，但必须逐步收紧。

---

## 17. 文档要求

每完成一个模块，更新：

```text
README.md：如何安装、如何运行
docs/DATA_SOURCES.md：数据源、字段、限制、授权提醒
docs/SCORING_MODEL.md：评分公式、权重、解释
docs/OPERATIONS.md：日常运行、调度、故障处理
docs/DECISIONS.md：重要技术选择和假设
```

每个 adapter 必须在 `docs/DATA_SOURCES.md` 写：

```text
数据源名称
用途
需要的 env vars
主要 endpoint/dataset
频率
限制
生产替代方案
```

---

## 18. Definition of Done

一个任务完成必须满足：

```text
1. 代码实现完成；
2. 有测试；
3. 无真实 token；
4. CLI 或函数有可验证输出；
5. source_run_log 可记录；
6. 文档已更新；
7. pytest 和 ruff 通过；
8. 如未完成，TODO 写明原因和下一步。
```

---

## 19. 当前推荐 Backlog

按顺序执行，完成后把 `[ ]` 改为 `[x]`。

### Phase 0：基础设施

- [x] 创建 pyproject.toml 和基础依赖
- [x] 创建 src/ai_chain_radar 包
- [x] 创建 settings loader
- [x] 创建 logging helper
- [x] 创建 CLI skeleton
- [x] 创建 DuckDB schema.sql
- [x] 创建 repository
- [x] 创建 init-db 命令
- [x] 添加 pytest/ruff/mypy

### Phase 1：配置和 taxonomy

- [x] 创建 segments.yml
- [x] 创建 global_anchors.yml
- [x] 创建 a_share_seed.yml
- [x] 实现 load-taxonomy
- [x] 实现 show segments
- [x] 写 taxonomy tests

### Phase 2：Tushare

- [x] 实现 TushareAdapter
- [x] 实现 stock_basic sync
- [x] 实现 daily/daily_basic sync
- [x] 实现 fina_mainbz sync
- [x] 实现 anns_d/research_report sync
- [x] 实现 limit_list_d/top_list/top_inst sync
- [x] 实现 source_run_log
- [x] 写 offline fixture tests

### Phase 3：FinMind

- [x] 实现 FinMindAdapter
- [x] 实现 TaiwanStockPrice
- [x] 实现 TaiwanStockMonthRevenue
- [x] 实现月营收 MoM/YoY
- [x] 写 tests

### Phase 4：SEC

- [x] 实现 SEC CIK/ticker resolver
- [x] 实现 submissions fetch
- [x] 实现 companyfacts fetch
- [x] 实现 filing metadata storage
- [x] 实现关键词抽取
- [x] 写 tests

### Phase 5：OpenDART

- [x] 实现 OpenDART corp code fetch
- [x] 实现 disclosure list fetch
- [x] 实现 disclosure metadata storage
- [x] 实现关键词抽取
- [x] 写 tests

### Phase 6：Scoring

- [x] 实现 EvidenceItem
- [x] 实现 GlobalAnchorScore
- [x] 实现 BottleneckScore
- [x] 实现 MappingScore
- [x] 实现 TradingConfirmationScore
- [x] 实现 RiskScore
- [x] 实现 OpportunityScore
- [x] 写 tests

### Phase 7：Briefing

- [x] 创建 daily_briefing.md.j2
- [x] 实现 renderer
- [x] 实现 ai-chain brief
- [x] 生成 data/briefings/YYYY-MM-DD.md
- [x] 写 tests

### Phase 8：API

- [x] 创建 FastAPI app
- [x] 实现 /health
- [x] 实现 /scores/latest
- [x] 实现 /briefings/latest
- [x] 写 tests

---

## 20. 重要设计决策

默认采用：

```text
1. DuckDB 作为本地 MVP 数据库；
2. 所有 adapter 可插拔；
3. 每个数据源先 raw 落地，再 normalize 入库；
4. schema 优先稳定，不追求过度抽象；
5. scoring 模型先规则化，后续再引入统计/ML；
6. brief 先 Markdown，后续再做 Web UI；
7. 所有结论附 evidence 和 invalidation。
```

如要改变这些决策，必须更新 `docs/DECISIONS.md`。

---

## 21. 失败处理

如果外部 API 不可用：

```text
1. 不要删除该 adapter；
2. 返回 status=failed 或 missing_credentials；
3. 写 source_run_log；
4. 使用 fixture 保持测试；
5. 在 docs/OPERATIONS.md 记录故障和替代方案。
```

如果 schema 变化：

```text
1. 保存 raw response；
2. status=schema_changed；
3. 不要静默丢字段；
4. 更新 normalize 和测试。
```

如果评分缺数据：

```text
1. 降低 confidence；
2. 标记 evidence 缺失；
3. 不要伪造数据；
4. 简报中写“数据不足，等待确认”。
```

---

## 22. 输出语气

生成给用户看的简报时：

```text
清晰、直接、像交易员复盘；
不要空话；
不要只写新闻；
必须写证据、反证、确认条件、失效条件；
不要使用“必涨”“稳赚”“一定”等确定性措辞。
```

示例风格：

```text
方向：1.6T 光模块上游
状态：预热
结论：产业景气强，但 A股确认不足。进入重点观察池，不追单日冲高。
证据：海外光通信锚点相对强；A股光模块总成已高位；资金开始向上游器件扩散。
反证：若上游器件放量失败，且龙头冲高回落，则该扩散逻辑降级。
```

---

## 23. 给未来 Agent 的提醒

```text
这个项目的壁垒不是抓了多少 API，
而是把“全球产业瓶颈迁移”映射到“A股可交易确认”。
不要把它做成资讯聚合器。
不要把它做成普通股票看板。
不要让 LLM 直接做交易判断。
始终把证据链、反证和置信度放在第一位。
```
