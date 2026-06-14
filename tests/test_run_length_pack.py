"""Tests for :mod:`run_length_pack`."""

import pytest

from run_length_pack import run_length_pack, run_length_unpack


# ---------------------------------------------------------------------------
# Basic behavior
# ---------------------------------------------------------------------------


def test_empty_string_returns_empty_list():
    assert run_length_pack("") == []


def test_none_input_returns_empty_list():
    assert run_length_pack(None) == []


def test_empty_list_returns_empty_list():
    assert run_length_pack([]) == []


def test_empty_tuple_returns_empty_list():
    assert run_length_pack(()) == []


def test_single_character_string():
    assert run_length_pack("a") == [("a", 1)]


def test_single_element_list():
    assert run_length_pack([42]) == [(42, 1)]


def test_all_same_characters():
    assert run_length_pack("aaaa") == [("a", 4)]


def test_all_different_characters():
    assert run_length_pack("abcd") == [
        ("a", 1),
        ("b", 1),
        ("c", 1),
        ("d", 1),
    ]


def test_mixed_string():
    assert run_length_pack("aaabbc") == [("a", 3), ("b", 2), ("c", 1)]


def test_alternating_runs():
    assert run_length_pack("ababab") == [
        ("a", 1),
        ("b", 1),
        ("a", 1),
        ("b", 1),
        ("a", 1),
        ("b", 1),
    ]


def test_numeric_list():
    assert run_length_pack([1, 1, 2, 3, 3, 3, 4]) == [
        (1, 2),
        (2, 1),
        (3, 3),
        (4, 1),
    ]


def test_numeric_tuple():
    assert run_length_pack((1, 1, 2, 2, 2, 3)) == [(1, 2), (2, 3), (3, 1)]


def test_whitespace_and_letters():
    assert run_length_pack("  hello  ") == [
        (" ", 2),
        ("h", 1),
        ("e", 1),
        ("l", 2),
        ("o", 1),
        (" ", 2),
    ]


def test_booleans_are_treated_as_values():
    # True/False are valid values; identity here is by ==, not by truthiness.
    assert run_length_pack([True, True, False, False, True]) == [
        (True, 2),
        (False, 2),
        (True, 1),
    ]


def test_none_can_appear_as_a_value():
    # None as an actual element (after the first non-None element is not
    # required for this case).
    assert run_length_pack([None, None, None]) == [(None, 3)]


def test_none_mixed_with_other_values():
    assert run_length_pack([None, None, 0, 0, None]) == [
        (None, 2),
        (0, 2),
        (None, 1),
    ]


# ---------------------------------------------------------------------------
# Generators and other iterables
# ---------------------------------------------------------------------------


def test_generator_input():
    def gen():
        yield from "aabbbcc"

    assert run_length_pack(gen()) == [
        ("a", 2),
        ("b", 3),
        ("c", 2),
    ]


def test_range_input():
    # Each integer in range(5) is unique, so we should get five 1-runs.
    assert run_length_pack(range(5)) == [
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 1),
    ]


# ---------------------------------------------------------------------------
# Return type / shape
# ---------------------------------------------------------------------------


def test_returns_list_of_two_tuples():
    result = run_length_pack("aabbb")
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, tuple)
        assert len(item) == 2


def test_counts_are_positive_integers():
    result = run_length_pack("aaabbbccc")
    for value, count in result:
        assert isinstance(count, int)
        assert count > 0


def test_non_iterable_raises_type_error():
    with pytest.raises(TypeError):
        run_length_pack(12345)


# ---------------------------------------------------------------------------
# Round-trip with run_length_unpack
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data",
    [
        "",
        "a",
        "aaaa",
        "abcd",
        "aaabbc",
        "ababab",
        [1, 1, 2, 3, 3, 3, 4],
        (1, 1, 2, 2, 2, 3),
        "  hello  ",
        [None, None, 0, 0, None],
    ],
)
def test_round_trip_through_unpack(data):
    assert run_length_unpack(run_length_pack(data)) == list(data)


def test_unpack_empty():
    assert run_length_unpack([]) == []


def test_unpack_rejects_negative_count():
    with pytest.raises(ValueError):
        run_length_unpack([("a", -1)])