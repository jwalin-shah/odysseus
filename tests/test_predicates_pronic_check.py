"""Tests for the pronic (oblong) number predicate.

Run with::

    pytest tests/test_predicates_pronic_check.py
"""

from __future__ import annotations

import math
import os
import sys

import pytest

# Make the ``src`` package importable when running pytest from the repo root.
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from predicates_pronic_check import is_pronic, predicates_pronic_check  # noqa: E402


# ---------------------------------------------------------------------------
# Known pronic numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "n",
    [0, 2, 6, 12, 20, 30, 42, 56, 72, 90, 110, 132, 156, 182, 210],
)
def test_known_pronic_numbers(n):
    assert is_pronic(n) is True


# ---------------------------------------------------------------------------
# Known non-pronic numbers (no k*(k+1) produces them)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "n",
    [1, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 21, 23, 25, 99],
)
def test_known_non_pronic_numbers(n):
    assert is_pronic(n) is False


# ---------------------------------------------------------------------------
# Generated sequences
# ---------------------------------------------------------------------------

def test_first_twenty_pronic_numbers_are_pronic():
    for k in range(20):
        assert is_pronic(k * (k + 1)) is True


def test_strictly_between_two_consecutive_pronic_numbers_is_not_pronic():
    """For every k, the open interval (k*(k+1), (k+1)*(k+2)) contains no
    pronic numbers."""
    for k in range(1, 50):
        lo = k * (k + 1)
        hi = (k + 1) * (k + 2)
        for n in range(lo + 1, hi):
            assert is_pronic(n) is False, f"{n} should not be pronic"


# ---------------------------------------------------------------------------
# Large values
# ---------------------------------------------------------------------------

def test_large_pronic_100x101():
    assert is_pronic(100 * 101) is True


def test_large_pronic_1000x1001():
    assert is_pronic(1000 * 1001) is True


def test_very_large_pronic_50000x50001():
    assert is_pronic(50000 * 50001) is True


def test_large_non_pronic():
    # Closest pronic numbers around 10001 are 99*100=9900 and 100*101=10100.
    assert is_pronic(10001) is False


# ---------------------------------------------------------------------------
# Specific edge cases
# ---------------------------------------------------------------------------

def test_zero_is_pronic():
    # 0 = 0 * 1
    assert is_pronic(0) is True


def test_one_is_not_pronic():
    assert is_pronic(1) is False


def test_negative_numbers_are_not_pronic():
    for n in (-1, -2, -6, -12, -20, -100, -10000):
        assert is_pronic(n) is False


# ---------------------------------------------------------------------------
# Non-integer / unusual inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [2.0, 6.0, 0.0, 0.5, 2.5, -2.0, math.nan, math.inf, -math.inf])
def test_floats_are_not_pronic(value):
    assert is_pronic(value) is False


@pytest.mark.parametrize("value", ["2", "6", "0", "", "pronic", " 2 "])
def test_strings_are_not_pronic(value):
    assert is_pronic(value) is False


def test_none_is_not_pronic():
    assert is_pronic(None) is False


@pytest.mark.parametrize("value", [True, False])
def test_bools_are_not_pronic(value):
    assert is_pronic(value) is False


def test_list_input_is_not_pronic():
    assert is_pronic([0, 2, 6]) is False
    assert is_pronic([]) is False


def test_dict_input_is_not_pronic():
    assert is_pronic({0: "zero", 1: "one"}) is False


# ---------------------------------------------------------------------------
# Module-name alias
# ---------------------------------------------------------------------------

def test_module_alias_is_same_function():
    assert predicates_pronic_check is is_pronic


def test_module_alias_behaves_identically():
    for n in range(-5, 100):
        assert predicates_pronic_check(n) is is_pronic(n)