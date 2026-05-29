# DAILY_WORKFLOW

## 盘后主流程（串行）
```bash
uv run ai-chain sync tushare --date <trade_date> --no-prefer-cache
uv run ai-chain extract evidence --date <trade_date>
uv run ai-chain score --date <trade_date>
uv run ai-chain review --date <trade_date> --lookback 10
uv run ai-chain brief --date <trade_date> --format md
```

## 盘前（v0.2 兼容形态）
```bash
uv run ai-chain sync tushare --date <trade_date> --events-only
uv run ai-chain extract evidence --date <trade_date>
uv run ai-chain score --date <trade_date>
uv run ai-chain brief --date <trade_date> --mode premarket --format md
```

## 盘中（v0.2 兼容形态）
```bash
uv run ai-chain sync tushare --date <trade_date> --realtime
uv run ai-chain score market-confirmation --date <trade_date> --intraday
uv run ai-chain alert --date <trade_date>
```

## 快速健康检查
```bash
uv run ai-chain db query "select source, job_name, status, started_at from source_run_log order by started_at desc limit 20"
```
