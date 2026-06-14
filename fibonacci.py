def fib(n: int) -> int:
    """Compute the nth Fibonacci number using O(log n) matrix exponentiation."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0
    if n == 1:
        return 1

    def mat_mult(A, B):
        return [
            [A[0][0] * B[0][0] + A[0][1] * B[1][0],
             A[0][0] * B[0][1] + A[0][1] * B[1][1]],
            [A[1][0] * B[0][0] + A[1][1] * B[1][0],
             A[1][0] * B[0][1] + A[1][1] * B[1][1]],
        ]

    def mat_pow(M, p):
        result = [[1, 0], [0, 1]]  # Identity matrix
        base = [row[:] for row in M]
        while p > 0:
            if p % 2 == 1:
                result = mat_mult(result, base)
            base = mat_mult(base, base)
            p //= 2
        return result

    M = [[1, 1], [1, 0]]
    return mat_pow(M, n)[0][1]


def fib_memo(n: int) -> int:
    """Compute the nth Fibonacci number using memoized recursion."""
    if n < 0:
        raise ValueError("n must be non-negative")
    cache = {0: 0, 1: 1}

    def helper(k):
        if k in cache:
            return cache[k]
        cache[k] = helper(k - 1) + helper(k - 2)
        return cache[k]

    return helper(n)


def fib_iter(n: int) -> int:
    """Compute the nth Fibonacci number iteratively using O(1) space."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0
    if n == 1:
        return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def fib_sequence(n: int) -> list:
    """Return the first n Fibonacci numbers as a list."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return []
    result = [0, 1]
    while len(result) < n:
        result.append(result[-1] + result[-2])
    return result[:n]


def is_fibonacci(n: int) -> bool:
    """Check if n is a Fibonacci number using the perfect square test."""
    if n < 0:
        return False
    if n == 0:
        return True

    def is_perfect_square(x):
        if x < 0:
            return False
        s = int(x ** 0.5)
        return s * s == x or (s + 1) * (s + 1) == x

    return is_perfect_square(5 * n * n + 4) or is_perfect_square(5 * n * n - 4)