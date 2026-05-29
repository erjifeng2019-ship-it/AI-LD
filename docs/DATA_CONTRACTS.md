# DATA_CONTRACTS

## 关键新增表（v0.2）

- `a_share_chain_mapping_version`
- `a_share_chain_mapping_history`
- `evidence_registry`
- `signal_review_result`
- `signal_review_summary`
- `counter_evidence_rule`
- `segment_market_confirmation_daily`
- `data_quality_report`

## 导入契约（mapping）

必填字段：
- `ts_code`
- `name`
- `segment`
- `sub_segment`
- `purity_level`
- `evidence_level`

支持输入格式：
- `.csv`
- `.xlsx`（优先读取 `A股映射主表`）

## 评分与日报证据链契约

- `theme_opportunity_score.evidence_json`：
  - 评分证据数组。
  - 当证据来自 `evidence_registry` 时，条目应携带 `evidence_id` 字段。
- `daily_ai_chain_briefing.evidence_json`：
  - JSON 对象，包含：
    - `anchor_moves`: 当日锚点摘要列表
    - `evidence_refs`: 日报引用的证据列表（含 `evidence_id`）
