"""
Tests for ``missions_concentric_ring_mn_maxima_collector``.
"""
import pytest

from src.missions_concentric_ring_mn_maxima_collector import (
    missions_concentric_ring_mn_maxima_collector,
)


class TestEdgeCases:
    def test_rings_with_no_angles_yield_empty_lists(self):
        """No measurements => every ring has an empty list, all indices present."""
        rings = [(0, 1), (1, 2), (2, 3)]
        result = missions_concentric_ring_mn_maxima_collector(rings, None)
        assert set(result.keys()) == {0, 1, 2}
        assert all(v == [] for v in result.values())

    def test_empty_rings_list(self):
        """An empty rings list should return an empty dict."""
        assert missions_concentric_ring_mn_maxima_collector([], None) == {}

    def test_empty_measurements_dict(self):
        """Empty measurements dict should yield empty lists for every ring."""
        rings = [(0, 1), (1, 2)]
        result = missions_concentric_ring_mn_maxima_collector(rings, {})
        assert result == {0: [], 1: []}

    def test_measurements_none_treated_as_empty(self):
        rings = [(0, 1), (1, 2), (2, 3)]
        result = missions_concentric_ring_mn_maxima_collector(rings, None)
        assert len(result) == 3
        for value in result.values():
            assert value == []


class TestBasicFunctionality:
    def test_single_ring_single_angle(self):
        rings = [(0, 1)]
        measurements = {0: {0.0: [1, 2, 3]}}
        result = missions_concentric_ring_mn_maxima_collector(rings, measurements)
        assert result == {0: [3]}

    def test_multiple_rings_single_angle(self):
        rings = [(0, 1), (1, 2), (2, 3)]
        measurements = {
            0: {0: [1, 2]},
            1: {0: [3, 4]},
            2: {0: [5, 6]},
        }
        result = missions_concentric_ring_mn_maxima_collector(rings, measurements)
        assert result == {0: [2], 1: [4], 2: [6]}

    def test_multiple_angles_per_ring(self):
        rings = [(0, 1)]
        measurements = {
            0: {
                0: [1, 2],
                1: [3, 4],
                2: [5, 6],
            }
        }
        result = missions_concentric_ring_mn_maxima_collector(rings, measurements)
        assert isinstance(result[0], list)
        assert sorted(result[0]) == [2, 4, 6]

    def test_empty_value_list_is_skipped(self):
        """An angle with no values should not contribute a maximum."""
        rings = [(0, 1)]
        measurements = {0: {0: [], 1: [10, 20]}}
        result = missions_concentric_ring_mn_maxima_collector(rings, measurements)
        assert result[0] == [20]

    def test_undeclared_ring_measurements_are_ignored(self):
        rings = [(0, 1)]  # only index 0 exists
        measurements = {
            0: {0: [1, 2]},
            5: {0: [99]},  # ring 5 was not declared
        }
        result = missions_concentric_ring_mn_maxima_collector(rings, measurements)
        assert 5 not in result
        assert result == {0: [2]}

    def test_partial_measurements_keep_missing_rings_empty(self):
        rings = [(0, 1), (1, 2), (2, 3)]
        measurements = {1: {0: [7, 8, 9]}}
        result = missions_concentric_ring_mn_maxima_collector(rings, measurements)
        assert result == {0: [], 1: [9], 2: []}


def test_returns_dict_type():
    rings = [(0, 1), (1, 2)]
    result = missions_concentric_ring_mn_maxima_collector(rings, None)
    assert isinstance(result, dict)


def test_negative_values_handled():
    rings = [(0, 1)]
    measurements = {0: {0: [-5, -2, -10]}}
    result = missions_concentric_ring_mn_maxima_collector(rings, measurements)
    assert result == {0: [-2]}