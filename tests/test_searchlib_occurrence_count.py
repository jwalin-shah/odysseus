"""Tests for searchlib_occurrence_count."""
import pytest

from src.searchlib_occurrence_count import searchlib_occurrence_count


def test_overlapping_single_occurrence():
    assert searchlib_occurrence_count("hello world", "world", overlap=True) == 1


def test_overlapping_multiple_occurrences():
    assert searchlib_occurrence_count("abcabcabc", "abc", overlap=True) == 3


def test_non_overlapping_multiple_occurrences():
    assert searchlib_occurrence_count("abcabcabc", "abc", overlap=False) == 3


def test_overlapping_repeating_single_char():
    assert searchlib_occurrence_count("aaaaa", "a", overlap=True) == 5


def test_non_overlapping_repeating_single_char():
    assert searchlib_occurrence_count("aaaaa", "a", overlap=False) == 5


def test_overlapping_repeating_multi_char():
    assert searchlib_occurrence_count("aaaaa", "aaa", overlap=True) == 3


def test_non_overlapping_repeating_multi_char():
    # Non-overlapping: each match consumes 3 chars, so only 1 in "aaaaa"
    assert searchlib_occurrence_count("aaaaa", "aaa", overlap=False) == 1


def test_no_match():
    assert searchlib_occurrence_count("hello", "xyz", overlap=True) == 0
    assert searchlib_occurrence_count("hello", "xyz", overlap=False) == 0


def test_empty_pattern():
    assert searchlib_occurrence_count("hello", "", overlap=True) == 0
    assert searchlib_occurrence_count("hello", "", overlap=False) == 0


def test_empty_text():
    assert searchlib_occurrence_count("", "hello", overlap=True) == 0
    assert searchlib_occurrence_count("", "hello", overlap=False) == 0


def test_pattern_longer_than_text():
    assert searchlib_occurrence_count("hi", "hello", overlap=True) == 0
    assert searchlib_occurrence_count("hi", "hello", overlap=False) == 0


def test_case_sensitive():
    assert searchlib_occurrence_count("Hello", "hello", overlap=True) == 0


def test_overlap_default_true():
    # overlap parameter defaults to True
    assert searchlib_occurrence_count("abcabc", "abc") == 2


def test_non_overlapping_ab_pattern():
    assert searchlib_occurrence_count("abababab", "ab", overlap=False) == 4


def test_overlapping_ab_pattern():
    assert searchlib_occurrence_count("abababab", "ab", overlap=True) == 4


def test_partial_match_at_end_not_counted():
    assert searchlib_occurrence_count("abcab", "abc", overlap=True) == 1
    assert searchlib_occurrence_count("abcab", "abc", overlap=False) == 1


def test_non_overlapping_aaaa_aaa():
    # "aaaa" has "aaa" only at position 0 non-overlapping
    assert searchlib_occurrence_count("aaaa", "aaa", overlap=False) == 1


def test_invalid_type_text_raises():
    with pytest.raises(TypeError):
        searchlib_occurrence_count(123, "abc")


def test_invalid_type_pattern_raises():
    with pytest.raises(TypeError):
        searchlib_occurrence_count("abc", 123)


def test_match_at_start_and_end():
    assert searchlib_occurrence_count("abcxyzabc", "abc", overlap=False) == 2
    assert searchlib_occurrence_count("abcxyzabc", "abc", overlap=True) == 2