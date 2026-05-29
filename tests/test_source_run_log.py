from __future__ import annotations

from datetime import UTC, datetime

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.sources.base import SyncResult


def test_write_source_run_log():
    repo = Repository()
    repo.init_db()
    result = SyncResult(
        run_id="run-1",
        source="tushare",
        dataset="daily",
        params={"date": "2026-05-28"},
        rows_read=10,
        rows_written=10,
        status="ok",
        started_at=datetime.now(UTC).replace(tzinfo=None),
        ended_at=datetime.now(UTC).replace(tzinfo=None),
    )
    repo.write_run_log(result)
    out = repo.query_dataframe("SELECT * FROM source_run_log WHERE run_id='run-1'")
    assert len(out) == 1
    assert out.iloc[0]["source"] == "tushare"
