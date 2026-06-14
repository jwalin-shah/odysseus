"""Tests for :func:`string_missions.pascal_to_snake.pascal_to_snake`."""

import pytest

from string_missions.pascal_to_snake import pascal_to_snake


# ---------------------------------------------------------------------------
# Behavioural tests
# ---------------------------------------------------------------------------


def test_basic_two_word_pascal():
    """A simple two-word PascalCase string is split on the case boundary."""
    assert pascal_to_snake("PascalCase") == "pascal_case"


def test_three_word_pascal():
    """Multiple PascalCase words are each separated by a single underscore."""
    assert pascal_to_snake("MyClassName") == "my_class_name"


def test_long_pascal_string():
    """A long PascalCase identifier is broken up at every boundary."""
    assert (
        pascal_to_snake("HelloWorldExample")
        == "hello_world_example"
    )


def test_single_word_pascal():
    """A single PascalCase word is simply lower-cased."""
    assert pascal_to_snake("Hello") == "hello"


def test_pascal_with_acronym():
    """Consecutive uppercase letters (an acronym) stay in one word."""
    assert pascal_to_snake("MyXMLParser") == "my_xml_parser"


def test_pascal_with_digits_in_middle():
    """Digits in the middle of the identifier are preserved without a split."""
    assert pascal_to_snake("Class2Name") == "class2_name"


def test_pascal_starting_with_digit():
    """A leading digit does not produce a leading underscore."""
    assert pascal_to_snake("1ClassName") == "1_class_name"


def test_already_snake_case_is_lowered():
    """Strings that are already snake_case pass through unchanged."""
    assert pascal_to_snake("already_snake") == "already_snake"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_string_returns_empty_string():
    """The function is the identity on the empty string."""
    assert pascal_to_snake("") == ""


def test_single_uppercase_letter():
    """A single uppercase letter becomes its lowercase counterpart."""
    assert pascal_to_snake("A") == "a"


def test_single_lowercase_letter():
    """A single lowercase letter is returned unchanged."""
    assert pascal_to_snake("a") == "a"


def test_trailing_uppercase_letter():
    """A trailing uppercase letter does not gain a trailing underscore."""
    # "MyClass" -> "my_class" (no trailing underscore after the final 's')
    assert pascal_to_snake("MyClass") == "my_class"


# ---------------------------------------------------------------------------
# Type validation
# ---------------------------------------------------------------------------


def test_non_string_integer_raises_type_error():
    """Passing an integer raises a TypeError."""
    with pytest.raises(TypeError):
        pascal_to_snake(123)


def test_non_string_none_raises_type_error():
    """Passing ``None`` raises a TypeError."""
    with pytest.raises(TypeError):
        pascal_to_snake(None)


def test_non_string_list_raises_type_error():
    """Passing a list raises a TypeError."""
    with pytest.raises(TypeError):
        pascal_to_snake(["Hello", "World"])