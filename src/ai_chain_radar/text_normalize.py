from __future__ import annotations


def normalize_text(value: str) -> str:
    text = str(value or "")
    if not text:
        return text
    fixed = _try_fix_gbk_utf8(text)
    if not fixed or fixed == text:
        return text
    if _readability_score(fixed) < _readability_score(text) + 2:
        return text
    return fixed


def _try_fix_gbk_utf8(text: str) -> str | None:
    try:
        return text.encode("gbk").decode("utf-8")
    except Exception:
        return None


def _readability_score(text: str) -> int:
    score = 0
    for ch in text:
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:
            score += 2
        elif ch.isascii() and (ch.isalnum() or ch in " _-:/.,()[]{}"):
            score += 1
        elif ch == "\ufffd":
            score -= 3
    return score
