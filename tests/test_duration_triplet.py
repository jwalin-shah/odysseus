"""
Tests for `duration_triplet`.

Run with: pytest test_duration_triplet.py
"""

import pytest

# Import from the implementation module using the correct relative path.
# The tests directory is a sibling of the implementation module's parent,
# so we add the project root to sys.path if necessary.
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)

from duration_triplet import duration_triplet


class TestDurationTripletBasic:
    """Basic correctness tests for duration_triplet."""

    def test_zero_seconds(self):
        assert duration_triplet(0) == (0, 0, 0)

    def test_one_second(self):
        assert duration_triplet(1) == (0, 0, 1)

    def test_only_seconds_under_a_minute(self):
        assert duration_triplet(45) == (0, 0, 45)

    def test_exactly_one_minute(self):
        assert duration_triplet(60) == (0, 1, 0)

    def test_only_minutes(self):
        assert duration_triplet(125) == (0, 2, 5)

    def test_exactly_one_hour(self):
        assert duration_triplet(3600) == (1, 0, 0)

    def test_one_hour_one_minute_one_second(self):
        assert duration_triplet(3661) == (1, 1, 1)

    def test_large_value(self):
        # 7325 seconds = 2h 2m 5s
        assert duration_triplet(7325) == (2, 2, 5)

    def test_returns_tuple_of_ints(self):
        result = duration_triplet(3723)
        assert isinstance(result, tuple)
        assert len(result) == 3
        for component in result:
            assert isinstance(component, int)
            assert component >= 0


class TestDurationTripletFractional:
    """Fractional seconds should be truncated, not rounded."""

    def test_fractional_truncates_down(self):
        assert duration_triplet(59.9) == (0, 0, 59)

    def test_fractional_truncates_toward_zero(self):
        # 45.7 -> 45 seconds
        assert duration_triplet(45.7) == (0, 0, 45)

    def test_fractional_just_under_next_minute(self):
        assert duration_triplet(119.999) == (0, 1, 59)


class TestDurationTripletErrors:
    """Error handling: bad input types and negative values."""

    def test_negative_raises_value_error(self):
        with pytest.raises(ValueError):
            duration_triplet(-1)

    def test_string_input_raises_type_error(self):
        with pytest.raises(TypeError):
            duration_triplet("3600")

    def test_none_raises_type_error(self):
        with pytest.raises(TypeError):
            duration_triplet(None)

    def test_list_input_raises_type_error(self):
        with pytest.raises(TypeError):
            duration_triplet([3600])

    def test_bool_input_raises_type_error(self):
        # booleans are a subclass of int in Python, but logically
        # they are not a "duration"; the implementation rejects them.
        with pytest.raises(TypeError):
            duration_triplet(True)


class TestDurationTripletProperties:
    """Property-based checks that should always hold."""

    @pytest.mark.parametrize("seconds", [0, 1, 59, 60, 3599, 3600, 3661, 7325, 86399, 100000])
    def test_round_trip_identity(self, seconds):
        """Re-flattening the triplet should yield the original (truncated) seconds."""
        h, m, s = duration_triplet(seconds)
        assert h * 3600 + m * 60 + s == int(seconds)

    @pytest.mark.parametrize("seconds", [0, 1, 59, 60, 3599, 3600, 3661, 7325, 86399, 100000])
    def test_components_within_bounds(self, seconds):
        """Minutes and seconds must always be in the range [0, 59]."""
        _, m, s = duration_triplet(seconds)
        assert 0 <= m < 60
        assert 0 <= s < 60
        assert _ >= 0