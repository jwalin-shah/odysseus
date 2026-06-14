"""Tests for ``predicates_moran_number``."""
import os
import sys

# Make the ``src`` directory importable regardless of how pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from predicates_moran_number import predicates_moran_number


def test_moran_18():
    # 18 / (1 + 8) == 2 (prime)
    assert predicates_moran_number(18) is True


def test_moran_21():
    # 21 / (2 + 1) == 7 (prime)
    assert predicates_moran_number(21) is True


def test_moran_27():
    # 27 / (2 + 7) == 3 (prime)
    assert predicates_moran_number(27) is True


def test_moran_42():
    # 42 / (4 + 2) == 7 (prime)
    assert predicates_moran_number(42) is True


def test_moran_45():
    # 45 / (4 + 5) == 5 (prime)
    assert predicates_moran_number(45) is True


def test_moran_63():
    # 63 / (6 + 3) == 7 (prime)
    assert predicates_moran_number(63) is True


def test_moran_84():
    # 84 / (8 + 4) == 7 (prime)
    assert predicates_moran_number(84) is True


def test_moran_117():
    # 117 / (1 + 1 + 7) == 13 (prime)
    assert predicates_moran_number(117) is True


def test_moran_153():
    # 153 / (1 + 5 + 3) == 17 (prime)
    assert predicates_moran_number(153) is True


def test_moran_171():
    # 171 / (1 + 7 + 1) == 19 (prime)
    assert predicates_moran_number(171) is True


def test_not_moran_12():
    # 12 / (1 + 2) == 4 (not prime)
    assert predicates_moran_number(12) is False


def test_not_moran_20():
    # 20 / (2 + 0) == 10 (not prime)
    assert predicates_moran_number(20) is False


def test_not_moran_99():
    # 99 / (9 + 9) is not an integer
    assert predicates_moran_number(99) is False


def test_not_moran_1():
    # 1 / 1 == 1 (not prime)
    assert predicates_moran_number(1) is False


def test_not_moran_0():
    assert predicates_moran_number(0) is False


def test_not_moran_negative():
    assert predicates_moran_number(-18) is False


def test_not_moran_non_integer():
    assert predicates_moran_number(18.0) is False
    assert predicates_moran_number("18") is False
    assert predicates_moran_number(None) is False


def test_not_moran_boolean():
    # In Python bool is a subclass of int, but a boolean is not a Moran number.
    assert predicates_moran_number(True) is False
    assert predicates_moran_number(False) is False


def test_moran_large():
    # 2 * 2 * 3 * 3 * 3 * 7 * 7 * 13 == 4 * 27 * 49 * 13 == 68644? Let's pick
    # a known value: 1026 -> 1+0+2+6 = 9, 1026 / 9 = 114 (not prime).
    # 1029 -> 1+0+2+9 = 12, 1029 / 12 = 85.75 (not integer).
    # Use 12 * 97 = 1164, 1+1+6+4=12, 1164/12=97 (prime) -> Moran.
    assert predicates_moran_number(1164) is True
    # 12 * 101 = 1212, 1+2+1+2=6, 1212/6=202 (not prime).
    assert predicates_moran_number(1212) is False