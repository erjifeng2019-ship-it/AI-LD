from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvidenceItem:
    source: str
    message: str


@dataclass
class ScoreOutput:
    score: float
    confidence: float
    evidence: list[EvidenceItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


__all__ = ["EvidenceItem", "ScoreOutput"]
