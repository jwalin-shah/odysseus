"""Tests for the T9 multi-tap keypad encoder."""

from src.src_strings_t9_keypad_encoder import t9_keypad_encoder


def test_empty_string_returns_empty_string():
    assert t9_keypad_encoder("") == ""


def test_none_input_returns_empty_string():
    # Defensive: passing None should not crash; treat as empty.
    assert t9_keypad_encoder(None) == ""  # type: ignore[arg-type]


def test_single_letter_a_is_one_press_of_2():
    assert t9_keypad_encoder("a") == "2"


def test_single_letter_z_is_four_presses_of_9():
    assert t9_keypad_encoder("z") == "9999"


def test_hello_is_classic_example():
    # The textbook multi-tap example: hello -> 44 33 555 555 666
    assert t9_keypad_encoder("hello") == "4433555555666"


def test_uppercase_is_normalised_to_lowercase():
    assert t9_keypad_encoder("HELLO") == "4433555555666"


def test_mixed_case_is_normalised_to_lowercase():
    assert t9_keypad_encoder("HeLLo") == "4433555555666"


def test_no_separator_between_consecutive_same_key_letters():
    # "ll" must concatenate to "555555" with no space/pause inserted.
    assert t9_keypad_encoder("ll") == "555555"


def test_space_is_encoded_as_zero():
    assert t9_keypad_encoder(" ") == "0"


def test_word_separated_by_space():
    # a<space>b  ->  2 0 22
    assert t9_keypad_encoder("a b") == "2022"


def test_digits_are_passed_through_unchanged():
    assert t9_keypad_encoder("123") == "123"


def test_mixed_letters_and_digits():
    # hi5 -> 44 444 5
    assert t9_keypad_encoder("hi5") == "444445"


def test_punctuation_is_ignored():
    # "hi!" should encode the letters and drop the '!'.
    assert t9_keypad_encoder("hi!") == "44444"


def test_full_alphabet_round_trip_known_values():
    # Spot-check a few representative letters.
    assert t9_keypad_encoder("s") == "7777"
    assert t9_keypad_encoder("k") == "55"
    assert t9_keypad_encoder("t") == "8"
    assert t9_keypad_encoder("y") == "999"