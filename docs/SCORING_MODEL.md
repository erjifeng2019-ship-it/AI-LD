# SCORING_MODEL

总分（0-100）默认权重：

- `global_anchor_score`: 20%
- `bottleneck_score`: 20%
- `earnings_order_price_score`: 15%
- `a_share_mapping_score`: 15%
- `a_share_confirmation_score`: 20%
- `risk_adjustment`: 10%（可负分）

每个 scorer 输出：
- `score`
- `confidence`
- `evidence`
- `warnings`

