def levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein edit distance between two strings.

    Uses an O(len(a) * len(b)) dynamic programming table where
    dp[i][j] is the edit distance between a[:i] and b[:j].
    """
    m, n = len(a), len(b)

    # Build a (m+1) x (n+1) DP table
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Base cases: transforming empty string requires i inserts or j deletes
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    # Fill in the rest of the table
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # deletion from a
                    dp[i][j - 1],      # insertion into a
                    dp[i - 1][j - 1],  # substitution
                )

    return dp[m][n]


assert levenshtein('kitten', 'sitting') == 3
assert levenshtein('', '') == 0
