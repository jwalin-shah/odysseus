"""Tests for :func:`compact_duration`."""

from __future__ import annotations

import os
import sys

import pytest

# Make the module-under-test importable when pytest is run from the repo root.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from compact_duration import compact_duration  # noqa: E402


def test_zero_returns_zero_seconds():
    assert compact_duration(0) == "0s"


def test_seconds_only():
    assert compact_duration(1) == "1s"
    assert compact_duration(45) == "45s"
    assert compact_duration(59) == "59s"


def test_exact_minute_drops_seconds():
    assert compact_duration(60) == "1m"
    assert compact_duration(120) == "2m"
    assert compact_duration(5 * 60) == "5m"


def test_minutes_and_seconds():
    assert compact_duration(90) == "1m 30s"
    assert compact_duration(125) == "2m 5s"


def test_exact_hour_drops_minutes_and_seconds():
    assert compact_duration(3600) == "1h"
    assert compact_duration(2 * 3600) == "2h"


def test_hours_minutes_seconds_combined():
    assert compact_duration(3661) == "1h 1m 1s"
    assert compact_duration(7325) == "2h 2m 5s"


def test_exact_day_drops_smaller_units():
    assert compact_duration(86400) == "1d"
    assert compact_duration(2 * 86400) == "2d"


def test_all_units_combined():
    # 1 day + 1 hour + 1 minute + 1 second = 90061 seconds.
    assert compact_duration(90061) == "1d 1h 1m 1s"
    # 2 days + 3 hours + 4 minutes + 5 seconds = 183845 seconds.
    assert compact_duration(183845) == "2d 3h 4m 5s"


def test_float_input_is_truncated():
    # 90.9 seconds -> 90 seconds -> "1m 30s".
    assert compact_duration(90.9) == "1m 30s"
    # Sub-second values are floored to 0.
    assert compact_duration(0.999) == "0s"


def test_negative_value_raises_value_error():
    with pytest.raises(ValueError):
        compact_duration(-1)
    with pytest.raises(ValueError):
        compact_duration(-3600)


def test_non_numeric_input_raises_type_error():
    with pytest.raises(TypeError):
        compact_duration("60")
    with pytest.raises(TypeError):
        compact_duration(None)
    with pytest.raises(TypeError):
        compact_duration([60])
    # Booleans are technically ints in Python; we explicitly reject them.
    with pytest.raises(TypeError):
        compact_duration(True)
    with pytest.raises(TypeError):
        compact_duration(False)