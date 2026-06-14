"""Aggregate statistics by category, with values ordered by a sort key."""
from collections import defaultdict
import statistics as _stats


def _safe_stdev(values):
    """Sample standard deviation. Returns 0.0 when fewer than 2 values exist."""
    if len(values) < 2:
        return 0.0
    return float(_stats.stdev(values))


def _safe_mean(values):
    if not values:
        return 0.0
    return float(_stats.mean(values))


def _safe_median(values):
    if not values:
        return 0.0
    return float(_stats.median(values))


def category_order_stat_aggregator(records, order_key='order',
                                   category_key='category', value_key='value'):
    """Aggregate statistics by category, sorting values within each group by ``order_key``.

    Parameters
    ----------
    records : list of dict
        Each record must contain ``category_key``, ``order_key``, and ``value_key``.
    order_key : str
        Key in each record used to sort values within a category. Default 'order'.
    category_key : str
        Key in each record used to group records into categories. Default 'category'.
    value_key : str
        Key in each record that holds the numeric value. Default 'value'.

    Returns
    -------
    dict
        Mapping from category name to a dict of statistics with keys:
        count, sum, mean, median, stdev, min, max.
    """
    if not records:
        return {}

    groups = defaultdict(list)
    for rec in records:
        groups[rec[category_key]].append((rec[order_key], rec[value_key]))

    result = {}
    for cat, items in groups.items():
        items.sort(key=lambda x: x[0])
        values = [v for _, v in items]
        result[cat] = {
            'count': len(values),
            'sum': sum(values),
            'mean': _safe_mean(values),
            'median': _safe_median(values),
            'stdev': _safe_stdev(values),
            'min': min(values),
            'max': max(values),
        }
    return result