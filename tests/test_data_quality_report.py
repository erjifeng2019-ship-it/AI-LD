from __future__ import annotations

from datetime import UTC, datetime

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.reports.data_quality_report import build_data_quality_report
from ai_chain_radar.sources.base import SourceRequest
from ai_chain_radar.sources.tushare_adapter import TushareAdapter


def test_data_quality_report_generation() -> None:
    repo = Repository()
    repo.init_db()
    adapter = TushareAdapter(repo)
    results = adapter.sync(SourceRequest(date="2026-05-28", dry_run=True))
    for item in results:
        # Force report date to test target day.
        item.started_at = datetime(2026, 5, 28, 9, 30, 0, tzinfo=UTC).replace(tzinfo=None)
        item.ended_at = datetime(2026, 5, 28, 9, 30, 1, tzinfo=UTC).replace(tzinfo=None)
        repo.write_run_log(item)

    rows = build_data_quality_report(repo, "2026-05-28")
    assert rows > 0
    df = repo.query_dataframe("SELECT count(*) AS cnt FROM data_quality_report")
    assert int(df.iloc[0]["cnt"]) > 0

