from src.string_ops_vowel_islands import string_ops_vowel_islands


def test_empty_string_returns_zero():
    assert string_ops_vowel_islands("") == 0


def test_no_vowels_returns_zero():
    assert string_ops_vowel_islands("bcdfg") == 0


def test_all_vowels_single_island():
    assert string_ops_vowel_islands("aeiou") == 1


def test_single_vowel_one_island():
    assert string_ops_vowel_islands("a") == 1


def test_hello_two_islands():
    # "e" and "o" are two separate vowel islands
    assert string_ops_vowel_islands("hello") == 2


def test_consonant_vowel_consonant_pattern():
    # "education" -> e, u, a, io => 4 islands
    assert string_ops_vowel_islands("education") == 4


def test_multiple_vowels_with_non_vowels_between():
    # "aei" is one island, "ou" is another => 2 islands
    assert string_ops_vowel_islands("aeibcdou") == 2


def test_uppercase_vowels_treated_as_vowels():
    assert string_ops_vowel_islands("AEIOU") == 1
    assert string_ops_vowel_islands("HELLO") == 2


def test_mixed_case_islands():
    # "aE" is one island, "Io" is another => 2 islands
    assert string_ops_vowel_islands("aE Io") == 2


def test_only_consonants_returns_zero():
    assert string_ops_vowel_islands("rhythm") == 0


def test_vowels_at_string_boundaries():
    # Leading "a" and trailing "u" are each their own island
    assert string_ops_vowel_islands("abcdeu") == 2


def test_long_vowel_run_is_single_island():
    assert string_ops_vowel_islands("aaaiiiooo") == 1


def test_alternating_vowels_and_consonants():
    # "a", "e", "i", "o", "u" are 5 separate islands
    assert string_ops_vowel_islands("abebibobub") == 5


def test_y_is_not_a_vowel():
    # "y" is not a vowel in this implementation
    assert string_ops_vowel_islands("syzygy") == 0


def test_numbers_and_punctuation_ignored():
    # "a", "e" are vowels; digits and punctuation break the chain
    assert string_ops_vowel_islands("a1e") == 2