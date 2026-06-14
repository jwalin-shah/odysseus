"""Vampire number detection.

A *vampire number* is a natural number ``v`` with an even number of
digits (2k) that can be factored into two integers ``x`` and ``y`` (the
*fangs*), each with ``k`` digits, such that:

  1. ``v = x * y``
  2. ``x`` and ``y`` are not both ending in 0
  3. The multiset of digits of ``v`` is equal to the multiset of digits
     of ``x`` and ``y`` combined.

The smallest vampire number is ``1260 = 21 * 60``.
"""

import math


def vampire_number(n):
    """Return the fangs ``(x, y)`` of vampire number ``n``, or ``None``.

    Parameters
    ----------
    n : int
        Candidate number.  Must be a positive integer with an even
        number of digits.

    Returns
    -------
    tuple[int, int] or None
        A 2-tuple ``(x, y)`` with ``x <= y`` representing the fangs, or
        ``None`` if ``n`` is not a vampire number (or the input is
        invalid).

    Examples
    --------
    >>> vampire_number(1260)
    (21, 60)
    >>> vampire_number(1395)
    (15, 93)
    >>> vampire_number(6880)
    (80, 86)
    >>> vampire_number(1255) is None
    True
    """
    # Reject non-integers.  Booleans are a subclass of ``int`` in Python
    # so we explicitly exclude them as well to keep the API strict.
    if not isinstance(n, int) or isinstance(n, bool):
        return None
    if n <= 0:
        return None

    s = str(n)
    length = len(s)

    # A vampire number must have an even number of digits.
    if length % 2 != 0:
        return None

    k = length // 2
    target_digits = sorted(s)

    # The smaller fang has exactly ``k`` digits (no leading zeros) and
    # is at most ``sqrt(n)``.
    start = 10 ** (k - 1)
    end = math.isqrt(n)

    for i in range(start, end + 1):
        if n % i != 0:
            continue

        j = n // i

        # Both fangs must have exactly ``k`` digits.
        if j < 10 ** (k - 1) or j >= 10 ** k:
            continue

        # Fangs may not both end in 0.
        if i % 10 == 0 and j % 10 == 0:
            continue

        # The multiset of digits of the fangs must equal the multiset
        # of digits of the original number.
        if sorted(str(i) + str(j)) == target_digits:
            return (i, j)

    return None