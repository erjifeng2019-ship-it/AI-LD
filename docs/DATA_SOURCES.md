# DATA_SOURCES

## Tushare
- 用途：A 股/港股确认层（行情、资金、公告、研报、评级）
- Env：`TUSHARE_TOKEN`
- 主要 dataset：
  - `stock_basic`, `stock_company`
  - `daily`, `daily_basic`, `limit_list_d`, `top_list`, `top_inst`, `moneyflow`, `margin_detail`, `hk_daily`
  - `anns_d`, `research_report`, `report_rc`
- 行为：
  - 支持 `--dry-run`
  - 默认 cache-first，支持 `--no-prefer-cache` 强制真网刷新
- 限制：
  - `fina_mainbz` / `income` / `fina_indicator` / `hk_mins` 在 MVP 批量模式为 `skipped`

## FinMind
- 用途：台湾链条价格、月营收、机构买卖
- Env：`FINMIND_TOKEN`（可尝试公共额度）
- 主要 dataset：
  - `TaiwanStockPrice`
  - `TaiwanStockMonthRevenue`
  - `TaiwanStockFinancialStatements`
  - `TaiwanStockInstitutionalInvestorsBuySell`
- 真网接口：`https://api.finmindtrade.com/api/v4/data`
- 结构化落表：
  - `global_anchor_price_daily`
  - `taiwan_monthly_revenue`
  - `taiwan_institutional_flow`

## SEC
- 用途：美股披露 + 财务事实
- Env：`SEC_USER_AGENT`（必填）
- 主要 endpoint：
  - `https://www.sec.gov/files/company_tickers.json`
  - `https://data.sec.gov/submissions/CIK*.json`
  - `https://data.sec.gov/api/xbrl/companyfacts/CIK*.json`
- 行为：
  - 内置最小间隔 rate limiter
  - 支持 gzip 响应解码
- 结构化落表：
  - `us_sec_filing_event`
  - `us_sec_company_fact`

## OpenDART
- 用途：韩国披露（Samsung / SK hynix 为默认 seed）
- Env：`OPENDART_API_KEY`
- 主要 endpoint：
  - `corpCode.xml`（企业代码主数据）
  - `list.json`（披露列表）
- 结构化落表：
  - `korea_corp_code_master`
  - `korea_disclosure_event`

## Seed / Manual
- A股映射种子：`data/seeds/AI_semiconductor_A_share_mapping_v1.csv`（或 `.xlsx`）
- 导入命令：`ai-chain import mapping --file <path>`
- 版本表：`a_share_chain_mapping_version`
- 历史表：`a_share_chain_mapping_history`

## Evidence Registry
- 证据表：`evidence_registry`
- 证据抽取：`ai-chain extract evidence --date YYYY-MM-DD`
- 人工补录：`ai-chain evidence add --claim ... --segment ...`

## Counter Evidence Rules
- 规则表：`counter_evidence_rule`
- 用途：以 `condition_expr` 对 segment 评分指标做反证命中判定。
- 生效位置：
  - 评分阶段写入 `theme_opportunity_score.invalid_conditions_json`
  - 命中后对 `risk_score/final_score` 施加保守惩罚
  - 日报风险区自动聚合并展示命中标签
