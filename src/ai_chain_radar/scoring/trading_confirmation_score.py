from __future__ import annotations

import math
from datetime import UTC, datetime

import pandas as pd

from ai_chain_radar.db.repository import Repository
from ai_chain_radar.features.market_confirmation import market_confirmation_score
from ai_chain_radar.scoring import EvidenceItem, ScoreOutput


class TradingConfirmationScore:
    def run_segment_daily(self, repo: Repository, score_date: str, intraday: bool = False) -> int:
        segments = repo.query_dataframe(
            "SELECT segment_id FROM ai_chain_segment ORDER BY segment_id"
        )
        if segments.empty:
            return 0

        all_market_5d_df = repo.query_dataframe(
            """
            WITH last_days AS (
              SELECT DISTINCT trade_date
              FROM a_share_market_confirmation
              WHERE trade_date <= ?
              ORDER BY trade_date DESC
              LIMIT 5
            )
            SELECT avg(coalesce(pct_chg, 0.0)) AS avg_pct_5d
            FROM a_share_market_confirmation
            WHERE trade_date IN (SELECT trade_date FROM last_days)
            """,
            [score_date],
        )
        all_market_5d = (
            float(all_market_5d_df.iloc[0]["avg_pct_5d"])
            if not all_market_5d_df.empty and all_market_5d_df.iloc[0]["avg_pct_5d"] is not None
            else 0.0
        )

        rows: list[dict] = []
        now = datetime.now(UTC).replace(tzinfo=None)
        for item in segments.itertuples(index=False):
            segment = str(item.segment_id)
            day_df = repo.query_dataframe(
                """
                SELECT
                  avg(coalesce(pct_chg, 0.0)) AS segment_return_1d,
                  avg(coalesce(amount, 0.0)) AS avg_amount,
                  avg(coalesce(turnover_rate, 0.0)) AS avg_turnover_rate,
                  avg(coalesce(volume_ratio, 0.0)) AS avg_volume_ratio,
                  sum(CASE WHEN coalesce(limit_status, '') = 'limit_up'
                            OR coalesce(pct_chg, 0.0) >= 9.8 THEN 1 ELSE 0 END) AS limit_up_count,
                  sum(CASE WHEN coalesce(limit_status, '') = 'limit_up'
                            OR coalesce(pct_chg, 0.0) >= 9.8
                           THEN coalesce(amount, 0.0) ELSE 0 END) AS limit_up_amount,
                  sum(coalesce(dragon_tiger_net_buy, 0.0)) AS top_list_net_buy,
                  sum(coalesce(institution_net_buy, 0.0)) AS institution_net_buy,
                  sum(coalesce(moneyflow_score, 0.0)) AS moneyflow_large_net,
                  sum(coalesce(margin_score, 0.0)) AS margin_balance_delta
                FROM a_share_market_confirmation
                WHERE trade_date = ? AND segment = ?
                """,
                [score_date, segment],
            )
            recent_df = repo.query_dataframe(
                """
                WITH last_days AS (
                  SELECT DISTINCT trade_date
                  FROM a_share_market_confirmation
                  WHERE segment = ?
                    AND trade_date <= ?
                  ORDER BY trade_date DESC
                  LIMIT 5
                )
                SELECT avg(coalesce(pct_chg, 0.0)) AS segment_return_5d
                FROM a_share_market_confirmation
                WHERE segment = ?
                  AND trade_date IN (SELECT trade_date FROM last_days)
                """,
                [segment, score_date, segment],
            )
            core_hit_df = repo.query_dataframe(
                """
                WITH core_pool AS (
                  SELECT DISTINCT ts_code
                  FROM a_share_chain_mapping
                  WHERE segment = ?
                    AND coalesce(is_latest, TRUE) = TRUE
                    AND coalesce(is_core, FALSE) = TRUE
                ),
                core_day AS (
                  SELECT ts_code, pct_chg
                  FROM a_share_market_confirmation
                  WHERE trade_date = ?
                    AND segment = ?
                )
                SELECT
                  CASE
                    WHEN (SELECT count(*) FROM core_pool) = 0 THEN 0.0
                    ELSE cast(
                      sum(CASE WHEN coalesce(core_day.pct_chg, 0.0) > 0 THEN 1 ELSE 0 END)
                      as DOUBLE
                    )
                         / cast((SELECT count(*) FROM core_pool) as DOUBLE)
                  END AS core_pool_hit_rate
                FROM core_pool
                LEFT JOIN core_day USING (ts_code)
                """,
                [segment, score_date, segment],
            )
            segment_return_1d = _as_float(day_df, "segment_return_1d")
            segment_return_5d = _as_float(recent_df, "segment_return_5d")
            avg_turnover_rate = _as_float(day_df, "avg_turnover_rate")
            avg_volume_ratio = _as_float(day_df, "avg_volume_ratio")
            limit_up_count = int(_as_float(day_df, "limit_up_count"))
            limit_up_amount = _as_float(day_df, "limit_up_amount")
            top_list_net_buy = _as_float(day_df, "top_list_net_buy")
            institution_net_buy = _as_float(day_df, "institution_net_buy")
            moneyflow_large_net = _as_float(day_df, "moneyflow_large_net")
            margin_balance_delta = _as_float(day_df, "margin_balance_delta")
            core_pool_hit_rate = _as_float(core_hit_df, "core_pool_hit_rate")
            crowding_score = _crowding_score(
                intraday=intraday,
                avg_turnover_rate=avg_turnover_rate,
                avg_volume_ratio=avg_volume_ratio,
                limit_up_count=limit_up_count,
                limit_up_amount=limit_up_amount,
                top_list_net_buy=top_list_net_buy,
                institution_net_buy=institution_net_buy,
                moneyflow_large_net=moneyflow_large_net,
            )
            segment_vs_all_a_5d = segment_return_5d - all_market_5d

            leader = max(0.0, min(100.0, 50.0 + segment_return_1d * 8.0))
            breadth = max(0.0, min(100.0, core_pool_hit_rate * 100.0))
            turnover = max(
                0.0,
                min(100.0, 30.0 + avg_turnover_rate * 6.0 + avg_volume_ratio * 12.0),
            )
            flow = max(
                0.0,
                min(
                    100.0,
                    50.0 + (moneyflow_large_net + institution_net_buy + top_list_net_buy) / 3.0,
                ),
            )
            confirmation_score = market_confirmation_score(leader, breadth, turnover, flow)

            rows.append(
                {
                    "trade_date": score_date,
                    "segment": segment,
                    "segment_return_1d": segment_return_1d,
                    "segment_return_5d": segment_return_5d,
                    "segment_vs_all_a_5d": segment_vs_all_a_5d,
                    "core_pool_hit_rate": core_pool_hit_rate,
                    "limit_up_count": limit_up_count,
                    "limit_up_amount": limit_up_amount,
                    "top_list_net_buy": top_list_net_buy,
                    "institution_net_buy": institution_net_buy,
                    "moneyflow_large_net": moneyflow_large_net,
                    "margin_balance_delta": margin_balance_delta,
                    "turnover_zscore": avg_volume_ratio,
                    "crowding_score": crowding_score,
                    "confirmation_score": confirmation_score,
                    "stage": _stage_from_confirmation(confirmation_score),
                    "created_at": now,
                }
            )

        if not rows:
            return 0
        frame = pd.DataFrame(rows)
        return repo.upsert_dataframe(
            "segment_market_confirmation_daily",
            frame,
            keys=["trade_date", "segment"],
        )

    def score(self, repo: Repository, segment: str, score_date: str) -> ScoreOutput:
        segment_df = repo.query_dataframe(
            """
            SELECT confirmation_score, segment_return_1d, core_pool_hit_rate, turnover_zscore
            FROM segment_market_confirmation_daily
            WHERE trade_date = ? AND segment = ?
            """,
            [score_date, segment],
        )
        if not segment_df.empty:
            row = segment_df.iloc[0]
            score = float(row["confirmation_score"])
            return ScoreOutput(
                score=score,
                confidence=75.0,
                evidence=[
                    EvidenceItem(
                        source="segment_market_confirmation_daily",
                        message=f"segment_return_1d={float(row['segment_return_1d']):.2f}",
                    ),
                    EvidenceItem(
                        source="segment_market_confirmation_daily",
                        message=f"core_pool_hit_rate={float(row['core_pool_hit_rate']):.2f}",
                    ),
                    EvidenceItem(
                        source="segment_market_confirmation_daily",
                        message=f"turnover_zscore={float(row['turnover_zscore']):.2f}",
                    ),
                ],
            )

        df = repo.query_dataframe(
            """
            SELECT
              avg(coalesce(pct_chg, 0)) AS avg_pct,
              avg(coalesce(amount, 0)) AS avg_amount
            FROM a_share_market_confirmation
            WHERE trade_date = ? AND segment = ?
            """,
            [score_date, segment],
        )
        avg_pct = (
            float(df.iloc[0]["avg_pct"])
            if not df.empty and df.iloc[0]["avg_pct"] is not None
            else 0.0
        )
        avg_amount = (
            float(df.iloc[0]["avg_amount"])
            if not df.empty and df.iloc[0]["avg_amount"] is not None
            else 0.0
        )
        leader = max(0.0, min(100.0, 50.0 + avg_pct * 10))
        breadth = 50.0 if avg_amount > 0 else 20.0
        turnover = 60.0 if avg_amount > 1e8 else 35.0
        flow = 55.0 if avg_amount > 5e8 else 30.0
        score = market_confirmation_score(leader, breadth, turnover, flow)
        return ScoreOutput(
            score=score,
            confidence=70.0 if avg_amount > 0 else 35.0,
            evidence=[
                EvidenceItem(
                    source="a_share_market_confirmation", message=f"avg_pct={avg_pct:.2f}"
                ),
                EvidenceItem(
                    source="a_share_market_confirmation", message=f"avg_amount={avg_amount:.0f}"
                ),
            ],
        )


def _as_float(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    value = df.iloc[0][column]
    if value is None:
        return 0.0
    try:
        out = float(value)
        if math.isnan(out):
            return 0.0
        return out
    except (TypeError, ValueError):
        return 0.0


def _stage_from_confirmation(score: float) -> str:
    if score >= 85:
        return "main_rally"
    if score >= 70:
        return "start"
    if score >= 55:
        return "warming_up"
    if score >= 40:
        return "observe"
    return "not_started"


def _crowding_score(
    *,
    intraday: bool,
    avg_turnover_rate: float,
    avg_volume_ratio: float,
    limit_up_count: int,
    limit_up_amount: float,
    top_list_net_buy: float,
    institution_net_buy: float,
    moneyflow_large_net: float,
) -> float:
    if not intraday:
        # 保持历史分布稳定：日频模式下保守估算拥挤度。
        return max(0.0, min(100.0, 30.0 + avg_turnover_rate * 6.0 + avg_volume_ratio * 12.0))

    turnover_heat = max(0.0, min(100.0, 35.0 + avg_turnover_rate * 7.0 + avg_volume_ratio * 14.0))
    limit_heat = max(0.0, min(100.0, limit_up_count * 7.0 + limit_up_amount / 8e8 * 20.0))
    flow_heat = max(
        0.0,
        min(100.0, 50.0 + (top_list_net_buy + institution_net_buy + moneyflow_large_net) / 4.0),
    )
    return max(0.0, min(100.0, turnover_heat * 0.4 + limit_heat * 0.25 + flow_heat * 0.35))
