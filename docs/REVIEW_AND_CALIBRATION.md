# REVIEW_AND_CALIBRATION

## 复盘命令

```bash
uv run ai-chain review --date YYYY-MM-DD --lookback 10
```

## 当前复盘输出

- `signal_review_result.forward_return_1d`
- `signal_review_result.forward_return_3d`
- `signal_review_result.forward_return_5d`
- `signal_review_result.forward_return_10d`
- `signal_review_result.max_drawdown`
- `signal_review_result.was_confirmed`
- `signal_review_result.was_false_positive`
- `signal_review_result.was_false_negative`
- `signal_review_summary.precision/recall`

## 计划增强

- [x] 增加按 segment 的 precision/recall 聚合（`signal_review_summary`）
- [x] 将复盘摘要自动注入简报
- [x] 评分阶段接入 `counter_evidence_rule` 命中结果，并在简报风险区展示动态反证标签
