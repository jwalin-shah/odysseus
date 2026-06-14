"""Tests for :func:`search.find_first_occurrence.find_first_occurrence`."""

import pytest

from search.find_first_occurrence import find_first_occurrence


# ---------------------------------------------------------------------------
# String haystack / string needle
# ---------------------------------------------------------------------------

def test_substring_in_string_basic():
    """A simple substring should be located at the expected index."""
    assert find_first_occurrence("hello world", "world") == 6


def test_substring_in_string_at_start():
    """A substring matching the very beginning should return 0."""
    assert find_first_occurrence("hello world", "hello") == 0


def test_substring_in_string_not_found():
    """A missing substring must return -1."""
    assert find_first_occurrence("hello world", "xyz") == -1


def test_substring_in_string_case_sensitive():
    """The search must be case sensitive, matching str.find semantics."""
    assert find_first_occurrence("Hello", "hello") == -1
    assert find_first_occurrence("Hello", "Hello") == 0


def test_substring_returns_first_occurrence():
    """When the pattern appears multiple times, the *first* index is returned."""
    assert find_first_occurrence("ababab", "ab") == 0
    assert find_first_occurrence("ababab", "ba") == 1


def test_substring_overlapping_patterns():
    """Overlapping occurrences still return the earliest start index."""
    assert find_first_occurrence("aaaa", "aa") == 0
    assert find_first_occurrence("abababab", "abab") == 0


def test_substring_full_match():
    """A needle equal to the haystack returns 0."""
    assert find_first_occurrence("hello", "hello") == 0


def test_substring_single_character():
    """Single character look-ups work as expected."""
    assert find_first_occurrence("abc", "b") == 1
    assert find_first_occurrence("abc", "z") == -1


# ---------------------------------------------------------------------------
# List / tuple haystack
# ---------------------------------------------------------------------------

def test_subsequence_in_list_basic():
    """A sub-list inside a list is located correctly."""
    assert find_first_occurrence([1, 2, 3, 4, 5], [2, 3]) == 1


def test_subsequence_in_list_not_found():
    """A missing sub-list returns -1."""
    assert find_first_occurrence([1, 2, 3, 4, 5], [6, 7]) == -1


def test_subsequence_in_list_full_match():
    """An exact-match sub-list returns 0."""
    assert find_first_occurrence([1, 2, 3], [1, 2, 3]) == 0


def test_subsequence_in_list_returns_first():
    """The earliest matching position is returned for repeated patterns."""
    assert find_first_occurrence([1, 2, 1, 2, 1, 2], [1, 2]) == 0
    assert find_first_occurrence([1, 2, 1, 2, 1, 2], [2, 1]) == 1


def test_subsequence_in_tuple():
    """Tuples should be accepted in place of lists."""
    assert find_first_occurrence((1, 2, 3, 2, 3), (2, 3)) == 1
    assert find_first_occurrence((1, 2, 3), (4, 5)) == -1


def test_subsequence_in_list_of_strings():
    """Searching for a sub-list of strings works as well."""
    assert find_first_occurrence(
        ["a", "b", "c", "d"], ["b", "c"]
    ) == 1


# ---------------------------------------------------------------------------
# Edge cases - empty inputs, mismatched lengths
# ---------------------------------------------------------------------------

def test_empty_needle_in_string_returns_zero():
    """An empty needle is found at position 0 (matches str.find)."""
    assert find_first_occurrence("hello", "") == 0


def test_empty_needle_in_list_returns_zero():
    """An empty needle is found at position 0 for sequences too."""
    assert find_first_occurrence([1, 2, 3], []) == 0
    assert find_first_occurrence([], []) == 0


def test_empty_haystack_with_non_empty_needle_returns_negative_one():
    """An empty haystack can never contain a non-empty needle."""
    assert find_first_occurrence("", "hello") == -1
    assert find_first_occurrence([], [1]) == -1


def test_needle_longer_than_haystack_returns_negative_one():
    """If the needle is longer than the haystack there is no match."""
    assert find_first_occurrence("hi", "hello") == -1
    assert find_first_occurrence([1], [1, 2]) == -1
    assert find_first_occurrence("", "") == 0  # both empty -> found at 0


def test_non_string_non_sequence_raises_type_error():
    """Inputs that do not support ``len`` should raise ``TypeError``."""
    with pytest.raises(TypeError):
        find_first_occurrence(123, 1)


# ---------------------------------------------------------------------------
# Consistency checks - behaviour matches str.find / list.index fallback
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "haystack, needle, expected",
    [
        ("abcabcabc", "abc", 0),
        ("abcabcabc", "bca", 1),
        ("abcabcabc", "cab", 2),
        ("abcabcabc", "abcd", -1),
        ("", "a", -1),
        ("a", "", 0),
    ],
)
def test_string_behaviour_matches_str_find(haystack, needle, expected):
    """The function's results on strings should mirror ``str.find``."""
    assert find_first_occurrence(haystack, needle) == expected


@pytest.mark.parametrize(
    "haystack, needle, expected",
    [
        ([1, 2, 3, 1, 2, 3], [1, 2], 0),
        ([1, 2, 3, 1, 2, 3], [2, 3], 1),
        ([1, 2, 3, 1, 2, 3], [3, 1], 2),
        ([1, 2, 3], [1, 2, 3, 4], -1),
        ([], [1], -1),
        ([1, 2, 3], [], 0),
    ],
)
def test_list_behaviour_is_consistent(haystack, needle, expected):
    """The function's results on lists should match a manual search."""
    assert find_first_occurrence(haystack, needle) == expected