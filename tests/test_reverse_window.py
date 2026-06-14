"""Tests for ``reverse_window``."""

from __future__ import annotations

import os
import sys

# Make the project root importable when pytest is run from any cwd.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from reverse_window import reverse_window


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

def test_basic_example_odd_length():
    assert reverse_window([1, 2, 3, 4, 5, 6, 7], 3) == [3, 2, 1, 6, 5, 4, 7]


def test_even_length_multiple_windows():
    assert reverse_window([1, 2, 3, 4, 5, 6], 3) == [3, 2, 1, 6, 5, 4]


def test_full_reverse_when_k_equals_length():
    assert reverse_window([1, 2, 3, 4, 5], 5) == [5, 4, 3, 2, 1]


def test_k_larger_than_length_reverses_everything():
    assert reverse_window([1, 2, 3], 10) == [3, 2, 1]


def test_k_equals_one_is_identity():
    assert reverse_window([1, 2, 3, 4, 5], 1) == [1, 2, 3, 4, 5]


def test_k_equals_two_pairwise_swap():
    assert reverse_window([1, 2, 3, 4, 5, 6], 2) == [2, 1, 4, 3, 6, 5]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_input_returns_empty_list():
    assert reverse_window([], 3) == []


def test_single_element():
    assert reverse_window([42], 1) == [42]


def test_single_element_k_larger():
    assert reverse_window([42], 5) == [42]


def test_string_input_returns_list_of_chars():
    assert reverse_window("abcdef", 2) == ["b", "a", "d", "c", "f", "e"]


def test_string_input_full_reverse():
    assert reverse_window("hello", 5) == ["o", "l", "l", "e", "h"]


def test_generator_input_is_consumed_correctly():
    gen = (i for i in range(6))
    assert reverse_window(gen, 2) == [1, 0, 3, 2, 5, 4]


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------

def test_k_zero_raises_value_error():
    with pytest.raises(ValueError):
        reverse_window([1, 2, 3], 0)


def test_k_negative_raises_value_error():
    with pytest.raises(ValueError):
        reverse_window([1, 2, 3], -1)


def test_k_non_integer_raises_type_error():
    with pytest.raises(TypeError):
        reverse_window([1, 2, 3], 2.0)  # type: ignore[arg-type]


def test_k_bool_raises_type_error():
    # ``True`` is an int but conceptually not a valid window size.
    with pytest.raises(TypeError):
        reverse_window([1, 2, 3], True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Mutation / return-type guarantees
# ---------------------------------------------------------------------------

def test_does_not_mutate_input_list():
    data = [1, 2, 3, 4, 5, 6]
    snapshot = data.copy()
    result = reverse_window(data, 2)
    assert data == snapshot
    assert result is not data


def test_returns_a_list():
    result = reverse_window((1, 2, 3, 4), 2)
    assert isinstance(result, list)
    assert result == [2, 1, 4, 3]


def test_handles_none_and_mixed_types():
    assert reverse_window([None, 1, "a", 2.0], 2) == [1, None, 2.0, "a"]