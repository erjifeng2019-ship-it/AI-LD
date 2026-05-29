from __future__ import annotations


def revenue_trend_score(mom: float | None, yoy: float | None) -> float:
    mom_val = mom if mom is not None else 0.0
    yoy_val = yoy if yoy is not None else 0.0
    raw = 50.0 + mom_val * 0.6 + yoy_val * 0.2
    return max(0.0, min(100.0, raw))
