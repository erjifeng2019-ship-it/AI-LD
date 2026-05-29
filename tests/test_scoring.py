from __future__ import annotations

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.scoring.opportunity_score import OpportunityScore
from ai_chain_radar.scoring.trading_confirmation_score import TradingConfirmationScore
from ai_chain_radar.taxonomy.mapping import load_taxonomy


def test_scoring_pipeline():
    repo = Repository()
    repo.init_db()
    load_taxonomy(repo)
    # Seed one anchor price row for scoring date.
    repo.query_dataframe(
        """
        INSERT INTO global_anchor_price_daily (
          trade_date, symbol, market, close, pct_chg, source, ingested_at
        ) VALUES
          ('2026-05-28', 'MU', 'US', 120, 2.5, 'test', now())
        """
    )
    rows = OpportunityScore().run(repo, "2026-05-28")
    assert rows >= 5
    out = repo.query_dataframe("SELECT count(*) AS cnt FROM theme_opportunity_score")
    assert int(out.iloc[0]["cnt"]) >= 5


def test_market_confirmation_segment_daily() -> None:
    repo = Repository()
    repo.init_db()
    load_taxonomy(repo)
    repo.query_dataframe(
        """
        INSERT INTO a_share_market_confirmation (
          trade_date, ts_code, segment, pct_chg, amount,
          turnover_rate, volume_ratio, source, ingested_at
        ) VALUES
          ('2026-05-28', '300308.SZ', 'optics_cpo_16t', 2.1, 300000000, 4.2, 1.8, 'test', now())
        """
    )
    rows = TradingConfirmationScore().run_segment_daily(repo, "2026-05-28")
    assert rows > 0
    out = repo.query_dataframe(
        """
        SELECT count(*) AS cnt
        FROM segment_market_confirmation_daily
        WHERE trade_date = '2026-05-28'
        """
    )
    assert int(out.iloc[0]["cnt"]) >= 1


def test_market_confirmation_segment_daily_intraday() -> None:
    repo = Repository()
    repo.init_db()
    load_taxonomy(repo)
    repo.query_dataframe(
        """
        INSERT INTO a_share_market_confirmation (
          trade_date, ts_code, segment, pct_chg, amount,
          turnover_rate, volume_ratio, source, ingested_at,
          dragon_tiger_net_buy, institution_net_buy, moneyflow_score
        ) VALUES
          (
            '2026-05-28', '300308.SZ', 'optics_cpo_16t', 3.2, 500000000,
            5.6, 2.4, 'test', now(), 30, 25, 40
          )
        """
    )
    rows = TradingConfirmationScore().run_segment_daily(repo, "2026-05-28", intraday=True)
    assert rows > 0
    out = repo.query_dataframe(
        """
        SELECT crowding_score
        FROM segment_market_confirmation_daily
        WHERE trade_date = '2026-05-28'
          AND segment = 'optics_cpo_16t'
        """
    )
    assert float(out.iloc[0]["crowding_score"]) > 0
