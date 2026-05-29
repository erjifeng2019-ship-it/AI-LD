from __future__ import annotations

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.evidence.extractor import extract_evidence_for_date
from ai_chain_radar.review.calibration import build_review_summary
from ai_chain_radar.review.signal_review import run_signal_review
from ai_chain_radar.scoring.opportunity_score import OpportunityScore
from ai_chain_radar.scoring.trading_confirmation_score import TradingConfirmationScore
from ai_chain_radar.taxonomy.mapping import load_taxonomy


def test_extract_evidence_and_review() -> None:
    repo = Repository()
    repo.init_db()
    load_taxonomy(repo)

    repo.upsert_dataframe(
        "a_share_market_confirmation",
        pd.DataFrame(
            [
                {
                    "trade_date": "2026-05-28",
                    "ts_code": "300308.SZ",
                    "segment": "optics_cpo_16t",
                    "pct_chg": 1.2,
                    "amount": 2.5e8,
                    "source": "test",
                    "ingested_at": Repository.now_ts(),
                },
                {
                    "trade_date": "2026-05-29",
                    "ts_code": "300308.SZ",
                    "segment": "optics_cpo_16t",
                    "pct_chg": 0.8,
                    "amount": 2.1e8,
                    "source": "test",
                    "ingested_at": Repository.now_ts(),
                },
            ]
        ),
        keys=["trade_date", "ts_code", "segment"],
    )

    evidence_rows = extract_evidence_for_date(repo, "2026-05-28")
    assert evidence_rows > 0
    ev_cnt = repo.query_dataframe("SELECT count(*) AS cnt FROM evidence_registry")
    assert int(ev_cnt.iloc[0]["cnt"]) > 0

    TradingConfirmationScore().run_segment_daily(repo, "2026-05-28")
    TradingConfirmationScore().run_segment_daily(repo, "2026-05-29")
    OpportunityScore().run(repo, "2026-05-28")
    review_rows = run_signal_review(repo, review_date="2026-05-29", lookback=10)
    assert review_rows > 0
    rv_cnt = repo.query_dataframe("SELECT count(*) AS cnt FROM signal_review_result")
    assert int(rv_cnt.iloc[0]["cnt"]) > 0
    summary_rows = build_review_summary(repo, "2026-05-29")
    assert summary_rows > 0
    sv_cnt = repo.query_dataframe("SELECT count(*) AS cnt FROM signal_review_summary")
    assert int(sv_cnt.iloc[0]["cnt"]) > 0
