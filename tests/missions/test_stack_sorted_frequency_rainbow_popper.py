import pytest
from missions.stack_sorted_frequency_rainbow_popper import (
    stack_sorted_frequency_rainbow_popper,
)


def test_empty_string():
    """An empty input should return an empty list."""
    assert stack_sorted_frequency_rainbow_popper("") == []


def test_none_input():
    """None input should be handled gracefully."""
    assert stack_sorted_frequency_rainbow_popper(None) == []


def test_single_character():
    """A single character should be returned as a single-element list."""
    assert stack_sorted_frequency_rainbow_popper("a") == ["a"]


def test_all_same_character():
    """All-same input should return the same character repeated."""
    result = stack_sorted_frequency_rainbow_popper("aaaa")
    assert result == ["a", "a", "a", "a"]


def test_string_sorted_by_frequency():
    """Characters with higher frequency should come first.

    'e' appears twice, 't' and 'r' once each.
    Between 't' and 'r' (tied at 1), 't' appears first in "tree".
    """
    result = stack_sorted_frequency_rainbow_popper("tree")
    assert result == ["e", "e", "t", "r"]


def test_tie_broken_by_first_appearance():
    """When frequencies are tied, first appearance wins.

    In "baba", 'b' and 'a' each appear twice, but 'b' appears first
    (at index 0), so 'b' should come before 'a'.
    """
    result = stack_sorted_frequency_rainbow_popper("baba")
    assert result == ["b", "b", "a", "a"]


def test_clear_frequency_order():
    """Clear frequency ordering with no ties."""
    result = stack_sorted_frequency_rainbow_popper("cccaab")
    assert result == ["c", "c", "c", "a", "a", "b"]


def test_no_duplicates_preserves_order():
    """All-unique input should preserve the original order."""
    result = stack_sorted_frequency_rainbow_popper("abcd")
    assert result == ["a", "b", "c", "d"]


def test_case_sensitive_sorting():
    """Upper and lower case are distinct characters."""
    result = stack_sorted_frequency_rainbow_popper("aAa")
    assert result == ["a", "a", "A"]


def test_three_way_tie_broken_by_first_appearance():
    """Three-way tie is broken by first appearance order."""
    result = stack_sorted_frequency_rainbow_popper("cbaabc")
    # Frequencies: c=2, b=2, a=2
    # First appearances: c=0, b=1, a=2
    # Expected order: c, c, b, b, a, a
    assert result == ["c", "c", "b", "b", "a", "a"]


def test_mixed_frequencies_and_ties():
    """Mix of clear winners and tied items."""
    result = stack_sorted_frequency_rainbow_popper("aabbbcccd")
    # Frequencies: b=3, c=3, a=2, d=1
    # First appearances: a=0, b=2, c=5, d=8
    # Order: b (3, idx 2), c (3, idx 5), a (2, idx 0), d (1, idx 8)
    assert result == ["b", "b", "b", "c", "c", "c", "a", "a", "d"]


def test_returns_list_not_string():
    """The function should return a list, not a string."""
    result = stack_sorted_frequency_rainbow_popper("aba")
    assert isinstance(result, list)
    assert result == ["a", "a", "b"]