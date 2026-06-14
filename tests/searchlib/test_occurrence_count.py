import pytest
from searchlib.occurrence_count import occurrence_count


class TestBasicCounting:
    def test_simple_string_count(self):
        assert occurrence_count("hello", "l") == 2

    def test_no_match(self):
        assert occurrence_count("hello", "z") == 0

    def test_full_match(self):
        assert occurrence_count("abc", "abc") == 1


class TestSequenceHaystack:
    def test_list_with_values(self):
        assert occurrence_count([1, 2, 3, 2, 1], [2]) == 2

    def test_none_elements(self):
        # Count occurrences of None in a list containing None values
        result = occurrence_count([1, None, 2, None, 2], [None])
        assert result == 2

    def test_none_at_boundaries(self):
        assert occurrence_count([None, 1, 2], [None]) == 1
        assert occurrence_count([1, 2, None], [None]) == 1

    def test_tuple_haystack(self):
        assert occurrence_count((1, 2, 1, 2, 1), (1,)) == 3


class TestEdgeCases:
    def test_none_haystack(self):
        assert occurrence_count(None, "a") == 0

    def test_none_needle(self):
        assert occurrence_count("hello", None) == 0

    def test_empty_needle(self):
        assert occurrence_count("hello", "") == 0

    def test_empty_haystack(self):
        assert occurrence_count("", "a") == 0

    def test_needle_longer_than_haystack(self):
        assert occurrence_count("hi", "hello") == 0

    @pytest.mark.parametrize("haystack, needle, expected", [
        ("mississippi", "ssi", 2),
        ("aaaa", "aa", 3),
        ("abcabc", "abc", 2),
        ("hello world", "o", 2),
    ])
    def test_parametrized_string_cases(self, haystack, needle, expected):
        assert occurrence_count(haystack, needle) == expected

    def test_overlap_parametrized(self):
        # "aa" in "aaaa" overlaps at positions 0, 1, 2 -> 3 matches
        assert occurrence_count("aaaa", "aa") == 3
        # "aba" in "ababa" overlaps at positions 0, 2 -> 2 matches
        assert occurrence_count("ababa", "aba") == 2
        # "ss" in "mississippi" at positions 2 and 5 -> 2 matches
        assert occurrence_count("mississippi", "ss") == 2