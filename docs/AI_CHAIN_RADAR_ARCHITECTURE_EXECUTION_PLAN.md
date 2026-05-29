# AI 产业链风口雷达：架构与执行方案

> 版本：v0.1  
> 生成日期：2026-05-28  
> 目标读者：项目 Owner、Codex、后续维护 Agent、量化/数据工程开发者  
> 项目定位：全球 AI 半导体/算力产业链研究系统 + A股映射与交易确认系统  
> 默认输出语言：中文  
> 默认时区：Asia/Shanghai  
> 重要声明：本项目用于研究、情报整理和交易辅助决策，不输出无依据的买卖建议，不替代投资顾问判断。

---

## 0. 项目总定义

**AI 产业链风口雷达**不是资讯聚合器，也不是普通行情看板。它的核心任务是：

```text
用全球核心地标识别产业瓶颈，
用台湾/韩国/日本/美国供应链数据确认景气度，
用 A股产业链映射判断真实受益纯度，
用 A股盘面、资金、公告、研报、龙虎榜确认交易价值，
最终输出：当前风口、下一个潜在风口、确认条件、反证条件、风险等级。
```

最终要回答的问题：

```text
1. 全球 AI 产业链当前最强环节是什么？
2. 当前市场在交易 GPU、HBM、CoWoS、1.6T/CPO、PCB、液冷、电力中的哪一层？
3. 下一个瓶颈可能迁移到哪里？
4. A股对应哪些产业链环节和公司？
5. 哪些是核心受益，哪些是二阶扩散，哪些只是蹭概念？
6. 产业逻辑是否已经被 A股盘面和资金确认？
7. 当前是未启动、预热、启动、主升、扩散、高潮、分歧，还是退潮？
8. 如果判断错了，哪些信号会证伪？
```

---

## 1. 产品原则

### 1.1 三个永远分清

```text
产业很强 ≠ A股马上涨
A股涨了 ≠ 产业真的强
海外涨了 ≠ A股一定跟
```

每个方向必须同时输出三类分数：

```text
产业景气分
A股映射纯度分
A股交易确认分
```

### 1.2 先证据，后结论

系统不允许直接根据新闻标题生成结论。正确链路：

```text
原始数据/原始文件
  ↓
标准化数据
  ↓
实体识别与产业链映射
  ↓
量化特征
  ↓
评分模型
  ↓
冲突检测
  ↓
结论生成
  ↓
证据链与反证条件
```

### 1.3 结论必须可追溯

任何简报中的结论都必须能追溯到：

```text
数据源
采集时间
原始字段
计算逻辑
命中的规则
相关公司/环节/事件
```

### 1.4 不追求第一版全自动

MVP 的现实目标：

```text
70% 自动采集与计算
20% LLM/规则做文本抽取和映射
10% 人工校正产业链标签
```

等标签库稳定后，再逐步自动化。

---

## 2. 总体架构

### 2.1 分层架构

```text
┌─────────────────────────────────────────────────────────────┐
│                      Product Layer                           │
│  CLI 简报 / Markdown 日报 / FastAPI / Web Dashboard / Alerts │
└─────────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────────┐
│                   Intelligence Layer                         │
│  风口评分 / 瓶颈迁移 / A股映射 / 交易确认 / 冲击风险 / 简报生成 │
└─────────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────────┐
│                    Knowledge Layer                           │
│  产业链 taxonomy / 全球地标库 / A股映射库 / 公司别名 / 事件本体 │
└─────────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────────┐
│                    Feature Layer                             │
│  相对强弱 / 月营收趋势 / 财报关键词 / 涨停扩散 / 资金确认 / 拥挤度 │
└─────────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────────┐
│                    Storage Layer                             │
│  DuckDB MVP / PostgreSQL 生产 / Object Storage 原文与附件       │
└─────────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────────┐
│                    Ingestion Layer                           │
│  Tushare / FinMind / SEC / OpenDART / J-Quants / FRED / DBnomics │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 第一版推荐技术栈

MVP 优先简单、可控、可本地运行：

```text
语言：Python 3.11+
包管理：uv，兼容 pip
数据处理：pandas, polars 可选
本地分析库：DuckDB
生产数据库：PostgreSQL，后续可加 TimescaleDB / ClickHouse
后端：FastAPI
调度：APScheduler 或 Prefect，MVP 先用 CLI + cron
配置：pydantic-settings + YAML
CLI：Typer
日志：structlog 或标准 logging
测试：pytest
代码质量：ruff, mypy
文本抽取：规则优先，LLM 作为可插拔模块
前端：MVP 不强制；后续 Next.js + TradingView Lightweight Charts + ECharts
```

---

## 3. 数据源战略

### 3.1 现有 Tushare 资源定位

Tushare 是本项目的 **A股/港股内场确认层**，不是全球产业链领先判断层。

现有权限实测显示：Tushare 报告中 122 个接口被探测，113 个可调取，明确无权限接口为 0；`row_count=0` 表示本次样本条件无记录，不等于无权限。重点可用类别包括：

```text
A股基础：stock_basic, stock_company, trade_cal
A股行情：daily, weekly, monthly, daily_basic, stk_factor
A股财务：income, balancesheet, cashflow, fina_indicator, fina_mainbz, disclosure_date
A股事件：anns_d, news, research_report, report_rc, npr, cctv_news
交易确认：limit_list_d, top_list, top_inst, moneyflow, margin, margin_detail
集合竞价：stk_auction_o, stk_auction_c, stk_premarket
实时分钟：rt_k, rt_idx_k, rt_sw_k, rt_min, rt_idx_min, stk_mins, idx_mins
指数行业：index_basic, index_daily, index_weight, index_classify, index_member_all
港股：hk_basic, hk_daily, hk_mins, hk_income, hk_fina_indicator, hk_hold
宏观/风险：fx_daily, shibor, opt_daily, fut_daily, fut_holding
美股入口：us_basic 可用；us_daily/us_income 需复测具体 symbol
```

Tushare 负责：

```text
1. A股产业链公司池建立；
2. 主营业务、财报、公告、研报验证；
3. A股盘面强弱、涨停扩散、龙虎榜、资金确认；
4. 港股中资科技桥接；
5. 指数、情绪、期权、期货、外汇反证。
```

### 3.2 外部数据源优先级

#### P0：MVP 必接

| 数据层 | 首选工具/源 | 用途 |
|---|---|---|
| 台湾供应链 | FinMind | 台股行情、月营收、财报、三大法人、持股 |
| 美国披露 | SEC 官方 API | submissions, companyfacts, XBRL |
| 美国披露解析 | EdgarTools | 10-K/10-Q/8-K/XBRL 结构化 |
| 韩国披露 | OpenDartReader + OpenDART 官方 | Samsung, SK hynix, Hanmi 等披露 |
| 宏观 | FRED / DBnomics | 美债、美元、利率、通胀、全球宏观 |
| A股/港股 | Tushare | 交易确认和映射层 |

#### P1：第二阶段接入

| 数据层 | 首选工具/源 | 用途 |
|---|---|---|
| 日本地标 | J-Quants | TEL, Advantest, Disco, Ibiden, Shinko 等行情与财务 |
| 台湾官方源 | TWSE OpenAPI / MOPS | 生产化校验 FinMind |
| 韩国行情 | KRX 官方 / FinanceDataReader / pykrx | SK hynix, Samsung, Hanmi 等行情 |
| 政策冲击 | Federal Register API | 美国出口管制、半导体政策、关税文件 |
| 制裁/实体清单 | Consolidated Screening List API | 出口限制/实体清单监控 |
| 全球事件 | GDELT | 新闻事件、政治冲击、地缘风险 |

#### P2：形成壁垒的数据

| 数据层 | 可能来源 | 用途 |
|---|---|---|
| 存储价格 | TrendForce / DRAMeXchange | DRAM/NAND/HBM/eSSD 价格 |
| 半导体销售 | WSTS / SIA | 全球半导体周期 |
| 设备周期 | SEMI | WFE、封装测试设备、晶圆厂扩产 |
| 光通信 | LightCounting | 800G/1.6T/CPO/光模块周期 |
| 网络设备 | Dell'Oro / 650 Group | AI networking、交换机、数据中心网络 |
| 台系供应链新闻 | Digitimes | 订单、产能、客户导入线索 |
| 服务器/数据中心 | IDC / Gartner / Omdia | AI 服务器、数据中心建设周期 |

### 3.3 不建议做核心依赖的工具

```text
OpenBB：
  可以做统一适配层或快速原型。
  不作为核心真源，原因是底层 provider 会变化，且需要注意 AGPLv3 对商业化的影响。

sec-edgar-downloader：
  可作为原始 SEC 文件下载工具。
  结构化分析优先使用 SEC 官方 API + EdgarTools。

FinanceDataReader / pykrx：
  可作为韩国行情研究备份。
  生产级建议优先官方 KRX 或付费源。
```

---

## 4. 产业链 taxonomy

### 4.1 顶层链路

```text
L0 需求层：模型、云厂商、AI capex、算力租赁、推理需求
L1 计算芯片层：GPU、ASIC、CPU、DPU、XPU
L2 存储层：HBM、DDR5、LPDDR、eSSD、NAND
L3 晶圆制造层：先进制程、成熟制程、晶圆代工
L4 先进封装层：CoWoS、SoIC、InFO、2.5D/3D、HBM封装
L5 封装材料层：ABF、BT、underfill、EMC、RDL、TIM、硅中介层
L6 半导体设备层：光刻、刻蚀、沉积、清洗、检测、测试、键合、切割研磨
L7 网络芯片层：Switch ASIC、DSP、SerDes、Retimer、PHY、DPU/NIC
L8 光通信层：光模块、光芯片、EML、VCSEL、硅光、CPO、OCS
L9 服务器整机层：AI 服务器、ODM、PCB、电源、连接器、高速铜缆
L10 数据中心基础设施：液冷、电力、UPS、变压器、机柜、温控
L11 A股交易层：映射股票、公告、研报、财务、涨停、资金确认
```

### 4.2 第一版重点方向

只做 5 条链，避免失控：

```text
1. HBM / 存储 / HBM4
2. CoWoS / 先进封装 / 封装材料 / 测试设备
3. 1.6T 光模块 / CPO / 硅光 / 光芯片
4. 高速 PCB / 低损耗 CCL / 连接器 / 高速铜缆
5. 液冷 / 数据中心电力 / UPS / 变压器 / 温控
```

---

## 5. 全球核心地标库

### 5.1 美国

```yaml
ai_compute:
  - NVDA   # GPU / NVLink / AI server platform
  - AMD    # GPU / CPU / AI accelerator
  - AVGO   # custom ASIC / AI networking / DSP
  - MRVL   # custom ASIC / optics / networking
  - ALAB   # retimer / PCIe / CXL
  - CRDO   # high-speed connectivity
storage:
  - MU     # HBM / DRAM / NAND
networking_optics:
  - ANET   # AI networking switch
  - COHR   # optical components / lasers
  - LITE   # optical components / lasers
  - CIEN   # optical networking
server_infra:
  - SMCI   # AI server
  - DELL   # AI server
  - HPE    # server
  - VRT    # data center power / thermal
```

### 5.2 台湾

```yaml
foundry_packaging:
  - TSMC
  - ASE
asic_design:
  - GUC
  - Alchip
server_odm:
  - Wiwynn
  - Quanta
  - Wistron
  - Inventec
substrate_pcb:
  - Unimicron
  - Kinsus
  - Tripod
network_connector_power:
  - Accton
  - Lotes
  - Delta
```

### 5.3 韩国

```yaml
storage_hbm:
  - SK_hynix
  - Samsung_Electronics
equipment:
  - Hanmi_Semiconductor
  - HPSP
  - ISC
  - SFA_Semicon
  - DB_HiTek
```

### 5.4 日本

```yaml
equipment:
  - Tokyo_Electron
  - Advantest
  - Disco
  - Lasertec
  - Screen
substrate_material:
  - Ibiden
  - Shinko
connection:
  - Fujikura
```

### 5.5 港股/中资桥接

```yaml
semiconductor:
  - SMIC
  - Hua_Hong
technology:
  - Tencent
  - Alibaba
  - Xiaomi
  - Lenovo
telecom:
  - ZTE
```

---

## 6. A股映射体系

### 6.1 映射分层

每个 A股标的必须归入以下之一：

```text
一阶核心受益：
  产品/客户/收入与目标环节直接相关，且已有财务或订单验证。

二阶扩散受益：
  不是产业链最核心环节，但受扩产、升级、替代、供应链外溢拉动。

概念观察：
  有关键词或布局，但收入占比低、客户/订单不明确、财务未验证。

伪概念/剔除：
  仅媒体/互动平台提及，无产品、无收入、无可验证证据。
```

### 6.2 产业纯度分

```text
产业纯度分 =
30% 收入占比
20% 产品技术匹配
15% 客户/供应链证据
15% 财报验证
10% 公告/研报/互动验证
10% 业务排他性
```

### 6.3 A股映射库字段

```yaml
ts_code: 股票代码
name: 公司名称
segment: 一级产业环节
sub_segment: 细分环节
product: 相关产品
global_anchor_links: 对应全球地标
purity_level: high | medium | low | concept | exclude
revenue_exposure: 收入占比，未知则 null
gross_margin_trend: rising | flat | falling | unknown
customer_evidence: 客户证据
order_evidence: 订单证据
source_evidence: 公告/财报/研报/新闻 URL 或文件 ID
is_core: bool
is_second_order: bool
is_concept_only: bool
notes: 人工备注
last_verified_at: 更新时间
```

---

## 7. 数据库设计

MVP 使用 DuckDB，生产可切 PostgreSQL。所有表必须带：

```text
source
source_version
source_url_or_id
ingested_at
updated_at
data_quality_flag
```

### 7.1 数据源运行日志

```sql
CREATE TABLE IF NOT EXISTS source_run_log (
    run_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    job_name TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP,
    status TEXT NOT NULL,
    rows_read INTEGER DEFAULT 0,
    rows_written INTEGER DEFAULT 0,
    error_message TEXT,
    params_json TEXT
);
```

### 7.2 全球地标证券表

```sql
CREATE TABLE IF NOT EXISTS global_anchor_security (
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    company_name TEXT NOT NULL,
    country TEXT,
    currency TEXT,
    industry_layer TEXT,
    chain_segment TEXT,
    is_core_anchor BOOLEAN DEFAULT FALSE,
    related_a_share_segments TEXT,
    related_a_share_symbols TEXT,
    source TEXT,
    updated_at TIMESTAMP,
    PRIMARY KEY(symbol, market)
);
```

### 7.3 全球地标行情

```sql
CREATE TABLE IF NOT EXISTS global_anchor_price_daily (
    trade_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    pre_close DOUBLE,
    pct_chg DOUBLE,
    volume DOUBLE,
    amount DOUBLE,
    relative_strength_5d DOUBLE,
    relative_strength_20d DOUBLE,
    source TEXT,
    ingested_at TIMESTAMP,
    PRIMARY KEY(trade_date, symbol, market)
);
```

### 7.4 台湾月营收

```sql
CREATE TABLE IF NOT EXISTS taiwan_monthly_revenue (
    revenue_month TEXT NOT NULL,
    symbol TEXT NOT NULL,
    company_name TEXT,
    revenue DOUBLE,
    revenue_mom DOUBLE,
    revenue_yoy DOUBLE,
    cumulative_revenue DOUBLE,
    cumulative_yoy DOUBLE,
    source TEXT,
    ingested_at TIMESTAMP,
    PRIMARY KEY(revenue_month, symbol)
);
```

### 7.5 美国 SEC filing 事件

```sql
CREATE TABLE IF NOT EXISTS us_sec_filing_event (
    accession_number TEXT PRIMARY KEY,
    cik TEXT NOT NULL,
    symbol TEXT,
    company_name TEXT,
    form_type TEXT,
    filing_date DATE,
    report_date DATE,
    filing_url TEXT,
    raw_path TEXT,
    extracted_text_path TEXT,
    key_items_json TEXT,
    keywords_json TEXT,
    impact_segments TEXT,
    sentiment_score DOUBLE,
    ingested_at TIMESTAMP
);
```

### 7.6 韩国披露事件

```sql
CREATE TABLE IF NOT EXISTS korea_disclosure_event (
    rcept_no TEXT PRIMARY KEY,
    corp_code TEXT,
    stock_code TEXT,
    corp_name TEXT,
    report_nm TEXT,
    rcept_dt DATE,
    rm TEXT,
    raw_url TEXT,
    raw_path TEXT,
    key_items_json TEXT,
    impact_segments TEXT,
    ingested_at TIMESTAMP
);
```

### 7.7 产业指标

```sql
CREATE TABLE IF NOT EXISTS industry_cycle_metric (
    metric_date DATE NOT NULL,
    metric_type TEXT NOT NULL,
    segment TEXT NOT NULL,
    value DOUBLE,
    unit TEXT,
    source TEXT,
    yoy DOUBLE,
    mom DOUBLE,
    z_score DOUBLE,
    interpretation TEXT,
    ingested_at TIMESTAMP,
    PRIMARY KEY(metric_date, metric_type, segment, source)
);
```

### 7.8 产业链环节表

```sql
CREATE TABLE IF NOT EXISTS ai_chain_segment (
    segment_id TEXT PRIMARY KEY,
    segment_name TEXT NOT NULL,
    parent_segment TEXT,
    cycle_stage TEXT,
    bottleneck_level DOUBLE,
    technology_generation TEXT,
    upstream_segments TEXT,
    downstream_segments TEXT,
    key_global_anchors TEXT,
    key_a_share_symbols TEXT,
    updated_at TIMESTAMP
);
```

### 7.9 A股映射表

```sql
CREATE TABLE IF NOT EXISTS a_share_chain_mapping (
    ts_code TEXT NOT NULL,
    name TEXT,
    segment TEXT NOT NULL,
    sub_segment TEXT,
    product TEXT,
    global_anchor_links TEXT,
    purity_level TEXT,
    purity_score DOUBLE,
    revenue_exposure DOUBLE,
    gross_margin DOUBLE,
    gross_margin_trend TEXT,
    customer_evidence TEXT,
    order_evidence TEXT,
    source_evidence TEXT,
    is_core BOOLEAN,
    is_second_order BOOLEAN,
    is_concept_only BOOLEAN,
    notes TEXT,
    last_verified_at TIMESTAMP,
    PRIMARY KEY(ts_code, segment, sub_segment)
);
```

### 7.10 A股交易确认

```sql
CREATE TABLE IF NOT EXISTS a_share_market_confirmation (
    trade_date DATE NOT NULL,
    ts_code TEXT NOT NULL,
    segment TEXT,
    pct_chg DOUBLE,
    turnover_rate DOUBLE,
    amount DOUBLE,
    volume_ratio DOUBLE,
    auction_strength DOUBLE,
    limit_status TEXT,
    dragon_tiger_net_buy DOUBLE,
    institution_net_buy DOUBLE,
    moneyflow_score DOUBLE,
    margin_score DOUBLE,
    trend_score DOUBLE,
    confirmation_score DOUBLE,
    source TEXT,
    ingested_at TIMESTAMP,
    PRIMARY KEY(trade_date, ts_code, segment)
);
```

### 7.11 主题/风口评分

```sql
CREATE TABLE IF NOT EXISTS theme_opportunity_score (
    score_date DATE NOT NULL,
    segment TEXT NOT NULL,
    industry_score DOUBLE,
    bottleneck_score DOUBLE,
    global_anchor_score DOUBLE,
    earnings_order_price_score DOUBLE,
    a_share_mapping_score DOUBLE,
    a_share_confirmation_score DOUBLE,
    crowding_score DOUBLE,
    risk_score DOUBLE,
    final_score DOUBLE,
    stage TEXT,
    conclusion TEXT,
    evidence_json TEXT,
    invalid_conditions_json TEXT,
    created_at TIMESTAMP,
    PRIMARY KEY(score_date, segment)
);
```

### 7.12 简报表

```sql
CREATE TABLE IF NOT EXISTS daily_ai_chain_briefing (
    briefing_date DATE PRIMARY KEY,
    global_chain_conclusion TEXT,
    top_segments_json TEXT,
    next_watch_segments_json TEXT,
    a_share_confirmed_segments_json TEXT,
    risk_segments_json TEXT,
    action_suggestion TEXT,
    evidence_json TEXT,
    invalid_conditions_json TEXT,
    markdown_path TEXT,
    created_at TIMESTAMP
);
```

---

## 8. 评分模型

### 8.1 总分

```text
AI 产业链风口分 =
20% 全球核心地标强度
20% 产业景气/瓶颈强度
15% 财报/订单/价格验证
15% A股产业映射纯度
20% A股交易确认
10% 风险调整
```

风险调整可以是负分，范围建议：

```text
risk_score = -20 到 +10
```

### 8.2 分数解释

| 分数 | 状态 | 含义 |
|---:|---|---|
| 85-100 | S级风口 | 产业强、映射强、交易确认强 |
| 70-85 | A级主线 | 值得重点跟踪或参与 |
| 55-70 | B级预热 | 逻辑强但确认不足 |
| 40-55 | C级观察 | 有题材，无强验证 |
| 0-40 | D级噪音 | 不值得进入主线池 |

### 8.3 阶段状态机

```text
未启动：
  产业或海外有信号，但 A股无响应。

预热：
  海外锚点增强，A股少数标的异动，尚无板块扩散。

启动：
  龙头走强，成交放大，出现涨停或趋势突破。

主升：
  多个核心标的共振，涨停/趋势扩散，资金确认。

扩散：
  从龙头扩散到二阶环节，如从光模块扩到光芯片、PCB、连接器。

高潮：
  大面积上涨，后排补涨，研报和消息密集，拥挤度升高。

分歧：
  龙头仍强但后排炸板、资金分化、成交异常。

退潮：
  龙头跌破关键位，昨日涨停负反馈，资金撤退，主题降级。
```

---

## 9. 核心引擎设计

### 9.1 全球锚点强度引擎

输入：

```text
全球锚点日线
本国指数
SOX / Nasdaq / KOSPI / Nikkei / TWSE 等基准
成交量和成交额
财报日事件
```

核心特征：

```text
pct_1d
pct_5d
pct_20d
relative_strength_5d
relative_strength_20d
new_high_60d
volume_zscore
earnings_gap
post_earnings_drift_5d
```

输出：

```text
global_anchor_score by segment
```

### 9.2 产业景气/瓶颈引擎

瓶颈分：

```text
bottleneck_score =
25% 需求增速
20% 供给集中度
15% 扩产周期
15% 价格趋势
10% 交期/订单
10% 技术代际升级
5% 客户认证难度
```

MVP 没有付费价格数据时，先用替代指标：

```text
财报关键词
月营收趋势
全球锚点相对强弱
公告/研报中订单、产能、认证关键词
```

### 9.3 财报/订单/价格验证引擎

关键词字典：

```yaml
positive:
  - AI infrastructure
  - data center revenue
  - HBM
  - HBM4
  - strong demand
  - supply constrained
  - capacity constrained
  - sold out
  - backlog
  - customer qualification
  - advanced packaging
  - CoWoS
  - 1.6T
  - silicon photonics
  - CPO
  - liquid cooling
negative:
  - inventory correction
  - demand softness
  - pricing pressure
  - margin decline
  - customer delay
  - export restriction
  - supply disruption
```

输出：

```text
earnings_order_price_score
impact_segments
evidence snippets
```

### 9.4 A股映射引擎

输入：

```text
a_share_chain_mapping
fina_mainbz
income
fina_indicator
anns_d
research_report
report_rc
news
```

输出：

```text
a_share_mapping_score by segment
核心标的清单
二阶扩散清单
概念观察清单
剔除清单
```

### 9.5 A股交易确认引擎

```text
A股交易确认分 =
20% 龙头相对强度
20% 板块涨停/趋势扩散
15% 集合竞价强度
15% 成交额放大
10% 龙虎榜/机构席位
10% 两融/资金流
10% 筹码与位置
```

必须识别：

```text
龙头独涨
板块扩散
低位补涨
高位拥挤
冲高回落
金融护盘导致指数失真
```

### 9.6 拥挤度引擎

```text
拥挤度 =
25% 近 20/60 日涨幅分位
20% 成交额分位
15% 换手率分位
15% 研报密度
10% 融资余额增长
10% 龙虎榜集中度
5% 股东人数/筹码变化
```

输出：

```text
low / medium / high / extreme
```

### 9.7 政策/冲击风险引擎

事件分级：

| 等级 | 含义 | 系统动作 |
|---|---|---|
| S0 | 噪音消息 | 记录，不进首页 |
| S1 | 板块扰动 | 影响相关主题 |
| S2 | 风险偏好扰动 | 下调置信度 |
| S3 | 市场级冲击 | 下调风向分 |
| S4 | 系统性风险 | 防守模式 |

事件类型：

```text
AI GPU 出口限制
HBM 出口限制
半导体设备出口管制
先进封装限制
实体清单
关税
地缘冲突
Fed / 利率 / 汇率冲击
```

---

## 10. 输出形态

### 10.1 CLI 输出

MVP 第一版必须支持：

```bash
ai-chain init-db
ai-chain sync tushare --date 20260528
ai-chain sync finmind --start 2026-01-01 --end 2026-05-28
ai-chain sync sec --tickers NVDA,AVGO,MRVL,MU,COHR,LITE
ai-chain sync opendart --symbols 005930,000660
ai-chain score --date 2026-05-28
ai-chain brief --date 2026-05-28 --format md
```

### 10.2 每日简报模板

```markdown
# AI 产业链风口雷达日报 - YYYY-MM-DD

## 1. 今日总判断

- 总状态：
- 产业景气分：
- A股交易确认分：
- 拥挤度：
- 风险等级：

## 2. 当前最强环节

| 排名 | 环节 | 总分 | 产业景气 | A股确认 | 拥挤度 | 结论 |
|---:|---|---:|---:|---:|---|---|

## 3. 下一潜在风口

| 环节 | 触发逻辑 | 全球地标 | A股映射 | 确认条件 | 反证 |
|---|---|---|---|---|---|

## 4. 全球核心地标变化

| 市场 | 标的 | 涨跌 | 相对强弱 | 对应环节 | 解释 |
|---|---|---:|---:|---|---|

## 5. 台湾/韩国/日本供应链验证

- 台湾月营收：
- 韩国 HBM/存储：
- 日本设备/载板：

## 6. A股映射与确认

| 环节 | 核心标的 | 二阶标的 | 涨停/趋势 | 资金确认 | 状态 |
|---|---|---|---|---|---|

## 7. 风险与反证

- 外部政策风险：
- 拥挤风险：
- A股盘面反证：
- 业绩/订单反证：

## 8. 明日观察点

1.
2.
3.
```

### 10.3 FastAPI MVP endpoints

```text
GET /health
GET /segments
GET /anchors
GET /scores/latest
GET /scores/{date}
GET /briefings/latest
GET /briefings/{date}
GET /symbols/{symbol}/mapping
GET /events/latest
```

---

## 11. 仓库结构

Codex 应按以下结构创建项目：

```text
ai-chain-radar/
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
│   ├── chains/
│   │   └── segments.yml
│   └── universe/
│       ├── global_anchors.yml
│       └── a_share_seed.yml
├── data/
│   ├── raw/
│   ├── processed/
│   ├── warehouse/
│   └── briefings/
├── docs/
│   ├── AI_CHAIN_RADAR_ARCHITECTURE_EXECUTION_PLAN.md
│   ├── DATA_SOURCES.md
│   ├── SCORING_MODEL.md
│   └── OPERATIONS.md
├── src/
│   └── ai_chain_radar/
│       ├── __init__.py
│       ├── cli.py
│       ├── settings.py
│       ├── logging.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── duckdb.py
│       │   ├── schema.sql
│       │   └── repository.py
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── tushare_adapter.py
│       │   ├── finmind_adapter.py
│       │   ├── sec_adapter.py
│       │   ├── opendart_adapter.py
│       │   ├── jquants_adapter.py
│       │   ├── fred_adapter.py
│       │   └── dbnomics_adapter.py
│       ├── taxonomy/
│       │   ├── __init__.py
│       │   ├── segments.py
│       │   ├── entity_resolver.py
│       │   └── mapping.py
│       ├── features/
│       │   ├── __init__.py
│       │   ├── relative_strength.py
│       │   ├── revenue_trend.py
│       │   ├── keyword_signal.py
│       │   ├── market_confirmation.py
│       │   └── crowding.py
│       ├── scoring/
│       │   ├── __init__.py
│       │   ├── global_anchor_score.py
│       │   ├── bottleneck_score.py
│       │   ├── mapping_score.py
│       │   ├── trading_confirmation_score.py
│       │   ├── risk_score.py
│       │   └── opportunity_score.py
│       ├── briefing/
│       │   ├── __init__.py
│       │   ├── renderer.py
│       │   └── templates/
│       │       └── daily_briefing.md.j2
│       └── api/
│           ├── __init__.py
│           └── app.py
└── tests/
    ├── fixtures/
    ├── test_settings.py
    ├── test_schema.py
    ├── test_scoring.py
    ├── test_briefing.py
    └── test_sources_offline.py
```

---

## 12. 环境变量

`.env.example` 必须包含：

```bash
# Core
AI_CHAIN_ENV=local
AI_CHAIN_DB_PATH=data/warehouse/ai_chain.duckdb
AI_CHAIN_TIMEZONE=Asia/Shanghai

# Tushare
TUSHARE_TOKEN=

# FinMind
FINMIND_TOKEN=

# SEC
SEC_USER_AGENT="your-company your-email@example.com"

# OpenDART
OPENDART_API_KEY=

# J-Quants
JQUANTS_EMAIL=
JQUANTS_PASSWORD=
JQUANTS_REFRESH_TOKEN=

# FRED
FRED_API_KEY=

# Optional
OPENAI_API_KEY=
FMP_API_KEY=
TIINGO_API_KEY=
POLYGON_API_KEY=
```

规则：

```text
1. 不允许在代码、测试、日志、简报中输出 token。
2. 无 token 时，adapter 必须 graceful skip，并提示如何配置。
3. 测试默认使用 fixtures，不访问真实网络。
```

---

## 13. 里程碑与验收标准

### M0：仓库骨架

任务：

```text
1. 创建 pyproject.toml
2. 创建 src/ai_chain_radar 包
3. 创建 CLI 入口
4. 创建 settings loader
5. 创建 schema.sql
6. 创建 pytest/ruff/mypy 基础配置
```

验收：

```bash
uv run pytest
uv run ruff check .
uv run ai-chain --help
```

### M1：DuckDB 与数据源运行日志

任务：

```text
1. init-db 创建所有核心表
2. source_run_log 写入
3. repository 封装 upsert
4. 数据库路径可配置
```

验收：

```bash
uv run ai-chain init-db
```

能够生成 `data/warehouse/ai_chain.duckdb`。

### M2：Tushare 内场确认层

任务：

```text
1. Tushare adapter
2. 拉取 stock_basic, daily, daily_basic, fina_mainbz, anns_d, research_report
3. 拉取 limit_list_d, top_list, top_inst, moneyflow, margin_detail
4. 标准化入库
```

验收：

```bash
uv run ai-chain sync tushare --date 2026-05-28 --dry-run
uv run ai-chain sync tushare --date 2026-05-28
```

无 token 时应跳过并说明；有 token 时写入表。

### M3：Taxonomy 与 A股映射初版

任务：

```text
1. 写 configs/chains/segments.yml
2. 写 configs/universe/global_anchors.yml
3. 写 configs/universe/a_share_seed.yml
4. 建 a_share_chain_mapping upsert
5. 实现 mapping_score
```

验收：

```bash
uv run ai-chain load-taxonomy
uv run ai-chain show segments
```

### M4：台湾 FinMind MVP

任务：

```text
1. FinMind adapter
2. 拉 TaiwanStockPrice
3. 拉 TaiwanStockMonthRevenue
4. 标准化 taiwan_monthly_revenue
5. 计算月营收 MoM/YoY 趋势
```

验收：

```bash
uv run ai-chain sync finmind --start 2026-01-01 --end 2026-05-28
```

### M5：美国 SEC MVP

任务：

```text
1. SEC 官方 API adapter
2. EdgarTools 可选解析
3. 拉 submissions/companyfacts
4. 解析 filing metadata
5. 对 10-K/10-Q/8-K 做关键词抽取
```

验收：

```bash
uv run ai-chain sync sec --tickers NVDA,AVGO,MRVL,MU
```

### M6：韩国 OpenDART MVP

任务：

```text
1. OpenDART adapter
2. OpenDartReader 可作为辅助
3. 拉 Samsung / SK hynix 披露
4. 关键词抽取
```

验收：

```bash
uv run ai-chain sync opendart --symbols 005930,000660
```

### M7：评分模型 MVP

任务：

```text
1. global_anchor_score
2. bottleneck_score 初版
3. mapping_score
4. trading_confirmation_score
5. opportunity_score
6. 输出 theme_opportunity_score
```

验收：

```bash
uv run ai-chain score --date 2026-05-28
```

生成 5 条主线评分。

### M8：日报生成

任务：

```text
1. Jinja2 模板
2. Markdown 日报
3. evidence_json
4. invalid_conditions_json
```

验收：

```bash
uv run ai-chain brief --date 2026-05-28 --format md
```

生成 `data/briefings/YYYY-MM-DD.md`。

### M9：FastAPI 只读服务

任务：

```text
1. /health
2. /scores/latest
3. /briefings/latest
4. /segments
5. /anchors
```

验收：

```bash
uv run uvicorn ai_chain_radar.api.app:app --reload
```

---

## 14. Codex 执行顺序

Codex 应严格按以下顺序推进：

```text
1. 先建仓库骨架和测试框架；
2. 再建 schema 和 repository；
3. 再实现配置、日志、CLI；
4. 再做 Tushare adapter；
5. 再做 taxonomy 和 seed 数据；
6. 再做 FinMind；
7. 再做 SEC；
8. 再做 OpenDART；
9. 再做 scoring；
10. 最后做 briefing 和 API。
```

不要一开始做 UI。第一版目标是：

```text
本地命令行可跑通数据同步、评分、日报生成。
```

---

## 15. 数据质量规则

每个 adapter 必须输出：

```text
rows_read
rows_written
started_at
ended_at
status
error_message
params_json
```

数据质量标记：

```text
ok
empty
partial
stale
schema_changed
failed
```

处理策略：

```text
empty 不等于失败；
schema_changed 必须保存原始响应并报警；
failed 不应中断其他数据源；
核心数据缺失时评分要降置信度；
所有原始文本/披露文件必须保留 raw copy。
```

---

## 16. 风险与限制

### 16.1 数据授权

```text
1. 开源库不等于数据可商用。
2. FinMind、OpenBB、pykrx、FinanceDataReader 等必须检查授权。
3. 商业化前优先替换为官方或付费源。
```

### 16.2 数据延迟

```text
月营收、财报、公告有发布时间差；
A股交易确认有盘中/盘后差；
海外行情时区不同，必须统一交易日归因。
```

### 16.3 AI 抽取风险

```text
LLM 只能做辅助抽取和摘要；
评分和结论必须由规则/模型产生；
LLM 输出不得直接写入最终结论，必须带 evidence。
```

### 16.4 交易风险

```text
系统只提供研究和风控辅助；
不承诺收益；
不输出“必涨/必买/满仓”。
```

---

## 17. 第一版种子数据

### 17.1 5 条主线

```yaml
segments:
  hbm_storage:
    name: HBM / 存储 / HBM4
    anchors: [MU, SK_hynix, Samsung_Electronics]
  cowos_advanced_packaging:
    name: CoWoS / 先进封装 / 封装材料
    anchors: [TSMC, ASE, Amkor, Ibiden, Shinko]
  optics_cpo_16t:
    name: 1.6T 光模块 / CPO / 硅光
    anchors: [COHR, LITE, AVGO, MRVL, ANET]
  pcb_connector:
    name: 高速 PCB / 低损耗 CCL / 连接器
    anchors: [Unimicron, Kinsus, Ibiden, Lotes, Fujikura]
  liquid_cooling_power:
    name: 液冷 / 数据中心电力
    anchors: [VRT, Delta, Schneider, Eaton]
```

### 17.2 A股映射初版应人工维护

不要指望第一版自动识别全部 A股公司。先人工 seed：

```text
光模块 / CPO / 硅光
光芯片 / 激光器
高速 PCB / CCL
先进封装 / 封测 / IC载板
半导体设备 / 测试设备
存储 / 模组 / DDR5 配套
液冷 / 电源 / 连接器 / 电力设备
```

---

## 18. 简报结论格式要求

每个方向必须输出：

```text
方向：
阶段：
最终分：
产业景气分：
A股映射纯度分：
A股交易确认分：
拥挤度：
核心证据：
主要反证：
确认条件：
失效条件：
A股映射：
全球地标：
结论：
```

示例：

```text
方向：HBM 设备 / 测试
阶段：预热
最终分：68
产业景气分：91
A股映射纯度分：72
A股交易确认分：48
拥挤度：中

结论：
产业强，但 A股尚未全面确认。列入高优先观察池，不追高。

确认条件：
1. 韩国 HBM 设备股继续强于 KOSPI；
2. A股测试/封测/设备标的放量突破；
3. 研报或公告出现 HBM4、先进封装、测试订单等证据；
4. 板块从单股异动扩散为多股共振。

失效条件：
1. 海外 HBM 锚点转弱；
2. A股冲高回落且无成交承接；
3. 财报显示相关业务收入占比过低；
4. 出口管制导致订单或客户预期下修。
```

---

## 19. 近期最小可行目标

第一版完成后，应该可以每天生成：

```text
1. 全球 AI 链隔夜变化
2. 五条主线评分
3. 台湾/韩国/美国关键证据
4. A股映射确认
5. 下一潜在风口
6. 风险与反证
```

第一版不需要完美，但必须形成闭环：

```text
数据进来 → 标准化 → 映射 → 评分 → 简报 → 可追溯证据
```

---

## 20. 给 Codex 的高层指令

```text
你是本项目的自主工程 Agent。
优先完成可运行的 MVP，而不是一次性设计完美系统。
当 API key 缺失时，用 fixtures 和 dry-run 完成接口、schema、测试。
任何数据源接入都必须可替换、可缓存、可追溯。
任何评分都必须可解释。
任何失败都必须记录到 source_run_log。
不要在日志、测试、文档中泄露 token。
每完成一个里程碑，更新 README 和 AGENTS.md 中的进度。
```
