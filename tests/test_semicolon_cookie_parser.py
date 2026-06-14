import pytest
from semicolon_cookie_parser import semicolon_cookie_parser


def test_basic_two_cookies():
    result = semicolon_cookie_parser("name=John; age=30")
    assert result == {"name": "John", "age": "30"}


def test_single_cookie():
    assert semicolon_cookie_parser("name=John") == {"name": "John"}


def test_with_extra_whitespace():
    result = semicolon_cookie_parser("  name=John ;  age=30 ; city=NY  ")
    assert result == {"name": "John", "age": "30", "city": "NY"}


def test_empty_string_returns_empty_dict():
    assert semicolon_cookie_parser("") == {}


def test_none_input_returns_empty_dict():
    assert semicolon_cookie_parser(None) == {}


def test_only_whitespace_returns_empty_dict():
    assert semicolon_cookie_parser("   ") == {}


def test_cookie_without_value():
    result = semicolon_cookie_parser("flag; name=John")
    assert result == {"flag": "", "name": "John"}


def test_empty_segments_are_skipped():
    result = semicolon_cookie_parser(";;name=John;;age=30;;")
    assert result == {"name": "John", "age": "30"}


def test_value_containing_equals_is_preserved():
    result = semicolon_cookie_parser("token=abc=123==; name=John")
    assert result == {"token": "abc=123==", "name": "John"}


def test_value_with_spaces_around_it_is_trimmed():
    result = semicolon_cookie_parser("greeting=  hello world  ; name=John")
    assert result == {"greeting": "hello world", "name": "John"}


def test_key_with_no_value_and_no_equals():
    result = semicolon_cookie_parser("session")
    assert result == {"session": ""}


def test_multiple_cookies_preserves_order_independence():
    result = semicolon_cookie_parser("a=1; b=2; c=3; d=4")
    assert result == {"a": "1", "b": "2", "c": "3", "d": "4"}
    assert len(result) == 4
    assert result["a"] == "1"
    assert result["d"] == "4"


def test_duplicate_keys_last_one_wins():
    result = semicolon_cookie_parser("name=Alice; name=Bob")
    assert result == {"name": "Bob"}


def test_realistic_cookie_header():
    cookie_header = (
        "sessionid=abc123def456; "
        "csrftoken=xyz789; "
        "theme=dark; "
        "tracking=1"
    )
    result = semicolon_cookie_parser(cookie_header)
    assert result["sessionid"] == "abc123def456"
    assert result["csrftoken"] == "xyz789"
    assert result["theme"] == "dark"
    assert result["tracking"] == "1"
    assert len(result) == 4