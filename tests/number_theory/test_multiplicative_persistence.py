"""
Tests for ``number_theory.multiplicative_persistence``.
"""
import os
import sys

import pytest

# Ensure the project root is on sys.path so ``number_theory`` can be imported
# regardless of where pytest is invoked from.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from number_theory.multiplicative_persistence import multiplicative_persistence


def test_zero_has_persistence_zero():
    """Zero is already a single digit, so its persistence is 0."""
    assert multiplicative_persistence(0) == 0


def test_single_digit_numbers_have_persistence_zero():
    """All single digit numbers have persistence 0."""
    for n in range(0, 10):
        assert multiplicative_persistence(n) == 0


def test_10_persistence_1():
    """10 -> 0 has persistence 1."""
    assert multiplicative_persistence(10) == 1


def test_25_persistence_2():
    """25 -> 10 -> 0 has persistence 2."""
    assert multiplicative_persistence(25) == 2


def test_39_persistence_3():
    """39 -> 27 -> 14 -> 4 has persistence 3."""
    assert multiplicative_persistence(39) == 3


def test_77_persistence_4():
    """77 -> 49 -> 36 -> 18 -> 8 has persistence 4."""
    assert multiplicative_persistence(77) == 4


def test_999_persistence_4():
    """999 -> 729 -> 126 -> 12 -> 2 has persistence 4."""
    assert multiplicative_persistence(999) == 4


def test_679_persistence_5():
    """679 -> 378 -> 168 -> 48 -> 32 -> 6 has persistence 5."""
    assert multiplicative_persistence(679) == 5


def test_known_record_holder_persistence_11():
    """277777788888899 is the smallest number with persistence 11 (the record)."""
    assert multiplicative_persistence(277777788888899) == 11


def test_terminates_for_typical_inputs():
    """Spot-check termination for a handful of additional inputs."""
    # 4 -> 4 (single digit) -> persistence 0
    assert multiplicative_persistence(4) == 0
    # 12 -> 2 -> persistence 1
    assert multiplicative_persistence(12) == 1
    # 1234 -> 24 -> 8 -> persistence 2
    assert multiplicative_persistence(1234) == 2


def test_negative_input_raises_value_error():
    """Negative inputs are not allowed and must raise ``ValueError``."""
    with pytest.raises(ValueError):
        multiplicative_persistence(-1)
    with pytest.raises(ValueError):
        multiplicative_persistence(-100)


def test_non_integer_input_raises_type_error():
    """Non-integer inputs must raise ``TypeError``."""
    with pytest.raises(TypeError):
        multiplicative_persistence(1.5)
    with pytest.raises(TypeError):
        multiplicative_persistence("10")
    with pytest.raises(TypeError):
        multiplicative_persistence(None)
    with pytest.raises(TypeError):
        multiplicative_persistence([1, 2, 3])


def test_boolean_input_raises_type_error():
    """Booleans are technically ``int`` but should be rejected here."""
    with pytest.raises(TypeError):
        multiplicative_persistence(True)
    with pytest.raises(TypeError):
        multiplicative_persistence(False)