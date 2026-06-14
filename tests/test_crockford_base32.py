"""Tests for crockford_base32 encode/decode."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from crockford_base32 import encode, decode

# Crockford alphabet: 0123456789ABCDEFGHJKMNPQRSTVWXYZ
# V is at index 27, Z is at index 31

def test_encode_zero():
    assert encode(0) == "0"

def test_encode_small():
    assert encode(1) == "1"
    assert encode(9) == "9"
    assert encode(10) == "A"

def test_encode_v_position():
    assert encode(27) == "V"

def test_encode_z_position():
    assert encode(31) == "Z"

def test_encode_32():
    assert encode(32) == "10"

def test_decode_digits():
    assert decode("0") == 0
    assert decode("9") == 9

def test_decode_letters():
    assert decode("A") == 10
    assert decode("Z") == 31

def test_decode_v_is_27():
    """V is at position 27 in Crockford alphabet (not 31 — Z is 31)."""
    assert decode("V") == 27
    assert decode("v") == 27

def test_decode_case_insensitive():
    assert decode("a") == decode("A")
    assert decode("z") == decode("Z") == 31

def test_decode_aliases_o():
    """O and o are aliases for 0."""
    assert decode("O") == 0
    assert decode("o") == 0

def test_decode_aliases_i_l():
    """I, i, L, l are aliases for 1."""
    assert decode("I") == 1
    assert decode("i") == 1
    assert decode("L") == 1
    assert decode("l") == 1

def test_roundtrip():
    for n in [0, 1, 31, 32, 255, 1000, 2**20]:
        assert decode(encode(n)) == n

def test_encode_negative_raises():
    with pytest.raises(ValueError):
        encode(-1)

def test_decode_invalid_char_raises():
    with pytest.raises(ValueError):
        decode("U")
