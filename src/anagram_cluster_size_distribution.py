"""Compute the distribution of anagram cluster sizes for a list of words."""

from collections import Counter, defaultdict
from typing import Dict, List


def anagram_cluster_size_distribution(words: List[str]) -> Dict[int, int]:
    """
    Group ``words`` into anagram clusters and return the distribution of
    cluster sizes.

    Two words are considered anagrams when their letters are the same up to
    permutation (case-insensitive).  Each maximal set of mutual anagrams is a
    *cluster*, and this function reports how many clusters of each size exist.

    Parameters
    ----------
    words : List[str]
        The list of words to analyse.  An empty list yields an empty dict.

    Returns
    -------
    Dict[int, int]
        Mapping ``{cluster_size: count_of_clusters_of_that_size}`` with the
        cluster sizes reported in ascending order.  Singletons (words with no
        anagram partner) are reported as size-1 clusters.

    Examples
    --------
    >>> anagram_cluster_size_distribution(["eat", "tea", "ate", "bat"])
    {1: 1, 3: 1}
    >>> anagram_cluster_size_distribution([])
    {}
    """
    if not words:
        return {}

    # An anagram signature is the word's letters in sorted order.  Words that
    # are anagrams of each other share the same signature.
    groups: Dict[str, List[str]] = defaultdict(list)
    for word in words:
        signature = "".join(sorted(word.lower()))
        groups[signature].append(word)

    # Tally how many clusters share each size and return a deterministic dict.
    size_counts = Counter(len(group) for group in groups.values())
    return dict(sorted(size_counts.items()))