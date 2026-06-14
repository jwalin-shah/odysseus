import os
import sys

# Allow `import decode_nested_bracket` from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from decode_nested_bracket import decode_nested_bracket


# ---------------------------------------------------------------------------
# Basic / canonical cases
# ---------------------------------------------------------------------------

def test_single_bracket_group():
    """A single group with a count is repeated that many times."""
    assert decode_nested_bracket("3[a]") == "aaa"


def test_consecutive_bracket_groups():
    """Two consecutive groups with literal trailing content between them."""
    assert decode_nested_bracket("3[a]2[bc]") == "aaabcbc"


def test_nested_brackets():
    """Inner content is decoded first, then the outer count is applied."""
    assert decode_nested_bracket("3[a2[c]]") == "accaccacc"


def test_complex_trailing_literal():
    """A typical LeetCode-style input with trailing literal characters."""
    assert decode_nested_bracket("2[abc]3[cd]ef") == "abcabccdcdcdef"


def test_deeply_nested_brackets():
    """Three levels of nesting: 2 * 2 * 2 = 8 a's."""
    assert decode_nested_bracket("2[2[2[a]]]") == "aaaaaaaa"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_string():
    """An empty string decodes to an empty string."""
    assert decode_nested_bracket("") == ""


def test_no_brackets_returns_unchanged():
    """A string containing only letters is returned unchanged."""
    assert decode_nested_bracket("hello world") == "hello world"


def test_single_letter_no_count():
    """A single character is returned as-is."""
    assert decode_nested_bracket("a") == "a"


def test_repeat_count_of_one():
    """A count of 1 yields the bracketed content exactly once."""
    assert decode_nested_bracket("1[a]") == "a"


def test_multi_digit_repeat_count():
    """Repeat counts may contain more than one digit."""
    assert decode_nested_bracket("10[a]") == "aaaaaaaaaa"


def test_brackets_with_only_letters():
    """Brackets may contain multi-letter words."""
    assert decode_nested_bracket("2[hello]") == "hellohello"


def test_bracket_immediately_followed_by_group():
    """Decoded output flows directly into the next group with no separator."""
    assert decode_nested_bracket("2[a]3[b]") == "aabbb"


def test_nested_then_flat():
    """Mixing nested and flat groups in the same input."""
    assert decode_nested_bracket("2[a3[b]]4[c]") == "abbbabbbcccc"


# ---------------------------------------------------------------------------
# Defensive behaviour for malformed input
# ---------------------------------------------------------------------------

def test_none_input_is_returned_unchanged():
    """Non-string input is returned as-is rather than raising."""
    assert decode_nested_bracket(None) is None


def test_unmatched_closing_bracket_returns_input():
    """An unmatched ']' falls back to returning the original string."""
    assert decode_nested_bracket("abc]") == "abc]"