from __future__ import annotations


def crowding_bucket(score: float) -> str:
    if score >= 85:
        return "extreme"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"
