"""Tests for the balanced_group_parser function."""
from balanced_group_parser import balanced_group_parser


def test_empty_string():
    """Empty input returns an empty list."""
    assert balanced_group_parser("") == []


def test_simple_empty_group():
    """A single empty group '()' returns ['()']."""
    assert balanced_group_parser("()") == ["()"]


def test_group_with_content():
    """A group with content returns the full group including delimiters."""
    assert balanced_group_parser("(hello)") == ["(hello)"]


def test_multiple_disjoint_groups():
    """Multiple separate groups are all returned in order."""
    assert balanced_group_parser("()()") == ["()", "()"]


def test_groups_separated_by_text():
    """Groups separated by text are all found."""
    assert balanced_group_parser("a(b)c(d)e") == ["(b)", "(d)"]


def test_unmatched_open_ignored():
    """An unmatched opening delimiter produces no groups."""
    assert balanced_group_parser("(abc") == []


def test_unmatched_close_ignored():
    """An unmatched closing delimiter produces no groups."""
    assert balanced_group_parser("abc)") == []


def test_nested_groups_included_in_outer():
    """Nested groups: the inner group string is contained in the outer one."""
    result = balanced_group_parser("((a))")
    assert "(a)" in result
    assert "((a))" in result
    assert len(result) == 2


def test_deeply_nested_groups():
    """Deeply nested groups return every level, innermost first."""
    s = "((((x))))"
    result = balanced_group_parser(s)
    assert "(x)" in result
    assert "((x))" in result
    assert "(((x)))" in result
    assert "((((x))))" in result
    assert len(result) == 4


def test_escape_inside_group():
    """An escaped closing delimiter inside a group is treated as literal."""
    # \) is escaped so the inner ) does not close the group; only the
    # final ) closes it.
    assert balanced_group_parser(r"(a\)b)") == [r"(a\)b)"]


def test_only_delimiters():
    """Input that is exactly a balanced pair returns that single group."""
    assert balanced_group_parser("()") == ["()"]


def test_only_open_delimiter():
    """Input that is just an open delimiter returns nothing."""
    assert balanced_group_parser("(") == []


def test_only_close_delimiter():
    """Input that is just a close delimiter returns nothing."""
    assert balanced_group_parser(")") == []


def test_inner_returned_before_outer():
    """Inner groups appear earlier in the result list than outer groups."""
    result = balanced_group_parser("((a))")
    assert result.index("(a)") < result.index("((a))")


def test_custom_angle_delimiters():
    """Custom angle-bracket delimiters are respected."""
    assert balanced_group_parser("<x>", "<", ">") == ["<x>"]


def test_custom_brace_delimiters():
    """Custom brace delimiters are respected."""
    assert balanced_group_parser("{y}", "{", "}") == ["{y}"]


def test_groups_at_start_and_end():
    """Groups at the start and end of the string are both found."""
    assert balanced_group_parser("(a) middle (b)") == ["(a)", "(b)"]


def test_no_delimiters_in_text():
    """A string with no delimiters returns an empty list."""
    assert balanced_group_parser("no delimiters here") == []


def test_escape_outside_group():
    """Escaped delimiters outside any group are treated as literal text."""
    # Both ( and ) are escaped so neither acts as a delimiter.
    assert balanced_group_parser(r"\(a\)") == []


def test_nested_with_surrounding_text():
    """Nested groups with surrounding text are found correctly."""
    result = balanced_group_parser("start(inner(innermost)end)finish")
    assert "(innermost)" in result
    assert "(inner(innermost)end)" in result
    assert len(result) == 2


def test_consecutive_groups():
    """Consecutive groups with no text between them are all found."""
    assert balanced_group_parser("(a)(b)(c)") == ["(a)", "(b)", "(c)"]


def test_alternating_nested():
    """Siblings nested inside an outer group are all returned."""
    s = "(a(b)c(d)e)"
    result = balanced_group_parser(s)
    assert "(b)" in result
    assert "(d)" in result
    assert "(a(b)c(d)e)" in result
    assert len(result) == 3


def test_partial_match_not_returned():
    """A close-then-open sequence yields no balanced groups."""
    assert balanced_group_parser(")(") == []


def test_empty_string_with_custom_delims():
    """Empty string returns empty list regardless of delimiters."""
    assert balanced_group_parser("", "[", "]") == []


def test_backslash_at_end_of_string():
    """A trailing backslash with nothing to escape is treated as literal."""
    assert balanced_group_parser("abc\\") == []


def test_multiple_escapes():
    """Multiple escaped delimiters in a row produce no groups."""
    assert balanced_group_parser(r"\(\(a\)\)") == []


def test_escape_then_real_group():
    """An escaped delimiter followed by a real group is parsed correctly."""
    # The first ( is escaped, but the second ( opens a group that ) closes.
    assert balanced_group_parser(r"\((a))") == ["(a)"]


def test_default_delimiters_ignore_brackets():
    """Default parser only looks for parentheses, not brackets."""
    assert balanced_group_parser("[hello]") == []