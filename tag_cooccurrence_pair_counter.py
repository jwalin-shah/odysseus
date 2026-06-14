"""Count unordered co-occurring tag pairs across multiple tag collections.

A "tag collection" is any iterable of hashable items (typically strings)
representing the tags assigned to a single context -- for example, the
tags on a single blog post, the skills listed on a single resume, or
the labels attached to a single image.
"""

from collections import Counter
from itertools import combinations
from typing import Dict, Hashable, Iterable, Tuple


def tag_cooccurrence_pair_counter(
    tag_collections: Iterable[Iterable[Hashable]],
) -> Dict[Tuple[Hashable, Hashable], int]:
    """Count the number of contexts in which each unordered tag pair co-occurs.

    Parameters
    ----------
    tag_collections:
        An iterable of iterables.  Each inner iterable holds the tags of
        a single context (e.g. one document, one user, one image).

    Returns
    -------
    dict
        A mapping from each unordered tag pair -- represented as a
        2-tuple with the smaller element first -- to the number of
        contexts in which the two tags appear together.

    Notes
    -----
    * The function is order-invariant within a pair: ``('python', 'ml')``
      and ``('ml', 'python')`` refer to the same pair and therefore to
      the same key in the returned dictionary.
    * Duplicate tags inside a single collection are collapsed before
      pair generation, so a self-pair such as ``('a', 'a')`` is never
      produced.
    * ``None`` is accepted as the outer input and yields ``{}``.
    * ``None`` elements inside the outer iterable are silently skipped.
    * Collections containing unhashable items are silently skipped.

    Examples
    --------
    >>> docs = [
    ...     ['python', 'ml', 'ai'],
    ...     ['python', 'web'],
    ...     ['ml', 'ai', 'data'],
    ... ]
    >>> counter = tag_cooccurrence_pair_counter(docs)
    >>> counter[('ai', 'ml')]
    2
    >>> counter[('python', 'web')]
    1
    """
    pair_counts: Counter = Counter()

    # Defensive: a ``None`` outer input should not raise.
    if tag_collections is None:
        return {}

    for collection in tag_collections:
        # Skip ``None`` placeholders gracefully.
        if collection is None:
            continue

        # ``set`` requires hashable items; unhashable collections are
        # skipped rather than allowed to raise ``TypeError``.
        try:
            unique_tags = set(collection)
        except TypeError:
            continue

        # A collection of zero or one unique tag cannot contribute any
        # pair, so we skip it cheaply.
        if len(unique_tags) < 2:
            continue

        # ``sorted`` is used so that the resulting pair key is
        # canonical regardless of the input order: ('a', 'b') and
        # ('b', 'a') therefore map to the same bucket.
        for tag_a, tag_b in combinations(sorted(unique_tags), 2):
            pair_counts[(tag_a, tag_b)] += 1

    return dict(pair_counts)


__all__ = ["tag_cooccurrence_pair_counter"]