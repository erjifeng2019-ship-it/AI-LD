from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pandas as pd

from ai_chain_radar.db.repository import Repository


def run_signal_review(repo: Repository, review_date: str, lookback: int = 10) -> int:
    scores = repo.query_dataframe(
        """
        SELECT score_date, segment, stage, final_score
        FROM theme_opportunity_score
        WHERE score_date <= ?
        ORDER BY score_date DESC
        LIMIT ?
        """,
        [review_date, max(1, lookback)],
    )
    if scores.empty:
        return 0

    by_seg_day = _segment_daily_returns(repo)
    if by_seg_day.empty:
        return 0

    out_rows = []
    now = datetime.now(UTC).replace(tzinfo=None)
    for row in scores.itertuples(index=False):
        signal_date = pd.to_datetime(row.score_date)
        seg = str(row.segment)
        seg_df = by_seg_day[by_seg_day["segment"] == seg].sort_values("trade_date")
        if seg_df.empty:
            continue

        f1 = _forward(seg_df, signal_date, 1)
        f3 = _forward(seg_df, signal_date, 3)
        f5 = _forward(seg_df, signal_date, 5)
        f10 = _forward(seg_df, signal_date, 10)
        drawdown = float(min(0.0, min(f1, f3, f5, f10)))
        score_val = float(row.final_score)
        confirmed = f3 > 0.0
        false_positive = bool(score_val >= 70.0 and not confirmed)
        false_negative = bool(score_val < 55.0 and confirmed)

        out_rows.append(
            {
                "review_id": f"rv_{uuid4().hex[:12]}",
                "signal_date": signal_date.date().isoformat(),
                "review_date": review_date,
                "segment": seg,
                "original_stage": row.stage,
                "original_score": score_val,
                "forward_return_1d": f1,
                "forward_return_3d": f3,
                "forward_return_5d": f5,
                "forward_return_10d": f10,
                "max_drawdown": drawdown,
                "was_confirmed": confirmed,
                "was_false_positive": false_positive,
                "was_false_negative": false_negative,
                "review_comment": _comment(confirmed, false_positive, false_negative),
                "created_at": now,
            }
        )

    if not out_rows:
        return 0
    out_df = pd.DataFrame(out_rows)
    return repo.upsert_dataframe("signal_review_result", out_df, keys=["review_id"])


def _segment_daily_returns(repo: Repository) -> pd.DataFrame:
    seg_daily = repo.query_dataframe(
        """
        SELECT trade_date, segment, segment_return_1d AS avg_pct
        FROM segment_market_confirmation_daily
        """
    )
    if not seg_daily.empty:
        seg_daily["trade_date"] = pd.to_datetime(seg_daily["trade_date"])
        return seg_daily

    fallback = repo.query_dataframe(
        """
        SELECT trade_date, segment, avg(coalesce(pct_chg, 0.0)) AS avg_pct
        FROM a_share_market_confirmation
        GROUP BY trade_date, segment
        """
    )
    if fallback.empty:
        return fallback
    fallback["trade_date"] = pd.to_datetime(fallback["trade_date"])
    return fallback


def _forward(seg_data: pd.DataFrame, start_date: pd.Timestamp, days: int) -> float:
    mask = (seg_data["trade_date"] > start_date) & (
        seg_data["trade_date"] <= start_date + timedelta(days=days)
    )
    window = seg_data[mask]["avg_pct"]
    return float(window.mean()) if not window.empty else 0.0


def _comment(confirmed: bool, false_positive: bool, false_negative: bool) -> str:
    if false_positive:
        return "false_positive"
    if false_negative:
        return "false_negative"
    if confirmed:
        return "confirmed"
    return "not_confirmed"

