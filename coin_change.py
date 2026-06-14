# === coin_change.py ===
"""Coin change DP problems."""
from __future__ import annotations


def min_coins(coins: list[int], amount: int) -> int:
    """Minimum number of coins to make amount. Returns -1 if impossible."""
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    for a in range(1, amount + 1):
        for c in coins:
            if c <= a and dp[a - c] + 1 < dp[a]:
                dp[a] = dp[a - c] + 1
    return -1 if dp[amount] == float('inf') else int(dp[amount])


def coin_combinations(coins: list[int], amount: int) -> int:
    """Number of distinct ways to make amount using unlimited coins."""
    dp = [0] * (amount + 1)
    dp[0] = 1
    for c in coins:
        for a in range(c, amount + 1):
            dp[a] += dp[a - c]
    return dp[amount]


def min_coins_path(coins: list[int], amount: int) -> list[int] | None:
    """Return the actual coin list for min_coins, or None if impossible."""
    dp = [float('inf')] * (amount + 1)
    dp[0] = 0
    parent = [-1] * (amount + 1)
    for a in range(1, amount + 1):
        for c in coins:
            if c <= a and dp[a - c] + 1 < dp[a]:
                dp[a] = dp[a - c] + 1
                parent[a] = c
    if dp[amount] == float('inf'):
        return None
    path: list[int] = []
    cur = amount
    while cur > 0:
        path.append(parent[cur])
        cur -= parent[cur]
    return sorted(path)
