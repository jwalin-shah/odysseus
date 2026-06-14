"""Tests for the Kish-Lengyel prime conjuncture validation predicate."""

import pytest

from src.validation_predicates_kish_lengyel_prime_conjuncture_predicate import (
    validation_predicates_kish_lengyel_prime_conjuncture_predicate,
)


def test_prime_numbers_satisfy_predicate():
    """Known prime numbers should satisfy the predicate (return True)."""
    primes = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 97, 101, 103, 211, 997]
    for prime in primes:
        assert (
            validation_predicates_kish_lengyel_prime_conjuncture_predicate(prime)
            is True
        )


def test_composite_numbers_fail_predicate():
    """Known composite numbers should fail the predicate (return False)."""
    composites = [4, 6, 8, 9, 10, 12, 14, 15, 16, 18, 20, 21, 25, 27, 49, 100, 1000]
    for composite in composites:
        assert (
            validation_predicates_kish_lengyel_prime_conjuncture_predicate(composite)
            is False
        )


def test_conjuncture_fails_at_n_100():
    """The conjuncture should fail (return False) for n=100."""
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(100) is False
    )


def test_edge_cases_below_two():
    """Values less than 2 should fail the predicate."""
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(0) is False
    )
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(1) is False
    )
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(-1) is False
    )
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(-100) is False
    )


def test_non_integer_inputs_return_false():
    """Non-integer inputs should return False."""
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(2.5) is False
    )
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(4.0) is False
    )
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate("7") is False
    )
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(None) is False
    )
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate([2]) is False
    )


def test_large_prime_satisfies_predicate():
    """A large prime number should satisfy the predicate."""
    # 7919 is prime
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(7919) is True
    )
    # 10007 is prime
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(10007) is True
    )


def test_large_composite_fails_predicate():
    """A large composite number should fail the predicate."""
    # 7917 = 3 * 2639
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(7917) is False
    )
    # 10000 = 2^4 * 5^4
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(10000) is False
    )


def test_two_is_prime():
    """The number 2 is the only even prime and should satisfy the predicate."""
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(2) is True
    )


def test_one_is_not_prime():
    """The number 1 is not considered prime by definition."""
    assert (
        validation_predicates_kish_lengyel_prime_conjuncture_predicate(1) is False
    )