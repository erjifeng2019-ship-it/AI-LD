from __future__ import annotations


def relative_strength_score(pct_5d: float, bench_5d: float) -> float:
    raw = 50.0 + (pct_5d - bench_5d) * 5.0
    return max(0.0, min(100.0, raw))
