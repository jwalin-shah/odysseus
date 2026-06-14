"""Tests for src.src_anagram_cluster_size_distribution."""

import pytest

from src.src_anagram_cluster_size_distribution import (
    src_anagram_cluster_size_distribution,
)


@pytest.fixture
def sample_words():
    """A sample list containing a size-3 cluster, a size-2 cluster, and a singleton."""
    return [
        "abc", "bca", "cab",   # cluster of size 3
        "xyz", "zyx",          # cluster of size 2
        "hello",               # singleton (not a cluster)
    ]


@pytest.fixture
def result(sample_words):
    return src_anagram_cluster_size_distribution(sample_words)


def test_returned_object_supports_lookup(result):
    """The returned object must support dict-style lookup."""
    assert result[3] == 1   # one cluster of size 3 ("abc"/"bca"/"cab")


def test_cluster_of_size_three(result):
    assert result[3] == 1


def test_cluster_of_size_two(result):
    assert result[2] == 1


def test_singleton_not_included(result):
    """A single word is not considered an anagram cluster."""
    assert 1 not in result


def test_returns_dict_type():
    out = src_anagram_cluster_size_distribution(["abc", "bca"])
    assert isinstance(out, dict)


def test_empty_input_returns_empty_dict():
    assert src_anagram_cluster_size_distribution([]) == {}


def test_all_unique_words_returns_empty_dict():
    out = src_anagram_cluster_size_distribution(["abc", "def", "ghi"])
    assert out == {}


def test_all_anagrams_yields_single_cluster():
    out = src_anagram_cluster_size_distribution(["abc", "bca", "cab", "acb"])
    assert out == {4: 1}


def test_multiple_clusters_of_same_size():
    out = src_anagram_cluster_size_distribution(
        ["abc", "bca", "xyz", "zyx", "foo", "oof"]
    )
    assert out == {2: 3}


def test_mixed_distribution():
    out = src_anagram_cluster_size_distribution(
        ["abc", "bca", "cab", "xyz", "zyx", "hello"]
    )
    assert out == {3: 1, 2: 1}


def test_case_sensitive_treated_as_different():
    """Anagrams are case-sensitive; 'Abc' is not an anagram of 'abc'."""
    out = src_anagram_cluster_size_distribution(["Abc", "abc"])
    assert out == {}