"""Tests for ``legendre_factorial_prime_exponent``.

The implementation lives at
``src/number_theory/legendre_factorial_prime_exponent.py``.  Because this
test file is located at ``tests/src/number_theory/`` we cannot rely on the
ordinary ``src.number_theory`` package import (the directory may not have an
``__init__.py`` in some check-out layouts).  We therefore add the source
directory directly to ``sys.path`` and import the module by its bare name.
"""

import os
import sys

# Path to the directory containing the implementation module.
_IMPL_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "src", "number_theory")
)
if _IMPL_DIR not in sys.path:
    sys.path.insert(0, _IMPL_DIR)

from legendre_factorial_prime_exponent import (  # noqa: E402
    legendre_factorial_prime_exponent,
    prime_factorial_exponent,
)

import pytest  # noqa: E402


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------

def test_exponent_of_2_in_5_factorial():
    # 5! = 120 = 2^3 * 3 * 5
    assert legendre_factorial_prime_exponent(5, 2) == 3


def test_exponent_of_3_in_5_factorial():
    # 5! = 120 = 2^3 * 3^1 * 5
    assert legendre_factorial_prime_exponent(5, 3) == 1


def test_exponent_of_5_in_5_factorial():
    # 5! contains 5 exactly once
    assert legendre_factorial_prime_exponent(5, 5) == 1


def test_exponent_in_10_factorial():
    # 10! = 2^8 * 3^4 * 5^2 * 7^1
    assert legendre_factorial_prime_exponent(10, 2) == 8
    assert legendre_factorial_prime_exponent(10, 3) == 4
    assert legendre_factorial_prime_exponent(10, 5) == 2
    assert legendre_factorial_prime_exponent(10, 7) == 1


def test_exponent_in_25_factorial_for_5():
    # floor(25/5) + floor(25/25) = 5 + 1 = 6
    assert legendre_factorial_prime_exponent(25, 5) == 6


def test_exponent_of_2_in_100_factorial():
    # floor(100/2)=50, /4=25, /8=12, /16=6, /32=3, /64=1 => 97
    assert legendre_factorial_prime_exponent(100, 2) == 97


def test_exponent_of_3_in_100_factorial():
    # floor(100/3)=33, /9=11, /27=3, /81=1 => 48
    assert legendre_factorial_prime_exponent(100, 3) == 48


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_zero_factorial_has_no_prime_factors():
    # 0! = 1, so every prime appears with exponent 0.
    assert legendre_factorial_prime_exponent(0, 2) == 0
    assert legendre_factorial_prime_exponent(0, 7) == 0


def test_one_factorial_has_no_prime_factors():
    # 1! = 1
    assert legendre_factorial_prime_exponent(1, 2) == 0
    assert legendre_factorial_prime_exponent(1, 13) == 0


def test_prime_larger_than_n_gives_zero():
    # If p > n, then p does not appear in 1*2*...*n at all.
    assert legendre_factorial_prime_exponent(3, 5) == 0
    assert legendre_factorial_prime_exponent(10, 11) == 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_negative_n_raises():
    with pytest.raises(ValueError):
        legendre_factorial_prime_exponent(-1, 2)


def test_p_less_than_2_raises():
    with pytest.raises(ValueError):
        legendre_factorial_prime_exponent(10, 1)
    with pytest.raises(ValueError):
        legendre_factorial_prime_exponent(10, 0)


def test_non_integer_n_raises():
    with pytest.raises(TypeError):
        legendre_factorial_prime_exponent(1.5, 2)  # type: ignore[arg-type]


def test_non_integer_p_raises():
    with pytest.raises(TypeError):
        legendre_factorial_prime_exponent(10, 2.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Alias
# ---------------------------------------------------------------------------

def test_alias_matches_main_function():
    for n in [0, 1, 2, 5, 10, 25, 100]:
        for p in [2, 3, 5, 7, 11, 13]:
            assert (
                prime_factorial_exponent(n, p)
                == legendre_factorial_prime_exponent(n, p)
            )