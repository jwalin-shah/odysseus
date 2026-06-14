"""
char_frequency_signature_grouper.py
===================================

Provides :func:`char_frequency_signature_grouper`, a small utility that
groups a collection of strings by their character frequency signature.

Two strings share a signature if and only if they are anagrams of one
another (i.e. they contain exactly the same characters with the same
multiplicities).  The grouping preserves the original order of the
input within each group.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List, Tuple

__all__ = ["char_frequency_signature_grouper"]

# A signature is a sorted tuple of ``(character, count)`` pairs.  This
# form is fully hashable and order-independent, which makes it ideal
# as a dictionary key.
Signature = Tuple[Tuple[str, int], ...]


def _signature(text: str) -> Signature:
    """Return the character frequency signature of *text*.

    Parameters
    ----------
    text : str
        The string whose signature should be computed.

    Returns
    -------
    Signature
        A hashable, order-independent representation of *text*.

    Raises
    ------
    TypeError
        If *text* is not a :class:`str`.
    """
    if not isinstance(text, str):
        raise TypeError(
            "char_frequency_signature_grouper only accepts string "
            f"elements, got {type(text).__name__}"
        )
    return tuple(sorted(Counter(text).items()))


def char_frequency_signature_grouper(
    strings: Iterable[str],
) -> Dict[Signature, List[str]]:
    """Group *strings* by their character frequency signature.

    Parameters
    ----------
    strings : Iterable[str]
        The strings to group.  Any iterable is accepted; the input
        order is preserved within each resulting group.

    Returns
    -------
    dict
        A mapping from each unique signature to the list of input
        strings (in original order) that produced it.  An empty input
        yields an empty dictionary.

    Examples
    --------
    >>> result = char_frequency_signature_grouper(
    ...     ["abc", "bca", "xyz", "aab", "baa"]
    ... )
    >>> sorted(sorted(g) for g in result.values())
    [['aab', 'baa'], ['abc', 'bca'], ['xyz']]
    """
    # Materialise the iterable once so the input order is captured and
    # so we can iterate over it safely (works for generators, etc.).
    items: List[str] = list(strings)

    groups: Dict[Signature, List[str]] = {}
    for text in items:
        sig = _signature(text)
        groups.setdefault(sig, []).append(text)
    return groups