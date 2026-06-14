"""Tests for :func:`search_find_first_occurrence`."""

from __future__ import annotations

import os
import sys

import pytest

# Make the ``src`` directory importable regardless of where pytest is
# invoked from.  This is the same approach used by many flat-layout
# repositories that place modules in ``src/`` and tests in ``tests/``.
_SRC_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "src")
)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from search_find_first_occurrence import search_find_first_occurrence  # noqa: E402


# ---------------------------------------------------------------------------
# Basic success cases
# ---------------------------------------------------------------------------


def test_pattern_at_start_of_text():
    assert search_find_first_occurrence("hello world", "hello") == 0


def test_pattern_in_middle_of_text():
    assert search_find_first_occurrence("hello world", "lo w") == 3


def test_pattern_at_end_of_text():
    assert search_find_first_occurrence("hello world", "world") == 6


def test_single_character_match():
    assert search_find_first_occurrence("abcdef", "c") == 2


def test_repeated_pattern_returns_first_index():
    assert search_find_first_occurrence("abcabcabc", "abc") == 0


def test_pattern_equal_to_text():
    assert search_find_first_occurrence("python", "python") == 0


# ---------------------------------------------------------------------------
# Not-found cases
# ---------------------------------------------------------------------------


def test_pattern_not_present_returns_minus_one():
    assert search_find_first_occurrence("hello world", "xyz") == -1


def test_empty_text_with_non_empty_pattern():
    assert search_find_first_occurrence("", "abc") == -1


def test_case_sensitivity_matters():
    assert search_find_first_occurrence("Hello", "hello") == -1


# ---------------------------------------------------------------------------
# Edge cases around emptiness
# ---------------------------------------------------------------------------


def test_empty_pattern_in_non_empty_text():
    assert search_find_first_occurrence("hello", "") == 0


def test_empty_pattern_in_empty_text():
    assert search_find_first_occurrence("", "") == 0


# ---------------------------------------------------------------------------
# Defensive behaviour for ``None`` and invalid types
# ---------------------------------------------------------------------------


def test_none_text_returns_minus_one():
    assert search_find_first_occurrence(None, "abc") == -1


def test_none_pattern_returns_minus_one():
    assert search_find_first_occurrence("abc", None) == -1


def test_both_none_returns_minus_one():
    assert search_find_first_occurrence(None, None) == -1


def test_non_string_text_raises_type_error():
    with pytest.raises(TypeError):
        search_find_first_occurrence(12345, "abc")  # type: ignore[arg-type]


def test_non_string_pattern_raises_type_error():
    with pytest.raises(TypeError):
        search_find_first_occurrence("abc", 12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A few additional sanity checks
# ---------------------------------------------------------------------------


def test_long_text_with_late_match():
    text = "a" * 1000 + "needle" + "b" * 1000
    assert search_find_first_occurrence(text, "needle") == 1000


def test_unicode_strings():
    assert search_find_first_occurrence("héllo wörld", "wörld") == 6
    assert search_find_first_occurrence("héllo wörld", "world") == -1