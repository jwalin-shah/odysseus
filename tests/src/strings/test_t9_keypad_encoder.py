import os
import sys

# Make the project root importable so `src` resolves when pytest
# is run from any working directory.
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')),
)

from src.strings.t9_keypad_encoder import t9_keypad_encoder, T9_KEYMAP


def test_keymap_contains_every_letter():
    for letter in 'abcdefghijklmnopqrstuvwxyz':
        assert letter in T9_KEYMAP


def test_single_letter_a():
    assert t9_keypad_encoder('a') == '2'


def test_single_letter_z():
    assert t9_keypad_encoder('z') == '9999'


def test_uppercase_matches_lowercase():
    assert t9_keypad_encoder('HELLO') == t9_keypad_encoder('hello')


def test_empty_string_returns_empty():
    assert t9_keypad_encoder('') == ''


def test_letters_on_different_keys_need_no_separator():
    # 'a' is on key 2, 'd' is on key 3.
    assert t9_keypad_encoder('ad') == '23'


def test_consecutive_letters_on_same_key_get_separator():
    # 'b' and 'c' are both on key 2.
    assert t9_keypad_encoder('bc') == '22 222'


def test_hello_word():
    # h(44) e(33) l(555) l(555, same key, separator) o(666).
    assert t9_keypad_encoder('hello') == '4433555 555666'


def test_space_encodes_to_zero():
    assert t9_keypad_encoder(' ') == '0'


def test_unknown_characters_are_dropped():
    # '!' is not in the keymap, so it is silently removed.
    assert t9_keypad_encoder('a!b') == '2 22'


def test_custom_separator_is_respected():
    assert t9_keypad_encoder('bc', separator='|') == '22|222'