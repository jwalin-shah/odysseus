"""Tests for the ``range_compressor`` function."""

import pytest

from range_compressor import range_compressor


class TestRangeCompressor:
    """Behavioural tests for ``range_compressor``."""

    # --- Edge cases -------------------------------------------------------

    def test_empty_iterable_returns_empty_list(self):
        """An empty input must produce an empty result list."""
        assert range_compressor([]) == []

    def test_empty_tuple_returns_empty_list(self):
        """An empty tuple should be treated the same as an empty list."""
        assert range_compressor(()) == []

    def test_single_element_becomes_singleton_range(self):
        """A single number should be returned as ``(value, value)``."""
        assert range_compressor([5]) == [(5, 5)]
        assert range_compressor([0]) == [(0, 0)]
        assert range_compressor([-42]) == [(-42, -42)]

    # --- Basic grouping ---------------------------------------------------

    def test_all_consecutive_collapse_to_single_range(self):
        """Strictly consecutive numbers should form one inclusive range."""
        assert range_compressor([1, 2, 3, 4, 5]) == [(1, 5)]

    def test_no_consecutive_numbers_are_all_singletons(self):
        """Numbers with no two being adjacent should each be a singleton."""
        assert range_compressor([1, 3, 5, 7]) == [
            (1, 1),
            (3, 3),
            (5, 5),
            (7, 7),
        ]

    def test_mixed_consecutive_and_gapped(self):
        """A typical mix of runs and gaps should compress correctly."""
        assert range_compressor([1, 2, 3, 5, 7, 8, 10]) == [
            (1, 3),
            (5, 5),
            (7, 8),
            (10, 10),
        ]

    def test_two_consecutive_numbers(self):
        """Two consecutive numbers form a single two-element range."""
        assert range_compressor([4, 5]) == [(4, 5)]

    def test_gap_of_exactly_one(self):
        """A gap of exactly one should split the input into two ranges."""
        assert range_compressor([1, 2, 4, 5]) == [(1, 2), (4, 5)]

    # --- Sorting & duplicates --------------------------------------------

    def test_unsorted_input_is_sorted(self):
        """The function should sort the input internally."""
        assert range_compressor([10, 1, 3, 2, 8, 7, 5]) == [
            (1, 3),
            (5, 5),
            (7, 8),
            (10, 10),
        ]

    def test_duplicates_are_removed(self):
        """Repeated values should not produce duplicate ranges."""
        assert range_compressor([1, 1, 2, 2, 3, 3]) == [(1, 3)]
        assert range_compressor([1, 2, 3, 1, 2, 3]) == [(1, 3)]
        assert range_compressor([5, 5, 5]) == [(5, 5)]

    def test_set_input_is_accepted(self):
        """A set (which is unordered) should be handled without error."""
        assert range_compressor({1, 2, 3, 5}) == [(1, 3), (5, 5)]

    def test_generator_input_is_accepted(self):
        """A generator expression should be consumed correctly."""
        gen = (x for x in [1, 2, 3, 5, 7, 8, 10])
        assert range_compressor(gen) == [(1, 3), (5, 5), (7, 8), (10, 10)]

    # --- Sign handling ----------------------------------------------------

    def test_negative_numbers(self):
        """Negative numbers should be handled just like positives."""
        assert range_compressor([-3, -2, -1, 0, 1, 2]) == [(-3, 2)]

    def test_only_negative_numbers(self):
        """A run of strictly negative numbers should compress as expected."""
        assert range_compressor([-5, -3, -1]) == [
            (-5, -5),
            (-3, -3),
            (-1, -1),
        ]

    def test_zero_included_in_run(self):
        """Zero should be treated as a normal integer value."""
        assert range_compressor([0, 1, 2]) == [(0, 2)]
        assert range_compressor([-1, 0, 1]) == [(-1, 1)]

    # --- Structural / return-type guarantees -----------------------------

    def test_returns_list(self):
        """The function should always return a list instance."""
        assert isinstance(range_compressor([1, 2, 3]), list)
        assert isinstance(range_compressor([]), list)

    def test_each_range_element_is_tuple_of_two_ints(self):
        """Every range should be a 2-tuple of integers."""
        result = range_compressor([1, 2, 3, 5, 7, 8, 10])
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            start, end = item
            assert isinstance(start, int)
            assert isinstance(end, int)
            assert start <= end

    def test_ranges_are_in_ascending_order(self):
        """The returned ranges should appear in ascending order of start."""
        result = range_compressor([1, 2, 10, 11, 12, 20])
        assert result == [(1, 2), (10, 12), (20, 20)]
        # Verify monotonicity explicitly.
        for (a, _), (b, _) in zip(result, result[1:]):
            assert a < b

    # --- Larger / performance-flavoured cases ----------------------------

    def test_large_contiguous_block(self):
        """A long contiguous block should compress into a single range."""
        numbers = list(range(1, 101))
        assert range_compressor(numbers) == [(1, 100)]

    def test_multiple_large_blocks(self):
        """Several large blocks separated by gaps should all be detected."""
        numbers = list(range(1, 51)) + list(range(100, 151)) + [200, 201, 202]
        assert range_compressor(numbers) == [(1, 50), (100, 150), (200, 202)]

    def test_round_trip_lengths(self):
        """Re-expanding the ranges should yield the original unique numbers."""
        original = [1, 2, 3, 5, 7, 8, 10, 11, 12, 20]
        ranges = range_compressor(original)
        expanded = [n for start, end in ranges for n in range(start, end + 1)]
        assert expanded == sorted(set(original))


# --- Parametrised sanity check ------------------------------------------------

@pytest.mark.parametrize(
    "input_seq, expected",
    [
        ([], []),
        ([1], [(1, 1)]),
        ([1, 2], [(1, 2)]),
        ([1, 3], [(1, 1), (3, 3)]),
        ([1, 2, 3, 4], [(1, 4)]),
        ([1, 2, 4, 5, 6, 10], [(1, 2), (4, 6), (10, 10)]),
        ([3, 1, 2], [(1, 3)]),
        ([2, 2, 2, 3, 4, 4], [(2, 4)]),
        ([-2, -1, 0, 1], [(-2, 1)]),
    ],
)
def test_range_compressor_parametrised(input_seq, expected):
    """A quick parametrised smoke test covering several scenarios at once."""
    assert range_compressor(input_seq) == expected
    assert range_compressor(list(input_seq)) == expected