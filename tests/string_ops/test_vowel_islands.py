import os
import sys

import pytest

# Make the project root importable so ``from string_ops...`` works.
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from string_ops.vowel_islands import vowel_islands  # noqa: E402


def test_empty_string_returns_empty_list():
    assert vowel_islands("") == []


def test_string_with_no_vowels():
    assert vowel_islands("bcdfg") == []


def test_single_vowel_character():
    assert vowel_islands("a") == ["a"]


def test_all_vowels_form_one_island():
    assert vowel_islands("aeiou") == ["aeiou"]


def test_basic_word_hello():
    assert vowel_islands("hello") == ["e", "o"]


def test_multiple_islands_in_beautiful():
    assert vowel_islands("beautiful") == ["eau", "i", "u"]


def test_uppercase_vowels_are_recognised():
    assert vowel_islands("HELLO") == ["E", "O"]


def test_mixed_case_and_space_separator():
    assert vowel_islands("Hello World") == ["e", "o", "o"]


def test_island_at_start():
    assert vowel_islands("apple") == ["a", "e"]


def test_island_at_end():
    assert vowel_islands("banana") == ["a", "a", "a"]


def test_y_is_not_a_vowel():
    assert vowel_islands("rhythm") == []


def test_long_consecutive_vowel_run():
    assert vowel_islands("queue") == ["ueue"]


def test_punctuation_separates_islands():
    assert vowel_islands("hi!") == ["i"]


def test_digits_separate_islands():
    assert vowel_islands("a1e") == ["a", "e"]


def test_non_string_input_raises_type_error():
    with pytest.raises(TypeError):
        vowel_islands(123)

    with pytest.raises(TypeError):
        vowel_islands(None)