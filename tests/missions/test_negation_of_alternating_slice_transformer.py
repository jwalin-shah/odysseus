"""Tests for ``negation_of_alternating_slice_transformer``."""

import pytest

from missions.negation_of_alternating_slice_transformer import (
    negation_of_alternating_slice_transformer,
)


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

def test_two_slices_negates_first_chunk_only():
    # 8 elements, 2 slices: [1, 2, 3, 4] | [5, 6, 7, 8]
    # The first slice is negated, the second is preserved.
    result = negation_of_alternating_slice_transformer(
        [1, 2, 3, 4, 5, 6, 7, 8], num_slices=2
    )
    assert result == [-1, -2, -3, -4, 5, 6, 7, 8]


def test_four_slices_negates_alternating_chunks():
    # 8 elements, 4 slices: [1, 2] | [3, 4] | [5, 6] | [7, 8]
    # 1st and 3rd slices are negated.
    result = negation_of_alternating_slice_transformer(
        [1, 2, 3, 4, 5, 6, 7, 8], num_slices=4
    )
    assert result == [-1, -2, 3, 4, -5, -6, 7, 8]


def test_three_slices_negates_first_and_third():
    # 9 elements, 3 slices: [1, 2, 3] | [4, 5, 6] | [7, 8, 9]
    result = negation_of_alternating_slice_transformer(
        [1, 2, 3, 4, 5, 6, 7, 8, 9], num_slices=3
    )
    assert result == [-1, -2, -3, 4, 5, 6, -7, -8, -9]


def test_default_num_slices_is_two():
    # With the default of 2 slices, [1, 2, 3, 4] -> [1, 2] | [3, 4]
    assert negation_of_alternating_slice_transformer([1, 2, 3, 4]) == [-1, -2, 3, 4]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_input_returns_empty_list():
    assert negation_of_alternating_slice_transformer([]) == []
    assert negation_of_alternating_slice_transformer([], num_slices=5) == []


def test_single_element_is_negated():
    # One element, one slice -> that single slice is negated.
    assert negation_of_alternating_slice_transformer([42]) == [-42]


def test_two_elements_with_one_slice_kept_unchanged():
    # One slice covers everything, so everything is negated.
    result = negation_of_alternating_slice_transformer([10, 20], num_slices=1)
    assert result == [-10, -20]


def test_uneven_chunks_extra_elements_go_to_earlier_slices():
    # 5 elements, 2 slices: [1, 2, 3] | [4, 5] -- first slice gets the
    # remainder element.
    result = negation_of_alternating_slice_transformer(
        [1, 2, 3, 4, 5], num_slices=2
    )
    assert result == [-1, -2, -3, 4, 5]


def test_num_slices_larger_than_length_is_capped():
    # num_slices=10 is capped to len(values)=3.
    # Slices become [1] | [2] | [3] -> negate 1st and 3rd.
    result = negation_of_alternating_slice_transformer(
        [1, 2, 3], num_slices=10
    )
    assert result == [-1, 2, -3]


def test_invalid_num_slices_raises_value_error():
    with pytest.raises(ValueError):
        negation_of_alternating_slice_transformer([1, 2, 3], num_slices=0)
    with pytest.raises(ValueError):
        negation_of_alternating_slice_transformer([1, 2, 3], num_slices=-2)


def test_non_integer_num_slices_raises_type_error():
    with pytest.raises(TypeError):
        negation_of_alternating_slice_transformer([1, 2, 3], num_slices=2.0)


# ---------------------------------------------------------------------------
# Numeric / data-type behaviour
# ---------------------------------------------------------------------------

def test_floats_are_negated_correctly():
    result = negation_of_alternating_slice_transformer(
        [1.5, 2.5, 3.5, 4.5], num_slices=2
    )
    assert result == [-1.5, -2.5, 3.5, 4.5]


def test_zero_is_preserved_when_in_unnegated_slice():
    result = negation_of_alternating_slice_transformer(
        [0, 1, 2, 3], num_slices=2
    )
    assert result == [0, -1, 2, 3]


def test_input_is_not_mutated():
    original = [1, 2, 3, 4]
    snapshot = list(original)
    negation_of_alternating_slice_transformer(original, num_slices=2)
    assert original == snapshot


def test_generator_input_is_supported():
    # The function should accept any iterable, not just lists.
    gen = (i for i in range(1, 9))  # 1..8
    result = negation_of_alternating_slice_transformer(gen, num_slices=2)
    assert result == [-1, -2, -3, -4, 5, 6, 7, 8]