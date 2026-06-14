import sys
import os

# Make the ``src`` directory importable regardless of where pytest is run from.
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from src_rotation_counter import src_rotation_counter  # noqa: E402


class TestSrcRotationCounter:
    """Test suite for ``src_rotation_counter``."""

    def test_empty_string_returns_zero(self):
        """An empty string has zero distinct rotations."""
        assert src_rotation_counter("") == 0

    def test_single_character_returns_one(self):
        """A single-character string has exactly one distinct rotation."""
        assert src_rotation_counter("a") == 1
        assert src_rotation_counter("z") == 1

    def test_all_identical_characters_returns_one(self):
        """A string made of identical characters has one distinct rotation."""
        assert src_rotation_counter("aaaa") == 1
        assert src_rotation_counter("xxxxxx") == 1

    def test_all_distinct_characters_returns_length(self):
        """A string with all distinct characters has n distinct rotations."""
        assert src_rotation_counter("abc") == 3
        assert src_rotation_counter("abcde") == 5
        assert src_rotation_counter("abcdef") == 6

    def test_two_distinct_rotations(self):
        """A string with period dividing n by 2 has 2 distinct rotations."""
        # "abab" -> rotations are "abab", "baba", "abab", "baba" -> 2 distinct
        assert src_rotation_counter("abab") == 2
        # "ababab" has period 2 -> 2 distinct rotations
        assert src_rotation_counter("ababab") == 2

    def test_three_distinct_rotations(self):
        """A string with period dividing n by 3 has 3 distinct rotations."""
        # "abcabc" -> rotations repeat every 3 -> 3 distinct
        assert src_rotation_counter("abcabc") == 3

    def test_palindrome_distinct_rotations(self):
        """A palindromic string can still have all distinct rotations."""
        # "aba" -> "aba", "baa", "aab" -> 3 distinct
        assert src_rotation_counter("aba") == 3

    def test_aab_has_three_distinct_rotations(self):
        """The string 'aab' produces 3 distinct rotations."""
        # "aab" -> "aab", "aba", "baa" -> 3 distinct
        assert src_rotation_counter("aab") == 3

    def test_long_string_of_same_character(self):
        """A long string of identical characters still has 1 distinct rotation."""
        assert src_rotation_counter("a" * 100) == 1

    def test_returns_non_negative(self):
        """The function should always return a non-negative integer."""
        for candidate in ["", "a", "ab", "abc", "hello", "xyzxyz"]:
            result = src_rotation_counter(candidate)
            assert isinstance(result, int)
            assert result >= 0

    def test_result_at_most_length(self):
        """The number of distinct rotations can never exceed the string length."""
        for candidate in ["abc", "aabb", "abcabc", "abababab"]:
            result = src_rotation_counter(candidate)
            assert result <= len(candidate)

    def test_count_does_not_exceed_length(self):
        """Distinct rotation count is bounded above by ``len(s)``."""
        assert src_rotation_counter("hello") <= 5
        assert src_rotation_counter("rotation") <= 8