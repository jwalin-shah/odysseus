"""Tests for missions_negation_of_alternating_slice_transformer."""

import pytest

from src.missions_negation_of_alternating_slice_transformer import (
    missions_negation_of_alternating_slice_transformer,
)


def test_empty_list_returns_empty_list():
    assert missions_negation_of_alternating_slice_transformer([]) == []


def test_single_element_is_negated():
    assert missions_negation_of_alternating_slice_transformer([5]) == [-5]


def test_two_elements_first_negated_second_unchanged():
    assert missions_negation_of_alternating_slice_transformer([1, 2]) == [-1, 2]


def test_four_elements_alternating_negation():
    assert (
        missions_negation_of_alternating_slice_transformer([1, 2, 3, 4])
        == [-1, 2, -3, 4]
    )


def test_five_elements_alternating_negation():
    assert (
        missions_negation_of_alternating_slice_transformer(
            [10, 20, 30, 40, 50]
        )
        == [-10, 20, -30, 40, -50]
    )


def test_floats_are_handled():
    result = missions_negation_of_alternating_slice_transformer(
        [1.5, 2.5, 3.5]
    )
    assert result == [-1.5, 2.5, -3.5]


def test_negative_values_are_flipped_to_positive():
    result = missions_negation_of_alternating_slice_transformer(
        [-1, -2, -3, -4]
    )
    assert result == [1, -2, 3, -4]


def test_mixed_int_and_float():
    result = missions_negation_of_alternating_slice_transformer(
        [1, 2.5, 3, 4.5]
    )
    assert result == [-1, 2.5, -3, 4.5]


def test_zero_values_remain_zero():
    result = missions_negation_of_alternating_slice_transformer(
        [0, 0, 0, 0]
    )
    assert result == [0, 0, 0, 0]


def test_tuple_input_is_supported():
    result = missions_negation_of_alternating_slice_transformer(
        (1, 2, 3, 4)
    )
    assert result == [-1, 2, -3, 4]


def test_range_input_is_supported():
    result = missions_negation_of_alternating_slice_transformer(range(5))
    assert result == [0, 1, -2, 3, -4]


def test_original_input_is_not_mutated():
    data = [1, 2, 3, 4]
    snapshot = list(data)
    result = missions_negation_of_alternating_slice_transformer(data)
    assert data == snapshot
    assert result == [-1, 2, -3, 4]
    assert result is not data


def test_string_element_raises_type_error():
    with pytest.raises(TypeError):
        missions_negation_of_alternating_slice_transformer([1, "two", 3])


def test_non_numeric_element_raises_type_error():
    with pytest.raises(TypeError):
        missions_negation_of_alternating_slice_transformer([1, 2, "three"])


def test_none_element_raises_type_error():
    with pytest.raises(TypeError):
        missions_negation_of_alternating_slice_transformer([1, None, 3])


def test_nested_list_element_raises_type_error():
    with pytest.raises(TypeError):
        missions_negation_of_alternating_slice_transformer([1, [2], 3])


def test_dict_element_raises_type_error():
    with pytest.raises(TypeError):
        missions_negation_of_alternating_slice_transformer([1, {"a": 2}, 3])


def test_non_iterable_input_raises_type_error():
    with pytest.raises(TypeError):
        missions_negation_of_alternating_slice_transformer(42)


def test_error_message_mentions_index():
    with pytest.raises(TypeError) as excinfo:
        missions_negation_of_alternating_slice_transformer([1, 2, "bad"])
    assert "2" in str(excinfo.value) or "index" in str(excinfo.value).lower()