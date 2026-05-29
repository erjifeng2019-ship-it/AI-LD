# NETWORK_ACCEPTANCE_TEMPLATE

用于真网回归验收留痕（有凭据环境下）。

## 验收信息
- 验收日期:
- 业务日期:
- 验收人:
- 环境:
  - Python:
  - OS:
  - AI_CHAIN_ENV:

## 凭据可用性
- TUSHARE_TOKEN: available / missing
- FINMIND_TOKEN: available / missing
- SEC_USER_AGENT: available / missing
- OPENDART_API_KEY: available / missing

## Source 完成态判断
- tushare:
- finmind:
- sec:
- opendart:

## 命令执行记录
- 建议仅保留关键命令与结果，超长日志请截断并保留定位线索。

## 关键证据
- theme_opportunity_score rows:
- signal_review_summary rows:
- briefing file:
- UI URL:
- UI screenshot:

## 结论
- 完成态判定: 通过 / 部分通过 / 不通过
- 未通过项与原因:
- 后续处理建议:

## 自动化命令（推荐）
```bash
uv run ai-chain export network-acceptance \
  --date YYYY-MM-DD \
  --target-date YYYY-MM-DD \
  --max-log-rows 40
```
