from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from ai_chain_radar.db.repository import Repository


def test_upsert_dataframe():
    repo = Repository()
    repo.init_db()
    df = pd.DataFrame(
        [
            {
                "segment_id": "hbm_storage",
                "segment_name": "HBM",
                "parent_segment": "L2",
                "updated_at": datetime.now(UTC).replace(tzinfo=None),
            }
        ]
    )
    repo.upsert_dataframe("ai_chain_segment", df, keys=["segment_id"])
    out = repo.query_dataframe("SELECT * FROM ai_chain_segment WHERE segment_id='hbm_storage'")
    assert len(out) == 1
    assert out.iloc[0]["segment_name"] == "HBM"


def test_upsert_dataframe_deduplicates_by_keys():
    repo = Repository()
    repo.init_db()
    df = pd.DataFrame(
        [
            {
                "trade_date": "2026-05-28",
                "ts_code": "300308.SZ",
                "segment": "unknown",
                "pct_chg": 1.0,
                "source": "tushare",
                "ingested_at": datetime.now(UTC).replace(tzinfo=None),
            },
            {
                "trade_date": "2026-05-28",
                "ts_code": "300308.SZ",
                "segment": "unknown",
                "pct_chg": 2.0,
                "source": "tushare",
                "ingested_at": datetime.now(UTC).replace(tzinfo=None),
            },
        ]
    )
    written = repo.upsert_dataframe(
        "a_share_market_confirmation", df, keys=["trade_date", "ts_code", "segment"]
    )
    assert written == 1
    out = repo.query_dataframe(
        "SELECT pct_chg FROM a_share_market_confirmation "
        "WHERE trade_date='2026-05-28' AND ts_code='300308.SZ' AND segment='unknown'"
    )
    assert len(out) == 1
    assert out.iloc[0]["pct_chg"] == 2.0
