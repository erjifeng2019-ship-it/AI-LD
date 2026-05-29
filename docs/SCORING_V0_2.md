# SCORING_V0_2

## 总分公式

```text
final_score =
0.20 * global_anchor_score
+ 0.20 * bottleneck_score
+ 0.15 * evidence_score
+ 0.15 * mapping_score
+ 0.20 * trading_confirmation_score
+ 0.10 * risk_adjusted_score
```

## 当前实现状态

- `mapping_score`：已实现
- `bottleneck_score`：已实现（简化版）
- `trading_confirmation_score`：已实现（简化版）
- `risk_score`：已实现
- `global_anchor_score`：已实现（依赖锚点数据）
- `confidence_score`：待增强（目前分散在各 scorer）

