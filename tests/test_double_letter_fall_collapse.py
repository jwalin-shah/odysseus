import pytest
from double_letter_fall_collapse import double_letter_fall_collapse


class TestBasicBehavior:
    def test_empty_string(self):
        assert double_letter_fall_collapse("") == ""

    def test_none_input(self):
        assert double_letter_fall_collapse(None) is None

    def test_single_character(self):
        assert double_letter_fall_collapse("a") == "a"

    def test_no_doubles(self):
        assert double_letter_fall_collapse("abc") == "abc"

    def test_simple_double_pair(self):
        assert double_letter_fall_collapse("aa") == ""

    def test_two_different_pairs(self):
        assert double_letter_fall_collapse("aabb") == ""

    def test_six_doubles(self):
        assert double_letter_fall_collapse("aabbcc") == ""


class TestIterativeCollapse:
    def test_nested_collapse(self):
        # abccba -> abba -> aa -> ""
        assert double_letter_fall_collapse("abccba") == ""

    def test_triple_collapse_to_single(self):
        # aaa -> a (remove two, leave one)
        assert double_letter_fall_collapse("aaa") == "a"

    def test_quad_collapse(self):
        # aaaa -> "" (remove two, remove two)
        assert double_letter_fall_collapse("aaaa") == ""

    def test_partial_collapse(self):
        # abbc -> ac
        assert double_letter_fall_collapse("abbc") == "ac"

    def test_mixed_doubles_and_singles(self):
        # aabbaa -> bb -> ""
        assert double_letter_fall_collapse("aabbaa") == ""

    def test_complex_pattern(self):
        # abbccdde -> ae
        assert double_letter_fall_collapse("abbccdde") == "ae"


class TestCaseSensitivity:
    def test_case_sensitive_lowercase(self):
        # 'a' and 'A' are different, so nothing collapses
        assert double_letter_fall_collapse("aA") == "aA"

    def test_case_sensitive_uppercase(self):
        assert double_letter_fall_collapse("Aa") == "Aa"

    def test_mixed_case_pattern(self):
        # aAa has no adjacent duplicates (case-sensitive), so unchanged
        assert double_letter_fall_collapse("aAa") == "aAa"

    def test_uppercase_doubles(self):
        assert double_letter_fall_collapse("AABB") == ""


class TestSpecialCharacters:
    def test_double_spaces(self):
        # Spaces are characters too; adjacent identical spaces collapse
        assert double_letter_fall_collapse("a  a") == ""

    def test_letters_around_non_letter(self):
        # The '!' breaks the adjacency, so 'a' and 'a' don't collapse
        assert double_letter_fall_collapse("a!a") == "a!a"

    def test_digit_doubles(self):
        assert double_letter_fall_collapse("112233") == ""

    def test_punctuation_doubles(self):
        assert double_letter_fall_collapse("!!??") == ""


class TestEdgeCases:
    def test_alternating(self):
        assert double_letter_fall_collapse("abab") == "abab"

    def test_single_double_in_middle(self):
        assert double_letter_fall_collapse("abccd") == "abd"

    def test_long_string_no_doubles(self):
        text = "thequickbrownfox"
        assert double_letter_fall_collapse(text) == text

    def test_full_collapse_long(self):
        # "abcd" with each letter doubled: aabbccdd -> ""
        assert double_letter_fall_collapse("aabbccdd") == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])