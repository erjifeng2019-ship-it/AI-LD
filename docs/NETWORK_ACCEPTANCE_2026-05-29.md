# NETWORK_ACCEPTANCE_2026-05-29

基于 source_run_log 与当前仓库产物的自动化验收记录。

## 验收信息

- 验收日期: 2026-05-29
- 业务日期: 2026-05-28
- 验收人: Codex
- 环境:
  - Python: 3.12.0
  - OS: Windows-11-10.0.26200-SP0
  - AI_CHAIN_ENV: local

## 凭据可用性
- TUSHARE_TOKEN: missing
- FINMIND_TOKEN: available
- SEC_USER_AGENT: available
- OPENDART_API_KEY: available

## Source 完成态判断
- finmind: credential=available, latest_status=missing, evaluation=fail
- opendart: credential=available, latest_status=missing, evaluation=fail
- sec: credential=available, latest_status=ok, evaluation=pass
- tushare: credential=missing, latest_status=ok, evaluation=acceptable_missing_credentials

## 命令执行记录（按验收日期）
- note: total rows=2, showing latest 1 rows only.
1. `sec/filings` status=ok read=11 written=11 started_at=2026-05-29 11:00:00
   - params: `{}`

## 关键证据
- theme_opportunity_score rows (2026-05-28): 1
- signal_review_summary (2026-05-28): cnt=1, avg_precision=0.8000, avg_recall=0.8000
- briefing file: exists (data/briefings/2026-05-28.md)
- UI URL: http://127.0.0.1:8000/ui

## 结论
- 完成态判定: 部分通过/需复核
- 说明: 存在失败源或关键产物缺失，请按 source_run_log 与产物检查。
