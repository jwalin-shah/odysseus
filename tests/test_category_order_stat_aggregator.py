"""Tests for category_order_stat_aggregator."""
import statistics

import pytest

from category_order_stat_aggregator import category_order_stat_aggregator


def test_empty_input_returns_empty_dict():
    assert category_order_stat_aggregator([]) == {}


def test_single_record():
    records = [{'category': 'A', 'order': 1, 'value': 42}]
    result = category_order_stat_aggregator(records)
    assert result == {
        'A': {
            'count': 1,
            'sum': 42,
            'mean': 42.0,
            'median': 42.0,
            'stdev': 0.0,
            'min': 42,
            'max': 42,
        }
    }


def test_multiple_categories():
    records = [
        {'category': 'A', 'order': 1, 'value': 10},
        {'category': 'A', 'order': 2, 'value': 20},
        {'category': 'B', 'order': 1, 'value': 5},
        {'category': 'B', 'order': 2, 'value': 15},
    ]
    result = category_order_stat_aggregator(records)
    assert result['A']['count'] == 2
    assert result['A']['sum'] == 30
    assert result['A']['mean'] == 15.0
    assert result['A']['min'] == 10
    assert result['A']['max'] == 20
    assert result['B']['count'] == 2
    assert result['B']['sum'] == 20
    assert result['B']['mean'] == 10.0
    assert result['B']['min'] == 5
    assert result['B']['max'] == 15


def test_stdev_stat_known_dataset():
    # Classic sample-stdev example: [2, 4, 4, 4, 5, 5, 7, 9]
    # mean = 5.0, sample stdev = 2.138089935299395, median = 4.5
    data = [2, 4, 4, 4, 5, 5, 7, 9]
    records = [
        {'category': 'X', 'order': i, 'value': v}
        for i, v in enumerate(data)
    ]
    result = category_order_stat_aggregator(records)
    expected_stdev = statistics.stdev(data)
    assert result['X']['count'] == 8
    assert result['X']['sum'] == 40
    assert result['X']['mean'] == 5.0
    assert result['X']['stdev'] == pytest.approx(expected_stdev)
    assert result['X']['min'] == 2
    assert result['X']['max'] == 9
    assert result['X']['median'] == 4.5


def test_stdev_single_value_is_zero():
    records = [{'category': 'A', 'order': 1, 'value': 99}]
    result = category_order_stat_aggregator(records)
    assert result['A']['stdev'] == 0.0


def test_order_used_for_sorting():
    # Records provided out of order; values must be sorted by 'order'
    records = [
        {'category': 'A', 'order': 3, 'value': 30},
        {'category': 'A', 'order': 1, 'value': 10},
        {'category': 'A', 'order': 2, 'value': 20},
    ]
    result = category_order_stat_aggregator(records)
    assert result['A']['min'] == 10
    assert result['A']['max'] == 30
    assert result['A']['mean'] == 20.0
    assert result['A']['sum'] == 60


def test_custom_keys():
    records = [
        {'cat': 'A', 'pos': 1, 'val': 100},
        {'cat': 'A', 'pos': 2, 'val': 200},
        {'cat': 'B', 'pos': 1, 'val': 50},
    ]
    result = category_order_stat_aggregator(
        records,
        order_key='pos',
        category_key='cat',
        value_key='val',
    )
    assert result['A']['sum'] == 300
    assert result['A']['count'] == 2
    assert result['A']['mean'] == 150.0
    assert result['B']['sum'] == 50
    assert result['B']['count'] == 1
    assert result['B']['mean'] == 50.0


def test_negative_values():
    records = [
        {'category': 'A', 'order': 1, 'value': -10},
        {'category': 'A', 'order': 2, 'value': 10},
    ]
    result = category_order_stat_aggregator(records)
    assert result['A']['min'] == -10
    assert result['A']['max'] == 10
    assert result['A']['mean'] == 0.0
    assert result['A']['sum'] == 0


def test_stdev_does_not_recurse():
    # Regression: previously _stdev called itself instead of statistics.stdev.
    records = [
        {'category': 'A', 'order': 1, 'value': 1.0},
        {'category': 'A', 'order': 2, 'value': 2.0},
        {'category': 'A', 'order': 3, 'value': 3.0},
    ]
    # Should not raise RecursionError
    result = category_order_stat_aggregator(records)
    assert result['A']['stdev'] == pytest.approx(statistics.stdev([1.0, 2.0, 3.0]))


def test_float_values():
    records = [
        {'category': 'A', 'order': 1, 'value': 1.5},
        {'category': 'A', 'order': 2, 'value': 2.5},
        {'category': 'A', 'order': 3, 'value': 3.5},
    ]
    result = category_order_stat_aggregator(records)
    assert result['A']['mean'] == pytest.approx(2.5)
    assert result['A']['sum'] == pytest.approx(7.5)
    assert result['A']['min'] == 1.5
    assert result['A']['max'] == 3.5


def test_three_categories_independent():
    records = [
        {'category': 'X', 'order': 1, 'value': 1},
        {'category': 'Y', 'order': 1, 'value': 10},
        {'category': 'Z', 'order': 1, 'value': 100},
    ]
    result = category_order_stat_aggregator(records)
    assert set(result.keys()) == {'X', 'Y', 'Z'}
    assert result['X']['sum'] == 1
    assert result['Y']['sum'] == 10
    assert result['Z']['sum'] == 100


def test_median_even_count():
    records = [
        {'category': 'A', 'order': 1, 'value': 1},
        {'category': 'A', 'order': 2, 'value': 3},
        {'category': 'A', 'order': 3, 'value': 5},
        {'category': 'A', 'order': 4, 'value': 7},
    ]
    result = category_order_stat_aggregator(records)
    assert result['A']['median'] == 4.0
    assert result['A']['mean'] == 4.0


def test_median_odd_count():
    records = [
        {'category': 'A', 'order': 1, 'value': 1},
        {'category': 'A', 'order': 2, 'value': 5},
        {'category': 'A', 'order': 3, 'value': 9},
    ]
    result = category_order_stat_aggregator(records)
    assert result['A']['median'] == 5.0


def test_duplicate_orders_stable_sort():
    # Python's sort is stable, so relative order is preserved for duplicate keys
    records = [
        {'category': 'A', 'order': 1, 'value': 5},
        {'category': 'A', 'order': 1, 'value': 1},
        {'category': 'A', 'order': 1, 'value': 3},
    ]
    result = category_order_stat_aggregator(records)
    assert result['A']['count'] == 3
    assert result['A']['sum'] == 9
    assert result['A']['mean'] == 3.0
    assert result['A']['min'] == 1
    assert result['A']['max'] == 5
    assert result['A']['median'] == 3.0