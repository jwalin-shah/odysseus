import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shell_tokenizer import shell_tokenizer


def test_simple_whitespace_split():
    assert shell_tokenizer("a b c") == ["a", "b", "c"]


def test_double_quoted_string():
    assert shell_tokenizer('"hello world"') == ["hello world"]


def test_single_quoted_string():
    assert shell_tokenizer("'hello world'") == ["hello world"]


def test_empty_double_quotes():
    assert shell_tokenizer('""') == [""]


def test_empty_single_quotes():
    assert shell_tokenizer("''") == [""]


def test_only_whitespace():
    assert shell_tokenizer("   ") == []


def test_empty_string():
    assert shell_tokenizer("") == []


def test_mixed_quoted_and_unquoted():
    assert shell_tokenizer('echo "hello world"') == ["echo", "hello world"]


def test_single_quoted_with_unquoted():
    assert shell_tokenizer("echo 'hello'") == ["echo", "hello"]


def test_double_quote_does_not_swallow_single_quote_outside():
    # A double-quoted string ends at the closing ", so the ' outside
    # is a separate single-quoted token.
    assert shell_tokenizer('"a"\'b\'') == ["a", "b"]


def test_adjacent_quoted_strings_are_separate_tokens():
    assert shell_tokenizer('"a""b"') == ["a", "b"]


def test_quoted_then_unquoted():
    # "a"b -> ["a", "b"]  (no concatenation)
    assert shell_tokenizer('"a"b') == ["a", "b"]


def test_unquoted_then_quoted():
    # a"b" -> ["a", "b"]  (no concatenation)
    assert shell_tokenizer('a"b"') == ["a", "b"]


def test_mixed_quote_types_adjacent():
    assert shell_tokenizer('"a"\'b\'') == ["a", "b"]


def test_three_tokens_with_quote_boundaries():
    assert shell_tokenizer('"a"b"c"') == ["a", "b", "c"]


def test_single_quote_does_not_swallow_double_quote_outside():
    assert shell_tokenizer("'a'\"b\"") == ["a", "b"]


def test_unquoted_between_quoted():
    assert shell_tokenizer('"a"bb"c"') == ["a", "bb", "c"]


def test_multiple_spaces_between_tokens():
    assert shell_tokenizer("a    b") == ["a", "b"]


def test_tab_separator():
    assert shell_tokenizer("a\tb") == ["a", "b"]


def test_double_quoted_with_spaces_inside():
    assert shell_tokenizer('"a  b  c"') == ["a  b  c"]


def test_single_quoted_with_spaces_inside():
    assert shell_tokenizer("'a  b  c'") == ["a  b  c"]


def test_command_with_args():
    result = shell_tokenizer("ls -la /tmp")
    assert result == ["ls", "-la", "/tmp"]


def test_quoted_path():
    result = shell_tokenizer('cd "/usr/local/bin"')
    assert result == ["cd", "/usr/local/bin"]


def test_quote_inside_other_quote_type():
    # Double-quoted string can contain a literal single quote.
    assert shell_tokenizer('"it\'s"') == ["it's"]
    # Single-quoted string can contain a literal double quote.
    assert shell_tokenizer("'say \"hi\"'") == ['say "hi"']