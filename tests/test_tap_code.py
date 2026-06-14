import pytest
from tap_code import encode, decode


# --- Basic single-letter encoding tests ---

def test_encode_A_is_top_left():
    assert encode("A") == "1.1"


def test_encode_E_is_top_right():
    assert encode("E") == "1.5"


def test_encode_F_starts_second_row():
    assert encode("F") == "2.1"


def test_encode_K_starts_third_row():
    assert encode("K") == "3.1"


def test_encode_T_ends_fourth_row():
    assert encode("T") == "4.5"


def test_encode_U_starts_fifth_row():
    assert encode("U") == "5.1"


def test_encode_Z_is_bottom_right():
    assert encode("Z") == "5.6"


# --- Basic single-letter decoding tests ---

def test_decode_A_from_top_left():
    assert decode("1.1") == "A"


def test_decode_K_from_third_row():
    assert decode("3.1") == "K"


def test_decode_U_from_fifth_row():
    assert decode("5.1") == "U"


def test_decode_Z_from_bottom_right():
    assert decode("5.6") == "Z"


# --- Multi-letter tests ---

def test_encode_two_letters_uses_space_separator():
    assert encode("AB") == "1.1 1.2"


def test_encode_first_and_last_letters():
    assert encode("AZ") == "1.1 5.6"


def test_decode_two_letters():
    assert decode("1.1 1.2") == "AB"


# --- Case insensitivity ---

def test_encode_lowercase_matches_uppercase():
    assert encode("a") == "1.1"
    assert encode("k") == "3.1"
    assert encode("z") == "5.6"


def test_decode_is_uppercase():
    assert decode("1.1") == "A"


# --- Empty input ---

def test_empty_string_encode():
    assert encode("") == ""


def test_empty_string_decode():
    assert decode("") == ""


# --- Round trip tests (the key correctness property) ---

@pytest.mark.parametrize("text", [
    "A",
    "K",
    "Z",
    "HELLO",
    "TAPCODE",
    "THEQUICKBROWNFOXJUMPSOVERTHELAZYDOG",
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
])
def test_round_trip(text):
    assert decode(encode(text)) == text


# --- Invalid input handling ---

def test_decode_invalid_group_shape_raises():
    # Missing the column component.
    with pytest.raises(ValueError):
        decode("1")
    # Too many dot-separated parts.
    with pytest.raises(ValueError):
        decode("1.2.3")
    # Non-numeric components.
    with pytest.raises(ValueError):
        decode("abc")
    # No dot at all.
    with pytest.raises(ValueError):
        decode("11")


def test_decode_out_of_range_raises():
    with pytest.raises(ValueError):
        decode("6.1")  # Row 6 does not exist.
    with pytest.raises(ValueError):
        decode("0.1")  # Row 0 does not exist.
    with pytest.raises(ValueError):
        decode("1.6")  # Row 1 only has 5 columns.
    with pytest.raises(ValueError):
        decode("5.7")  # Row 5 only has 6 columns.


def test_encode_non_alphabetic_raises():
    with pytest.raises(ValueError):
        encode("1")
    with pytest.raises(ValueError):
        encode("HELLO!")
    with pytest.raises(ValueError):
        encode(" ")
    with pytest.raises(ValueError):
        encode("HELLO WORLD")