from __future__ import annotations

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.taxonomy.mapping import load_taxonomy


def test_load_taxonomy():
    repo = Repository()
    repo.init_db()
    stats = load_taxonomy(repo)
    assert stats["segments"] > 0
    assert stats["anchors"] > 0
    df = repo.query_dataframe("SELECT count(*) AS cnt FROM ai_chain_segment")
    assert int(df.iloc[0]["cnt"]) >= 5
