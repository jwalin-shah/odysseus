"""Pytest test suite for :mod:`bracket_reverser`."""
import pytest

from bracket_reverser import bracket_reverser


# ---------------------------------------------------------------------------
# Basic / happy-path tests
# ---------------------------------------------------------------------------


def test_simple_parentheses():
    """The substring inside a single pair of parentheses is reversed."""
    assert bracket_reverser("a(bc)d") == "a(cb)d"


def test_simple_square_brackets():
    """The substring inside a single pair of square brackets is reversed."""
    assert bracket_reverser("hello[world]") == "hello[dlrow]"


def test_simple_curly_braces():
    """The substring inside a single pair of curly braces is reversed."""
    assert bracket_reverser("{abc}xyz") == "{cba}xyz"


def test_only_brackets_round():
    """A string consisting solely of one bracketed segment is reversed."""
    assert bracket_reverser("(abc)") == "(cba)"


def test_multiple_pairs_same_type():
    """Every matched pair is reversed independently of the others."""
    assert bracket_reverser("(ab)(cd)") == "(ba)(dc)"


def test_multiple_pairs_mixed_types():
    """Different bracket types in the same string are all handled."""
    assert bracket_reverser("(ab)[cd]{ef}") == "(ba)[dc]{fe}"


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------


def test_empty_string():
    """An empty input is returned unchanged without raising."""
    assert bracket_reverser("") == ""


def test_no_brackets():
    """A string with no brackets at all is returned unchanged."""
    assert bracket_reverser("hello world 123!") == "hello world 123!"


def test_unmatched_opening_bracket():
    """A stray opening bracket with no partner leaves the string untouched."""
    assert bracket_reverser("(abc") == "(abc"


def test_unmatched_closing_bracket():
    """A stray closing bracket with no partner leaves the string untouched."""
    assert bracket_reverser("abc)") == "abc)"


def test_brackets_around_empty_content():
    """Empty content between brackets is a no-op."""
    assert bracket_reverser("a()b") == "a()b"


def test_unicode_inside_brackets():
    """Non-ASCII characters inside brackets are reversed correctly."""
    assert bracket_reverser("(\u00e9\u00e8\u00ea)") == "(\u00ea\u00e8\u00e9)"


# ---------------------------------------------------------------------------
# Input-validation tests
# ---------------------------------------------------------------------------


def test_non_string_raises_type_error():
    """Passing an integer raises TypeError."""
    with pytest.raises(TypeError):
        bracket_reverser(123)


def test_none_raises_type_error():
    """Passing None raises TypeError."""
    with pytest.raises(TypeError):
        bracket_reverser(None)


def test_list_raises_type_error():
    """Passing a list raises TypeError."""
    with pytest.raises(TypeError):
        bracket_reverser(["a", "b", "c"])