"""Evil and odious number predicates.

An evil number has an even number of 1s in its binary representation.
An odious number has an odd number of 1s in its binary representation.
"""


def _popcount(n):
    """Return the number of 1-bits in the binary representation of n."""
    if n < 0:
        raise ValueError("n must be non-negative")
    count = 0
    while n:
        count += n & 1
        n >>= 1
    return count


def is_evil(n):
    """Return True if n is an evil number (even number of 1s in binary)."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be an integer")
    if n < 0:
        raise ValueError("n must be non-negative")
    return _popcount(n) % 2 == 0


def is_odious(n):
    """Return True if n is an odious number (odd number of 1s in binary)."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be an integer")
    if n < 0:
        raise ValueError("n must be non-negative")
    return _popcount(n) % 2 == 1


def evil_check(n):
    """Return 'evil' if n is evil, 'odious' if n is odious."""
    return "evil" if is_evil(n) else "odious"


def evil_numbers(limit):
    """Return a list of evil numbers in the range [0, limit]."""
    if limit < 0:
        return []
    return [n for n in range(limit + 1) if is_evil(n)]


def odious_numbers(limit):
    """Return a list of odious numbers in the range [0, limit]."""
    if limit < 0:
        return []
    return [n for n in range(limit + 1) if is_odious(n)]


def first_n_evil(n):
    """Return the first n evil numbers (starting from 0)."""
    if n < 0:
        raise ValueError("n must be non-negative")
    result = []
    candidate = 0
    while len(result) < n:
        if is_evil(candidate):
            result.append(candidate)
        candidate += 1
    return result


def first_n_odious(n):
    """Return the first n odious numbers (starting from 1)."""
    if n < 0:
        raise ValueError("n must be non-negative")
    result = []
    candidate = 1
    while len(result) < n:
        if is_odious(candidate):
            result.append(candidate)
        candidate += 1
    return result