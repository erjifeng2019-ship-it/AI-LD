# KNOWN_LIMITATIONS

- DuckDB 不适合多进程并发写同一数据库文件；本项目默认采用“单写串行”纪律。
- API 常驻与 CLI 写入并发时，Windows 文件锁仍可能出现短时抖动；当前通过请求级短连接与连接重试（`AI_CHAIN_DB_OPEN_RETRY_SECONDS`）缓解，但不建议并发触发多条写命令。
- `integration` 测试为条件启用；凭据缺失时会出现 `skipped`。
- XLSX 导入依赖 `openpyxl`。
- 部分全球锚点数据在无外部凭据时只能走手工导入或降级处理，评分会降低置信度。
- 复盘指标当前主要基于可得字段，尚未覆盖完整微观交易行为特征。
