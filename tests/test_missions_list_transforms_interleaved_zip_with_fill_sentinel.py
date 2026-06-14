"""Tests for ``missions_list_transforms_interleaved_zip_with_fill_sentinel``."""

from __future__ import annotations

import pytest

from src.missions_list_transforms_interleaved_zip_with_fill_sentinel import (
    missions_list_transforms_interleaved_zip_with_fill_sentinel,
)


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


def test_equal_length_two_lists():
    """Two equal-length lists are zipped element-wise."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        [1, 2, 3],
        [4, 5, 6],
    )
    assert result == [(1, 4), (2, 5), (3, 6)]


def test_default_fillvalue_is_none():
    """The default fillvalue is ``None``."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        [1, 2, 3],
        [4, 5],
    )
    assert result == [(1, 4), (2, 5), (3, None)]


def test_custom_fillvalue_zero():
    """A user supplied fillvalue is used to pad shorter inputs."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        [1, 2],
        [3, 4],
        [5, 6, 7],
        fillvalue=0,
    )
    assert result == [(1, 3, 5), (2, 4, 6), (0, 0, 7)]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_no_arguments_returns_empty_list():
    """Calling the function with no inputs returns ``[]``."""
    assert missions_list_transforms_interleaved_zip_with_fill_sentinel() == []


def test_empty_iterables_return_empty_list():
    """When every supplied iterable is empty, the result is empty."""
    assert (
        missions_list_transforms_interleaved_zip_with_fill_sentinel([], [], [])
        == []
    )


def test_single_list_input():
    """A single iterable produces single-element tuples."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel([1, 2, 3])
    assert result == [(1,), (2,), (3,)]


def test_first_list_is_longest():
    """The first list being longest pads the others at the end."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        [1, 2, 3, 4],
        [5, 6],
        fillvalue=-1,
    )
    assert result == [(1, 5), (2, 6), (3, -1), (4, -1)]


def test_last_list_is_longest():
    """The last list being longest pads the earlier ones at the end."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        [1, 2],
        [3, 4, 5, 6],
        fillvalue="*",
    )
    assert result == [(1, 3), (2, 4), ("*", 5), ("*", 6)]


def test_mixed_lengths_three_lists():
    """Multiple lists with different lengths are handled correctly."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        [1],
        [2, 3, 4],
        [5, 6],
        fillvalue=0,
    )
    assert result == [(1, 2, 5), (0, 3, 6), (0, 4, 0)]


def test_string_elements():
    """String elements are preserved and padded with the sentinel."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        ["a", "b"],
        ["c"],
        ["d", "e", "f"],
        fillvalue="?",
    )
    assert result == [("a", "c", "d"), ("b", "?", "e"), ("?", "?", "f")]


def test_generator_input_is_fully_consumed():
    """Generators (single-pass iterables) are handled exactly once."""
    gen = (x for x in [10, 20, 30])
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        gen,
        [1, 2],
        fillvalue=0,
    )
    assert result == [(10, 1), (20, 2), (30, 0)]


def test_fillvalue_is_dedicated_sentinel_object():
    """A unique sentinel object is faithfully preserved."""
    sentinel = object()
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        [1],
        [2, 3],
        fillvalue=sentinel,
    )
    assert len(result) == 2
    assert result[0] == (1, 2)
    # The second tuple must contain the *same* sentinel object.
    assert result[1][0] is sentinel
    assert result[1][1] == 3


def test_result_length_equals_longest_input():
    """The output length matches the longest input iterable."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        [1, 2, 3, 4, 5],
        [],
        [9, 9, 9],
        fillvalue=None,
    )
    assert len(result) == 5


def test_all_empty_except_one():
    """A single non-empty input becomes a list of single-element tuples."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        [],
        [1, 2, 3],
        [],
        fillvalue="pad",
    )
    assert result == [("pad", 1, "pad"), ("pad", 2, "pad"), ("pad", 3, "pad")]


@pytest.mark.parametrize(
    "lists, fillvalue, expected",
    [
        (
            ([1, 2, 3], [4, 5, 6]),
            None,
            [(1, 4), (2, 5), (3, 6)],
        ),
        (
            ([1, 2, 3], [4, 5]),
            None,
            [(1, 4), (2, 5), (3, None)],
        ),
        (
            ([], [1, 2]),
            -1,
            [(-1, 1), (-1, 2)],
        ),
        (
            ([1], [2], [3]),
            0,
            [(1, 2, 3)],
        ),
    ],
)
def test_parametrised_cases(lists, fillvalue, expected):
    """A handful of representative scenarios exercised via parametrisation."""
    result = missions_list_transforms_interleaved_zip_with_fill_sentinel(
        *lists, fillvalue=fillvalue
    )
    assert result == expected