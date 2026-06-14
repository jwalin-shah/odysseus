"""Tests for ``string_missions_sentence_word_reverser``."""

import os
import sys

# Make the project root importable so ``from src ...`` works regardless
# of where pytest is invoked from.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from src.string_missions_sentence_word_reverser import (
    string_missions_sentence_word_reverser,
)


def test_basic_two_word_reversal():
    assert string_missions_sentence_word_reverser("Hello World") == "World Hello"


def test_multiple_words_full_reversal():
    assert (
        string_missions_sentence_word_reverser("The quick brown fox")
        == "fox brown quick The"
    )


def test_long_sentence_reversal():
    sentence = "The quick brown fox jumps over the lazy dog"
    expected = "dog lazy the over jumps fox brown quick The"
    assert string_missions_sentence_word_reverser(sentence) == expected


def test_empty_string_returns_empty_string():
    assert string_missions_sentence_word_reverser("") == ""


def test_whitespace_only_returns_empty_string():
    assert string_missions_sentence_word_reverser("   ") == ""
    assert string_missions_sentence_word_reverser("\t\n  \r") == ""


def test_single_word_is_unchanged():
    assert string_missions_sentence_word_reverser("hello") == "hello"


def test_multiple_internal_spaces_collapse_to_single_space():
    assert (
        string_missions_sentence_word_reverser("hello   world  foo")
        == "foo world hello"
    )


def test_leading_and_trailing_spaces_are_stripped():
    assert (
        string_missions_sentence_word_reverser("   hello world   ")
        == "world hello"
    )


def test_tabs_and_newlines_act_as_separators():
    assert (
        string_missions_sentence_word_reverser("hello\tworld\nfoo bar")
        == "bar foo world hello"
    )


def test_none_input_returns_empty_string():
    assert string_missions_sentence_word_reverser(None) == ""


def test_non_string_input_returns_empty_string():
    assert string_missions_sentence_word_reverser(123) == ""
    assert string_missions_sentence_word_reverser(["hello", "world"]) == ""
    assert string_missions_sentence_word_reverser(3.14) == ""


def test_punctuation_attached_to_word_is_preserved():
    # Punctuation is part of the word, so it travels with it.
    assert (
        string_missions_sentence_word_reverser("Hello, World!")
        == "World! Hello,"
    )


def test_reversal_is_involutive():
    # Reversing twice should return the original (modulo whitespace
    # normalisation).
    original = "  The   quick  brown fox  "
    once = string_missions_sentence_word_reverser(original)
    twice = string_missions_sentence_word_reverser(once)
    assert once == "fox brown quick The"
    assert twice == "The quick brown fox"


def test_words_with_only_surrounding_spaces_collapse():
    assert (
        string_missions_sentence_word_reverser("a  b  c  d  e")
        == "e d c b a"
    )


def test_single_letter_words():
    assert string_missions_sentence_word_reverser("a b c") == "c b a"


def test_return_type_is_string():
    result = string_missions_sentence_word_reverser("a b c")
    assert isinstance(result, str)


@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("a b c", "c b a"),
        ("1 2 3 4", "4 3 2 1"),
        ("one two", "two one"),
        ("x", "x"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_parametrized_reversals(input_str, expected):
    assert string_missions_sentence_word_reverser(input_str) == expected