"""
Tests for :func:`char_frequency_signature_grouper`.
"""

from __future__ import annotations

import os
import sys

# Ensure the project root is importable regardless of how pytest is
# invoked.  This makes the test file self-contained.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
)

import pytest

from char_frequency_signature_grouper import char_frequency_signature_grouper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _values_by_member(result, member):
    """Return the group list that contains *member*, or ``None``."""
    for group in result.values():
        if member in group:
            return group
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_groups_simple_anagrams_together():
    result = char_frequency_signature_grouper(["abc", "bca", "xyz", "zyx"])
    assert len(result) == 2
    assert _values_by_member(result, "abc") == ["abc", "bca"]
    assert _values_by_member(result, "xyz") == ["xyz", "zyx"]


def test_preserves_input_order_within_groups():
    result = char_frequency_signature_grouper(["cab", "abc", "bca", "zzz"])
    assert len(result) == 2
    assert _values_by_member(result, "abc") == ["cab", "abc", "bca"]
    assert _values_by_member(result, "zzz") == ["zzz"]


def test_empty_input_returns_empty_dict():
    assert char_frequency_signature_grouper([]) == {}


def test_empty_strings_group_together():
    result = char_frequency_signature_grouper(["", "", "abc"])
    assert len(result) == 2
    assert _values_by_member(result, "") == ["", ""]
    assert _values_by_member(result, "abc") == ["abc"]


def test_different_frequencies_form_distinct_groups():
    # "aab" and "baa" share the same frequency profile (a:2, b:1);
    # "ab" has a different profile (a:1, b:1); "baba" is also different.
    result = char_frequency_signature_grouper(["aab", "ab", "baa", "baba"])
    assert len(result) == 3
    assert _values_by_member(result, "aab") == ["aab", "baa"]
    assert _values_by_member(result, "ab") == ["ab"]
    assert _values_by_member(result, "baba") == ["baba"]


def test_repeated_strings_remain_in_same_group():
    result = char_frequency_signature_grouper(["abc", "abc", "abc"])
    assert len(result) == 1
    assert next(iter(result.values())) == ["abc", "abc", "abc"]


def test_single_string_produces_single_group():
    result = char_frequency_signature_grouper(["hello"])
    assert len(result) == 1
    assert next(iter(result.values())) == ["hello"]


def test_grouping_is_case_sensitive():
    # "Abc" must not be grouped with the lowercase anagrams of "abc".
    result = char_frequency_signature_grouper(["Abc", "abc", "bca"])
    assert len(result) == 2
    assert _values_by_member(result, "Abc") == ["Abc"]
    assert _values_by_member(result, "abc") == ["abc", "bca"]


def test_strings_with_repeated_characters():
    result = char_frequency_signature_grouper(
        ["aabbbc", "bcbaab", "cccaaa", "aaabbb"]
    )
    # "aabbbc" and "bcbaab" share (a:2, b:3, c:1).
    # "cccaaa" is (a:3, c:3).
    # "aaabbb" is (a:3, b:3).
    assert len(result) == 3
    assert _values_by_member(result, "aabbbc") == ["aabbbc", "bcbaab"]
    assert _values_by_member(result, "cccaaa") == ["cccaaa"]
    assert _values_by_member(result, "aaabbb") == ["aaabbb"]


def test_non_string_element_raises_type_error():
    with pytest.raises(TypeError):
        char_frequency_signature_grouper(["abc", 123])  # type: ignore[list-item]


def test_accepts_arbitrary_iterables():
    # Generators should also work because the implementation
    # materialises the input.
    result = char_frequency_signature_grouper(s for s in ["abc", "bca"])
    assert len(result) == 1
    assert next(iter(result.values())) == ["abc", "bca"]