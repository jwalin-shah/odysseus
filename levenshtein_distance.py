"""Levenshtein (edit) distance algorithms."""
from __future__ import annotations


def levenshtein(s1: str, s2: str) -> int:
    """Wagner-Fischer DP. O(mn) time, O(min(m,n)) space."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1, 1):
        curr = [i] + [0] * len(s2)
        for j, c2 in enumerate(s2, 1):
            if c1 == c2:
                curr[j] = prev[j - 1]
            else:
                curr[j] = 1 + min(prev[j], curr[j - 1], prev[j - 1])
        prev = curr
    return prev[len(s2)]


def similarity(s1: str, s2: str) -> float:
    """0.0 (completely different) to 1.0 (identical)."""
    denom = max(len(s1), len(s2))
    if denom == 0:
        return 1.0
    return 1.0 - levenshtein(s1, s2) / denom


def closest_word(word: str, candidates: list[str]) -> str:
    """Return the candidate with the smallest edit distance to word."""
    if not candidates:
        raise ValueError("candidates must be non-empty")
    return min(candidates, key=lambda c: levenshtein(word, c))
