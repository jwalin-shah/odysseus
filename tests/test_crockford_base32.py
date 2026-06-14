"""Tests for crockford_base32."""

import pytest

from crockford_base32 import encode, decode


# ----- Empty / whitespace handling -----

def test_encode_empty():
    assert encode(b"") == ""


def test_decode_empty():
    assert decode("") == b""


def test_decode_only_whitespace():
    assert decode("   ") == b""


def test_decode_only_hyphens():
    assert decode("---") == b""


def test_decode_whitespace_and_hyphens():
    assert decode(" - - - ") == b""


# ----- Single byte roundtrips -----

def test_encode_single_zero_byte():
    assert encode(b"\x00") == "00"


def test_decode_single_zero():
    assert decode("00") == b"\x00"


@pytest.mark.parametrize("byte_val,expected", [
    (0x00, "00"),
    (0x01, "01"),
    (0x0A, "0A"),
    (0x1F, "0Z"),
    (0x20, "10"),
    (0x3F, "1Z"),
    (0x40, "20"),
    (0x7F, "3Z"),
    (0x80, "40"),
    (0xFF, "7Z"),
])
def test_encode_single_byte_values(byte_val, expected):
    assert encode(bytes([byte_val])) == expected


@pytest.mark.parametrize("encoded,expected", [
    ("00", b"\x00"),
    ("01", b"\x01"),
    ("0A", b"\x0A"),
    ("0Z", b"\x1F"),
    ("10", b"\x20"),
    ("1Z", b"\x3F"),
    ("20", b"\x40"),
    ("3Z", b"\x7F"),
    ("40", b"\x80"),
    ("7Z", b"\xFF"),
])
def test_decode_single_byte_values(encoded, expected):
    assert decode(encoded) == expected


# ----- Multi-byte values -----

def test_encode_two_bytes():
    # 0xFFFF = 65535 = 1*32^3 + 31*32^2 + 31*32 + 31 = "1ZZZ"
    assert encode(b"\xFF\xFF") == "1ZZZ"


def test_decode_two_bytes():
    assert decode("1ZZZ") == b"\xFF\xFF"


def test_encode_two_zero_bytes():
    assert encode(b"\x00\x00") == "0000"


def test_decode_two_zero_bytes():
    assert decode("0000") == b"\x00\x00"


def test_encode_known_mixed():
    # 0x0100 = 256 = 8*32 + 0 -> "80", padded to 4 chars -> "0080"
    assert encode(b"\x01\x00") == "0080"
    assert decode("0080") == b"\x01\x00"


# ----- Hyphen and whitespace tolerance in decoding -----

def test_decode_hyphens_and_whitespace():
    # "7Z-7Z" normalizes to "7Z7Z".
    # 7Z7Z = 7*32^3 + 31*32^2 + 7*32 + 31 = 261375 = 0x03FCFF
    assert decode("7Z-7Z") == b"\x03\xFC\xFF"
    assert decode(" 7Z 7Z ") == b"\x03\xFC\xFF"
    assert decode("7Z-7-Z") == b"\x03\xFC\xFF"
    assert decode("7Z\n7Z") == b"\x03\xFC\xFF"
    assert decode("\t7Z-7Z\t") == b"\x03\xFC\xFF"


# ----- Case insensitivity -----

def test_decode_lowercase():
    assert decode("7z") == b"\xFF"
    assert decode("1zzz") == b"\xFF\xFF"


def test_decode_mixed_case():
    assert decode("1ZzZ") == b"\xFF\xFF"
    assert decode("7z7Z") == b"\x03\xFC\xFF"


# ----- Common visual aliases -----

def test_decode_alias_i():
    assert decode("I") == b"\x01"
    assert decode("i") == b"\x01"


def test_decode_alias_l():
    assert decode("L") == b"\x01"
    assert decode("l") == b"\x01"


def test_decode_alias_o():
    assert decode("O") == b"\x00"
    assert decode("o") == b"\x00"


# ----- Invalid characters -----

def test_decode_invalid_character():
    # 'U' is not in the Crockford Base32 alphabet.
    with pytest.raises(ValueError):
        decode("U")


def test_decode_invalid_with_punctuation():
    with pytest.raises(ValueError):
        decode("7Z!")


# ----- Roundtrip property -----

@pytest.mark.parametrize("data", [
    b"\x01",
    b"\x0A",
    b"\x1F",
    b"\x20",
    b"\x7F",
    b"\x80",
    b"\xFF",
    b"\xFF\xFF",
    b"\x00\x00",
    b"\x00\x01",
    b"Hello",
    b"Hello, World!",
    bytes(range(1, 17)),
    bytes(range(1, 33)),
])
def test_roundtrip(data):
    encoded = encode(data)
    assert decode(encoded) == data