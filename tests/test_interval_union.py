"""Tests for ``interval_union``."""

import pytest

from interval_union import interval_union


class TestIntervalUnion:
    # --- trivial inputs ----------------------------------------------------

    def test_empty_list(self):
        assert interval_union([]) == []

    def test_none_input(self):
        assert interval_union(None) == []

    def test_single_interval_tuple(self):
        assert interval_union([(1, 3)]) == [(1, 3)]

    def test_single_interval_list(self):
        assert interval_union([[1, 3]]) == [(1, 3)]

    # --- basic geometry ----------------------------------------------------

    def test_no_overlap_preserves_order(self):
        assert interval_union([(1, 3), (5, 7), (10, 12)]) == [
            (1, 3),
            (5, 7),
            (10, 12),
        ]

    def test_overlapping_intervals_merged(self):
        assert interval_union([(1, 4), (2, 5)]) == [(1, 5)]

    def test_touching_intervals_merged(self):
        # [1, 3] and [3, 5] share the point 3, so the union is [1, 5].
        assert interval_union([(1, 3), (3, 5)]) == [(1, 5)]

    def test_chain_of_touching_intervals(self):
        assert interval_union([(1, 2), (2, 3), (3, 4), (5, 6)]) == [
            (1, 4),
            (5, 6),
        ]

    def test_one_interval_inside_another(self):
        assert interval_union([(1, 10), (3, 7), (5, 6)]) == [(1, 10)]

    def test_duplicate_intervals_merged(self):
        assert interval_union([(1, 3), (1, 3)]) == [(1, 3)]

    # --- input ordering / iterables ---------------------------------------

    def test_unsorted_input_is_sorted_in_output(self):
        assert interval_union([(10, 12), (1, 3), (5, 7)]) == [
            (1, 3),
            (5, 7),
            (10, 12),
        ]

    def test_generator_input(self):
        gen = ((s, e) for s, e in [(1, 3), (2, 5), (7, 9)])
        assert interval_union(gen) == [(1, 5), (7, 9)]

    # --- complex / mixed cases --------------------------------------------

    def test_complex_overlapping_groups(self):
        assert interval_union([(1, 4), (2, 5), (7, 9), (8, 12), (11, 14)]) == [
            (1, 5),
            (7, 14),
        ]

    def test_negative_intervals(self):
        assert interval_union([(-5, -1), (-3, 2)]) == [(-5, 2)]

    def test_mixed_signs(self):
        assert interval_union([(-2, 0), (0, 3), (2, 5)]) == [(-2, 5)]

    def test_float_intervals(self):
        assert interval_union([(1.5, 2.5), (2.0, 3.0)]) == [(1.5, 3.0)]

    # --- invalid inputs ----------------------------------------------------

    def test_invalid_intervals_skipped(self):
        # (3, 1) is inverted and should be ignored; the valid one is kept.
        assert interval_union([(3, 1), (1, 3)]) == [(1, 3)]

    def test_all_invalid_returns_empty(self):
        assert interval_union([(3, 1), (5, 2)]) == []

    def test_malformed_items_ignored(self):
        # 42 is not a 2-element sequence -> skipped.
        assert interval_union([(1, 3), 42, (5, 7)]) == [(1, 3), (5, 7)]

    # --- return-type contract ---------------------------------------------

    def test_returns_list_of_tuples(self):
        result = interval_union([[1, 3], [5, 7]])
        assert isinstance(result, list)
        for iv in result:
            assert isinstance(iv, tuple)
            assert len(iv) == 2

    def test_output_intervals_are_disjoint_and_sorted(self):
        result = interval_union([(1, 4), (2, 5), (7, 9), (8, 12), (0, 0)])
        for (a_start, a_end), (b_start, b_end) in zip(result, result[1:]):
            assert a_end < b_start, f"overlap detected: {result}"
            assert a_start <= a_end
            assert b_start <= b_end