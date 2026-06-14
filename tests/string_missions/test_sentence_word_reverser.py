import pytest

from string_missions.sentence_word_reverser import sentence_word_reverser


def test_basic_two_word_sentence():
    assert sentence_word_reverser("Hello world") == "world Hello"


def test_multiple_words_reversed():
    assert (
        sentence_word_reverser("The quick brown fox jumps over the lazy dog")
        == "dog lazy the over jumps fox brown quick The"
    )


def test_single_word_is_unchanged():
    assert sentence_word_reverser("Hello") == "Hello"


def test_empty_string_returns_empty():
    assert sentence_word_reverser("") == ""


def test_whitespace_only_returns_empty():
    assert sentence_word_reverser("   ") == ""
    assert sentence_word_reverser("\t\n  ") == ""


def test_extra_internal_whitespace_collapsed():
    assert sentence_word_reverser("Hello   world") == "world Hello"
    assert sentence_word_reverser("a\t\tb\n\nc") == "c b a"


def test_leading_and_trailing_whitespace_stripped():
    assert sentence_word_reverser("  Hello world  ") == "world Hello"
    assert sentence_word_reverser("\n  one two three  \t") == "three two one"


def test_punctuation_attached_to_words_is_preserved():
    # Punctuation that is part of a token stays with that token; only word
    # order is reversed.
    assert sentence_word_reverser("Hello, world!") == "world! Hello,"


def test_unicode_words_are_reversed():
    assert sentence_word_reverser("café résumé naïve") == "naïve résumé café"


def test_non_string_input_raises_type_error():
    with pytest.raises(TypeError):
        sentence_word_reverser(123)
    with pytest.raises(TypeError):
        sentence_word_reverser(None)
    with pytest.raises(TypeError):
        sentence_word_reverser(["Hello", "world"])