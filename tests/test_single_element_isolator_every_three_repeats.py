import pytest
from single_element_isolator_every_three_repeats import single_element_isolator_every_three_repeats


def test_basic_case():
    """Single element hidden inside a triplet."""
    assert single_element_isolator_every_three_repeats([2, 2, 3, 2]) == 3


def test_classic_example():
    """The canonical LeetCode 'Single Number II' example."""
    assert single_element_isolator_every_three_repeats([0, 1, 0, 1, 0, 1, 99]) == 99


def test_single_element_list():
    """A list that contains only the unique element returns that element."""
    assert single_element_isolator_every_three_repeats([5]) == 5


def test_empty_list_returns_none():
    """An empty list yields None rather than raising."""
    assert single_element_isolator_every_three_repeats([]) is None


def test_single_at_start():
    """Unique element positioned at the very start of the list."""
    assert single_element_isolator_every_three_repeats([7, 4, 4, 4, 5, 5, 5]) == 7


def test_single_at_end():
    """Unique element positioned at the very end of the list."""
    assert single_element_isolator_every_three_repeats([4, 4, 4, 5, 5, 5, 7]) == 7


def test_single_in_middle():
    """Unique element sandwiched between two triplets."""
    assert single_element_isolator_every_three_repeats([4, 4, 4, 7, 5, 5, 5]) == 7


def test_multiple_triplets_around_single():
    """Several triplets with the unique element between them."""
    assert single_element_isolator_every_three_repeats([1, 1, 1, 2, 3, 3, 3, 4, 4, 4]) == 2


def test_zero_is_single():
    """Zero as the unique single element should be detected correctly."""
    assert single_element_isolator_every_three_repeats([0, 5, 5, 5]) == 0


def test_large_numbers():
    """Verify the bit-manipulation logic works for large integer values."""
    nums = [1000, 1000, 1000, 999999, 7, 7, 7]
    assert single_element_isolator_every_three_repeats(nums) == 999999


def test_does_not_mutate_input():
    """The function must not mutate the caller's list."""
    nums = [0, 1, 0, 1, 0, 1, 99]
    snapshot = list(nums)
    _ = single_element_isolator_every_three_repeats(nums)
    assert nums == snapshot