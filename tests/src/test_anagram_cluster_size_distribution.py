"""Tests for ``anagram_cluster_size_distribution``."""

import os
import sys

# Allow ``from src...`` imports when the test is executed directly or via
# pytest, regardless of the working directory the user invokes it from.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.anagram_cluster_size_distribution import (  # noqa: E402
    anagram_cluster_size_distribution,
)


def test_empty_input_returns_empty_dict():
    """An empty input list should yield an empty distribution."""
    assert anagram_cluster_size_distribution([]) == {}


def test_single_word_creates_one_singleton_cluster():
    """A list with a single word should produce one cluster of size 1."""
    assert anagram_cluster_size_distribution(["hello"]) == {1: 1}


def test_two_anagrams_form_one_cluster_of_size_two():
    """``listen`` and ``silent`` are anagrams, so a single cluster of size 2."""
    assert anagram_cluster_size_distribution(["listen", "silent"]) == {2: 1}


def test_classic_three_plus_two_plus_one_distribution():
    """Mix of anagram triples, pairs, and singletons."""
    words = ["eat", "tea", "ate", "tan", "nat", "bat"]
    assert anagram_cluster_size_distribution(words) == {1: 1, 2: 1, 3: 1}


def test_words_with_no_anagrams_are_all_singletons():
    """Words sharing no letters should each form their own cluster."""
    words = ["hello", "world", "python", "anagram"]
    assert anagram_cluster_size_distribution(words) == {1: 4}


def test_all_words_are_mutual_anagrams():
    """When every word is an anagram of every other, a single cluster remains."""
    words = ["abc", "bca", "cab", "cba", "bac", "acb"]
    assert anagram_cluster_size_distribution(words) == {6: 1}


def test_case_insensitive_grouping():
    """Different capitalisations of the same letters are anagrams."""
    result = anagram_cluster_size_distribution(["Listen", "SILENT", "enlist"])
    assert result == {3: 1}


def test_duplicate_words_form_larger_cluster():
    """Repeated identical words belong to the same cluster."""
    assert anagram_cluster_size_distribution(["abc", "abc", "abc"]) == {3: 1}


def test_result_is_sorted_by_cluster_size():
    """The returned mapping should have keys in ascending order."""
    words = ["abc", "bca", "cab", "de", "ed", "f", "ghi", "ihg", "gih"]
    result = anagram_cluster_size_distribution(words)
    assert list(result.keys()) == sorted(result.keys())
    # One singleton ("f"), one pair ("de"/"ed"), and two triples.
    assert result == {1: 1, 2: 1, 3: 2}


def test_total_word_count_invariant():
    """``sum(size * count)`` across the distribution must equal input length."""
    words = ["eat", "tea", "ate", "tan", "nat", "bat", "code", "odec"]
    result = anagram_cluster_size_distribution(words)
    total = sum(size * count for size, count in result.items())
    assert total == len(words)


def test_returns_plain_dict_with_int_types():
    """The function returns a dict whose keys and values are all ints."""
    result = anagram_cluster_size_distribution(["a", "b", "c"])
    assert isinstance(result, dict)
    for key, value in result.items():
        assert isinstance(key, int)
        assert isinstance(value, int)