# === lcs.py ===
"""Longest Common Subsequence algorithms."""
from __future__ import annotations


def lcs_length(s1: str, s2: str) -> int:
    """DP O(mn) time, O(min(m,n)) space."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    prev = [0] * (len(s2) + 1)
    for c1 in s1:
        curr = [0] * (len(s2) + 1)
        for j, c2 in enumerate(s2, 1):
            if c1 == c2:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(curr[j - 1], prev[j])
        prev = curr
    return prev[len(s2)]


def lcs_string(s1: str, s2: str) -> str:
    """Return one LCS string via backtracking."""
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i, c1 in enumerate(s1, 1):
        for j, c2 in enumerate(s2, 1):
            if c1 == c2:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    result: list[str] = []
    i, j = m, n
    while i > 0 and j > 0:
        if s1[i - 1] == s2[j - 1]:
            result.append(s1[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    return "".join(reversed(result))


def lcs_percent(s1: str, s2: str) -> float:
    """LCS length / max(len(s1), len(s2)), returns 0.0 for empty strings."""
    denom = max(len(s1), len(s2))
    if denom == 0:
        return 0.0
    return lcs_length(s1, s2) / denom