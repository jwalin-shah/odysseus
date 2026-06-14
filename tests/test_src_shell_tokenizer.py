import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src_shell_tokenizer import shell_tokenize


def test_empty_string():
    assert shell_tokenize("") == []


def test_simple_word():
    assert shell_tokenize("hello") == ["hello"]


def test_multiple_words():
    assert shell_tokenize("hello world") == ["hello", "world"]


def test_single_quoted():
    assert shell_tokenize("'hello world'") == ["hello world"]


def test_double_quoted():
    assert shell_tokenize('"hello world"') == ["hello world"]


def test_empty_single_quoted_string():
    assert shell_tokenize("''") == [""]


def test_empty_double_quoted_string():
    assert shell_tokenize('""') == [""]


def test_backslash_escape_space_outside_quotes():
    # Backslash-escaped space should be part of the token, not a separator
    assert shell_tokenize("hello\\ world") == ["hello world"]


def test_backslash_escape_quote_in_double_quotes():
    # Inside double quotes, \" is an escaped double quote
    assert shell_tokenize('"hello\\"world"') == ['hello"world']


def test_multiple_spaces_between_words():
    assert shell_tokenize("hello   world") == ["hello", "world"]


def test_tab_separator():
    assert shell_tokenize("hello\tworld") == ["hello", "world"]


def test_command_with_args():
    assert shell_tokenize("ls -la /tmp") == ["ls", "-la", "/tmp"]


def test_empty_single_quotes_then_text():
    # ''hello should be a single token "hello"
    assert shell_tokenize("''hello") == ["hello"]


def test_empty_double_quotes_then_text():
    assert shell_tokenize('""hello') == ["hello"]


def test_adjacent_quoted_and_unquoted():
    assert shell_tokenize("a'b'c") == ["abc"]


def test_single_inside_double_quotes_is_literal():
    assert shell_tokenize("\"hello'world\"") == ["hello'world"]


def test_double_inside_single_quotes_is_literal():
    assert shell_tokenize("'hello\"world'") == ['hello"world']


def test_leading_whitespace():
    assert shell_tokenize("  hello") == ["hello"]


def test_trailing_whitespace():
    assert shell_tokenize("hello  ") == ["hello"]


def test_newline_separator():
    assert shell_tokenize("hello\nworld") == ["hello", "world"]


def test_dollar_kept_literal_in_double_quotes():
    # No variable expansion; $ stays as a literal character
    assert shell_tokenize('"$VAR"') == ["$VAR"]


def test_backtick_kept_literal_in_double_quotes():
    # No command substitution; backticks stay literal
    assert shell_tokenize('"`cmd`"') == ["`cmd`"]


def test_only_whitespace():
    assert shell_tokenize("   \t  ") == []


def test_single_quote_inside_double_quotes_does_not_close():
    # The single quote inside double quotes is literal and should not
    # affect the double-quote state.
    assert shell_tokenize("\"ab'cd\"") == ["ab'cd"]


def test_backslash_in_single_quotes_is_literal():
    # In single quotes, backslash is literal (no escape processing)
    assert shell_tokenize("'a\\b'") == ["a\\b"]


def test_returns_list_type():
    assert isinstance(shell_tokenize("echo hi"), list)


def test_token_count():
    assert len(shell_tokenize("one two three four")) == 4