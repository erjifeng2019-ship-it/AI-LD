from __future__ import annotations


def keyword_score(positive_hits: int, negative_hits: int) -> float:
    raw = 50.0 + positive_hits * 8.0 - negative_hits * 10.0
    return max(0.0, min(100.0, raw))
