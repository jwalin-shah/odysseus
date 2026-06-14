"""Tests for :mod:`missions.string_ops.alternating_word_caser`."""

from __future__ import annotations

import os
import sys

import pytest

# Make the project root importable so we can pull in the module under
# test via its package path.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from missions.string_ops.alternating_word_caser import alternating_word_caser  # noqa: E402


def test_basic_alternating_pattern():
    """Words at even indices are uppercased, odd indices lowercased."""
    assert alternating_word_caser("hello world foo bar") == "HELLO world FOO bar"


def test_single_word_is_uppercase():
    """A single word sits at index 0, so it is uppercased."""
    assert alternating_word_caser("hello") == "HELLO"


def test_two_words_pattern():
    """First word uppercase, second word lowercase."""
    assert alternating_word_caser("HELLO WORLD") == "HELLO world"


def test_empty_string_returns_empty():
    """Empty input yields empty output."""
    assert alternating_word_caser("") == ""


def test_whitespace_only_returns_empty():
    """A string of only whitespace is treated as empty."""
    assert alternating_word_caser("   \t  \n ") == ""


def test_mixed_case_input_is_normalised():
    """Existing case is overridden by the alternating pattern."""
    assert alternating_word_caser("HeLLo WoRLd FoO BaR") == "HELLO world FOO bar"


def test_multiple_spaces_are_collapsed():
    """Runs of whitespace between words are normalised to single spaces."""
    assert (
        alternating_word_caser("hello    world  foo   bar")
        == "HELLO world FOO bar"
    )


def test_leading_and_trailing_whitespace_ignored():
    """Leading/trailing whitespace does not become a phantom word."""
    assert alternating_word_caser("   hello world   ") == "HELLO world"


def test_punctuation_stays_attached():
    """Punctuation glued to a word is part of that word and not altered."""
    result = alternating_word_caser("hello, world! foo? bar.")
    assert result == "HELLO, world! FOO? bar."


def test_non_string_input_raises_type_error():
    """Non-string arguments must raise ``TypeError``."""
    with pytest.raises(TypeError):
        alternating_word_caser(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        alternating_word_caser(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        alternating_word_caser(["hello", "world"])  # type: ignore[arg-type]


def test_alternating_pattern_resets_correctly():
    """The alternation follows the index, regardless of previous case."""
    # Six words: pattern is U l U l U l
    assert (
        alternating_word_caser("a b c d e f") == "A b C d E f"
    )
    # Seven words: pattern is U l U l U l U
    assert (
        alternating_word_caser("a b c d e f g") == "A b C d E f G"
    )