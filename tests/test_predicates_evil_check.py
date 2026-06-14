"""Tests for :func:`src.predicates_evil_check.predicates_evil_check`."""

from __future__ import annotations

import pytest

from src.predicates_evil_check import predicates_evil_check


# ---------------------------------------------------------------------------
# Basic evil cases -- must return True
# ---------------------------------------------------------------------------


def test_empty_string_is_evil():
    """An empty string has no content at all."""
    assert predicates_evil_check("") is True


def test_none_is_evil():
    """``None`` is treated as a missing/empty description."""
    assert predicates_evil_check(None) is True


def test_whitespace_only_is_evil():
    """Strings made of only whitespace are not meaningful descriptions."""
    assert predicates_evil_check("   \n\t  \n") is True


def test_single_html_comment_is_evil():
    """A single placeholder comment carries no information."""
    assert predicates_evil_check("<!-- placeholder -->") is True


def test_multiline_html_comment_is_evil():
    """Multi-line HTML comments are still placeholders."""
    body = "<!--\nTODO: write a description\n-->\n   \n"
    assert predicates_evil_check(body) is True


def test_multiple_html_comments_are_evil():
    """Several comments back-to-back with no real prose are evil."""
    assert predicates_evil_check("<!-- a --><!-- b --><!-- c -->") is True


def test_html_comment_with_surrounding_whitespace_is_evil():
    """Whitespace around an HTML comment is irrelevant."""
    assert predicates_evil_check("  \n  <!-- nope -->  \n") is True


def test_non_string_values_are_evil():
    """Numbers, bytes, lists, etc. cannot be valid descriptions."""
    assert predicates_evil_check(0) is True
    assert predicates_evil_check(b"hello") is True
    assert predicates_evil_check(["nope"]) is True
    assert predicates_evil_check(object()) is True


# ---------------------------------------------------------------------------
# Non-evil cases -- must return False
# ---------------------------------------------------------------------------


def test_plain_text_is_not_evil():
    """A normal sentence is a real description."""
    assert predicates_evil_check("Looks good to me!") is False


def test_text_with_trailing_newline_is_not_evil():
    """Trailing whitespace does not invalidate real content."""
    assert predicates_evil_check("Real content\n\n") is False


def test_text_with_leading_html_comment_is_not_evil():
    """A comment marker followed by real prose is fine."""
    assert predicates_evil_check("<!-- pr-description-check-bot -->\nActual text") is False


def test_text_between_html_comments_is_not_evil():
    """Real content nested between comments is preserved."""
    body = "<!-- header -->\nImportant details here.\n<!-- footer -->"
    assert predicates_evil_check(body) is False


def test_unicode_text_is_not_evil():
    """Non-ASCII characters should be treated as valid content."""
    assert predicates_evil_check("LGTM 👍 — ship it!") is False


# ---------------------------------------------------------------------------
# Type / robustness
# ---------------------------------------------------------------------------


def test_returns_bool_type():
    """The predicate must always return a real ``bool``."""
    result_true = predicates_evil_check("")
    result_false = predicates_evil_check("x")
    assert isinstance(result_true, bool)
    assert isinstance(result_false, bool)
    assert result_true is True
    assert result_false is False


@pytest.mark.parametrize(
    "evil_value",
    [
        "",
        "   ",
        "\n\n\t",
        "<!-- x -->",
        "<!--\nfoo\n-->",
        "<!-- a --><!-- b -->",
        None,
        0,
        [],
    ],
)
def test_parametrized_evil_values(evil_value):
    """A handful of evil inputs all return ``True``."""
    assert predicates_evil_check(evil_value) is True


@pytest.mark.parametrize(
    "good_value",
    [
        "hello",
        "<!-- marker -->\nbody",
        "x",
        "こんにちは",
        "A" * 4096,
    ],
)
def test_parametrized_good_values(good_value):
    """A handful of real inputs all return ``False``."""
    assert predicates_evil_check(good_value) is False