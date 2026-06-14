import pytest

from logfmt_kv import logfmt_kv


def test_returns_dict():
    result = logfmt_kv("key=value")
    assert isinstance(result, dict)


def test_simple_key_value():
    assert logfmt_kv("key=value") == {"key": "value"}


def test_multiple_pairs():
    assert logfmt_kv("a=1 b=2 c=3") == {"a": "1", "b": "2", "c": "3"}


def test_quoted_value_with_spaces():
    assert logfmt_kv('msg="hello world"') == {"msg": "hello world"}


def test_mixed_quoted_and_unquoted():
    assert logfmt_kv('name=alice msg="hello world" level=info') == {
        "name": "alice",
        "msg": "hello world",
        "level": "info",
    }


def test_empty_string():
    assert logfmt_kv("") == {}


def test_whitespace_only():
    assert logfmt_kv("   ") == {}


def test_key_without_value():
    assert logfmt_kv("flag") == {"flag": ""}


def test_key_with_equals_no_value():
    assert logfmt_kv("flag=") == {"flag": ""}


def test_pair_followed_by_bare_key():
    assert logfmt_kv("a=1 b") == {"a": "1", "b": ""}


def test_extra_whitespace_between_pairs():
    assert logfmt_kv("  a=1   b=2  ") == {"a": "1", "b": "2"}


def test_underscore_in_key():
    assert logfmt_kv("user_id=42") == {"user_id": "42"}


def test_unquoted_value_with_slashes():
    assert logfmt_kv("path=/var/log/app.log") == {"path": "/var/log/app.log"}


def test_equals_sign_inside_quoted_value():
    assert logfmt_kv('expr="a=b+c"') == {"expr": "a=b+c"}


def test_empty_quoted_value():
    assert logfmt_kv('key=""') == {"key": ""}


def test_escaped_quote_in_quoted_value():
    # Raw string so backslashes are literal in the source.
    assert logfmt_kv(r'key="say \"hi\""') == {"key": 'say "hi"'}


def test_escaped_backslash_in_quoted_value():
    assert logfmt_kv(r'path="C:\\Users\\me"') == {"path": "C:\\Users\\me"}


def test_realistic_log_line():
    line = 'ts=2024-01-15T12:34:56Z level=info msg="request completed" status=200 duration_ms=43'
    assert logfmt_kv(line) == {
        "ts": "2024-01-15T12:34:56Z",
        "level": "info",
        "msg": "request completed",
        "status": "200",
        "duration_ms": "43",
    }