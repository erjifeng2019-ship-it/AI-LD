from __future__ import annotations


def market_confirmation_score(
    leader_strength: float, breadth: float, turnover: float, flow: float
) -> float:
    raw = leader_strength * 0.35 + breadth * 0.25 + turnover * 0.2 + flow * 0.2
    return max(0.0, min(100.0, raw))
