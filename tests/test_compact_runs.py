"""Tests for compact_runs."""

import types

import pytest

from compact_runs import compact_runs


def test_empty_iterable_returns_nothing():
    assert list(compact_runs([])) == []


def test_single_element():
    assert list(compact_runs([42])) == [(42, 1)]


def test_all_identical_elements():
    assert list(compact_runs([1, 1, 1, 1])) == [(1, 4)]


def test_no_duplicates():
    assert list(compact_runs([1, 2, 3, 4])) == [(1, 1), (2, 1), (3, 1), (4, 1)]


def test_mixed_runs():
    assert list(compact_runs([1, 1, 2, 2, 2, 3, 1, 1])) == [
        (1, 2),
        (2, 3),
        (3, 1),
        (1, 2),
    ]


def test_string_input():
    assert list(compact_runs("aaabbc")) == [("a", 3), ("b", 2), ("c", 1)]


def test_generator_input():
    def gen():
        for x in [1, 1, 2, 3, 3]:
            yield x

    assert list(compact_runs(gen())) == [(1, 2), (2, 1), (3, 2)]


def test_returns_iterator():
    result = compact_runs([1, 1, 2])
    assert hasattr(result, "__next__")
    assert isinstance(result, types.GeneratorType)


def test_works_with_set_input_sorted_by_iteration():
    """A set iterated (after sorting for determinism) should yield each
    distinct element exactly once, so the total count equals the set size."""
    s = {1, 2, 3}
    # Sort the set so iteration order is deterministic.
    runs = list(compact_runs(sorted(s)))
    total = sum(count for _, count in runs)
    assert total == 3
    assert len(runs) == 3


def test_works_with_set_input_larger():
    s = {1, 2, 3, 4, 5}
    runs = list(compact_runs(sorted(s)))
    total = sum(count for _, count in runs)
    assert total == 5


def test_set_with_duplicate_origins():
    # Data has duplicates, but converting to a set removes them.
    # compact_runs over the sorted unique values gives one run per element.
    data = [1, 2, 2, 3, 3, 3, 1]
    runs = list(compact_runs(sorted(set(data))))
    assert sum(count for _, count in runs) == 3
    assert sorted(elem for elem, _ in runs) == [1, 2, 3]


def test_with_key_function():
    data = [("a", 1), ("a", 2), ("b", 3), ("b", 4), ("c", 5)]
    result = list(compact_runs(data, key=lambda x: x[0]))
    assert result == [(("a", 1), 2), (("b", 3), 2), (("c", 5), 1)]


def test_key_function_with_mixed_order():
    data = [("b", 1), ("a", 1), ("a", 2), ("b", 2)]
    # Without sorting, the input order determines the runs.
    result = list(compact_runs(data, key=lambda x: x[0]))
    assert result == [(("b", 1), 1), (("a", 1), 2), (("b", 2), 1)]


def test_two_distinct_values_alternating():
    # Alternating values: each is its own run of length 1.
    assert list(compact_runs([1, 2, 1, 2, 1])) == [
        (1, 1),
        (2, 1),
        (1, 1),
        (2, 1),
        (1, 1),
    ]


def test_tuple_input():
    assert list(compact_runs((1, 1, 2, 3, 3))) == [(1, 2), (2, 1), (3, 2)]


def test_preserves_original_element_not_key():
    # The yielded element should be the original, not the key.
    data = [{"id": 1, "v": "a"}, {"id": 1, "v": "b"}, {"id": 2, "v": "c"}]
    result = list(compact_runs(data, key=lambda d: d["id"]))
    assert len(result) == 2
    assert result[0][0] is data[0]
    assert result[1][0] is data[2]
    assert result[0][1] == 2
    assert result[1][1] == 1


def test_can_iterate_partially():
    it = compact_runs([1, 1, 1, 2, 2, 3, 3, 3, 3])
    first = next(it)
    assert first == (1, 3)
    second = next(it)
    assert second == (2, 2)