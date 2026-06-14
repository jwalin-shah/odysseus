"""Compute the distribution of anagram cluster sizes from a list of words."""

from collections import Counter, defaultdict


def src_anagram_cluster_size_distribution(words):
    """
    Compute the distribution of anagram cluster sizes.

    Words are grouped by their anagram signature (sorted characters).
    A "cluster" is a group containing two or more words that are anagrams
    of one another; singletons are not considered clusters.

    Args:
        words: An iterable of strings.

    Returns:
        A dict mapping cluster size -> number of clusters of that size.
        Singletons (size 1) are excluded from the distribution.
    """
    groups = defaultdict(list)
    for word in words:
        # Use sorted characters as the anagram signature/key.
        key = "".join(sorted(word))
        groups[key].append(word)

    # Count how many clusters exist of each size (size >= 2 only).
    cluster_sizes = Counter()
    for members in groups.values():
        size = len(members)
        if size > 1:
            cluster_sizes[size] += 1

    return dict(cluster_sizes)