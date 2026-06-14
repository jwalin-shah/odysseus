"""Tests for the alternating word caser mission."""
import pytest

from src.missions_string_ops_alternating_word_caser import alternating_word_caser


class TestAlternatingWordCaser:
    """Test suite for ``alternating_word_caser``."""

    def test_basic_two_words(self):
        assert alternating_word_caser("hello world") == "HELLO world"

    def test_basic_four_words(self):
        assert (
            alternating_word_caser("hello world foo bar")
            == "HELLO world FOO bar"
        )

    def test_three_words(self):
        assert alternating_word_caser("one two three") == "ONE two THREE"

    def test_single_word_uppercased(self):
        assert alternating_word_caser("hello") == "HELLO"

    def test_empty_string_returns_empty(self):
        assert alternating_word_caser("") == ""

    def test_whitespace_only_returns_empty(self):
        # split() with no args drops whitespace-only strings into [].
        assert alternating_word_caser("   ") == ""

    def test_mixed_case_input_is_normalised(self):
        assert (
            alternating_word_caser("HeLLo WoRLd FoO BaR")
            == "HELLO world FOO bar"
        )

    def test_already_alternating_stays_alternating(self):
        assert (
            alternating_word_caser("HELLO world FOO bar")
            == "HELLO world FOO bar"
        )

    def test_collapses_multiple_spaces(self):
        # split() with no args treats any run of whitespace as one
        # separator; the function should not preserve the original gap.
        result = alternating_word_caser("hello   world")
        assert result == "HELLO world"

    def test_long_sentence(self):
        sentence = "The quick brown fox jumps over the lazy dog"
        expected = "THE quick BROWN fox JUMPS over THE lazy DOG"
        assert alternating_word_caser(sentence) == expected

    def test_preserves_punctuation_within_words(self):
        # Punctuation attached to a word stays attached; only letter
        # case is changed.
        result = alternating_word_caser("Hello, World! Foo Bar?")
        assert result == "HELLO, world! FOO bar?"

    def test_non_string_raises_type_error(self):
        with pytest.raises(TypeError):
            alternating_word_caser(123)

    def test_none_raises_type_error(self):
        with pytest.raises(TypeError):
            alternating_word_caser(None)

    def test_list_raises_type_error(self):
        with pytest.raises(TypeError):
            alternating_word_caser(["hello", "world"])