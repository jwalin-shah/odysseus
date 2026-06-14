"""Tests for ``tag_cooccurrence_pair_counter``."""

import os
import sys

import pytest

# Ensure the project root is on ``sys.path`` so that the implementation
# module can be imported when this file is executed in isolation.
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir)
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tag_cooccurrence_pair_counter import tag_cooccurrence_pair_counter  # noqa: E402


class TestTagCooccurrencePairCounter:
    """Behavioural tests for the co-occurrence counter."""

    def test_empty_input_returns_empty_dict(self):
        """An empty outer iterable produces no pairs."""
        assert tag_cooccurrence_pair_counter([]) == {}

    def test_none_input_returns_empty_dict(self):
        """``None`` as the outer input must not raise and must return ``{}``."""
        assert tag_cooccurrence_pair_counter(None) == {}

    def test_single_tag_per_collection(self):
        """Collections of size 1 cannot contribute any pair."""
        collections = [["a"], ["b"], ["c"]]
        assert tag_cooccurrence_pair_counter(collections) == {}

    def test_empty_collections_are_skipped(self):
        """Empty inner iterables are silently ignored."""
        collections = [[], ["a", "b"], []]
        assert tag_cooccurrence_pair_counter(collections) == {("a", "b"): 1}

    def test_one_collection_two_tags(self):
        """A single collection with two tags yields exactly one pair."""
        result = tag_cooccurrence_pair_counter([["a", "b"]])
        assert result == {("a", "b"): 1}

    def test_pair_key_is_order_invariant(self):
        """``('a', 'b')`` and ``('b', 'a')`` must map to the same key."""
        r1 = tag_cooccurrence_pair_counter([["a", "b"]])
        r2 = tag_cooccurrence_pair_counter([["b", "a"]])
        assert r1 == r2
        assert ("a", "b") in r1

    def test_duplicate_tags_in_a_collection_collapse(self):
        """Repeated tags inside a single collection do not yield self-pairs."""
        result = tag_cooccurrence_pair_counter([["a", "a", "a", "b"]])
        assert result == {("a", "b"): 1}
        # A self-pair must never appear.
        assert all(a != b for (a, b) in result)

    def test_counts_aggregate_across_collections(self):
        """Pair frequencies accumulate across multiple collections."""
        docs = [
            ["python", "ml", "ai"],
            ["python", "web"],
            ["ml", "ai", "data"],
        ]
        result = tag_cooccurrence_pair_counter(docs)
        assert result[("ai", "ml")] == 2
        assert result[("ai", "python")] == 1
        assert result[("ml", "python")] == 1
        assert result[("python", "web")] == 1
        assert result[("ai", "data")] == 1
        assert result[("data", "ml")] == 1
        # No spurious entries.
        assert len(result) == 6

    def test_full_combinations_for_n_tags(self):
        """A collection of ``n`` unique tags produces exactly ``C(n, 2)`` pairs."""
        result = tag_cooccurrence_pair_counter([["a", "b", "c", "d"]])
        assert len(result) == 6
        expected_keys = {
            ("a", "b"), ("a", "c"), ("a", "d"),
            ("b", "c"), ("b", "d"), ("c", "d"),
        }
        assert set(result.keys()) == expected_keys
        assert all(v == 1 for v in result.values())

    def test_generator_input_is_accepted(self):
        """A generator of collections must work the same as a list."""
        def gen():
            yield ["a", "b"]
            yield ["b", "c"]
            yield ["a", "b", "c"]

        result = tag_cooccurrence_pair_counter(gen())
        assert result[("a", "b")] == 2
        assert result[("b", "c")] == 2
        assert result[("a", "c")] == 1

    def test_return_type_is_dict(self):
        """The function returns a plain ``dict`` instance."""
        result = tag_cooccurrence_pair_counter([["a", "b"]])
        assert isinstance(result, dict)

    def test_none_collection_entries_are_skipped(self):
        """``None`` entries inside the outer iterable are skipped gracefully."""
        result = tag_cooccurrence_pair_counter(
            [["a", "b"], None, ["a", "c"]]
        )
        assert result[("a", "b")] == 1
        assert result[("a", "c")] == 1

    def test_repeated_collection_increments_count(self):
        """The same collection appearing twice doubles the pair counts."""
        result = tag_cooccurrence_pair_counter(
            [["a", "b", "c"], ["a", "b", "c"]]
        )
        assert result[("a", "b")] == 2
        assert result[("a", "c")] == 2
        assert result[("b", "c")] == 2

    def test_unhashable_collection_is_skipped(self):
        """Collections whose elements are unhashable must not crash the call."""
        # Lists are unhashable, so ``set`` raises ``TypeError``; the
        # implementation should swallow it and keep going.
        result = tag_cooccurrence_pair_counter(
            [[[1, 2], [3, 4]], ["a", "b"]]
        )
        assert result == {("a", "b"): 1}

    def test_integer_tags_are_supported(self):
        """Non-string hashable tags should be handled identically."""
        result = tag_cooccurrence_pair_counter([[1, 2, 3], [2, 3, 4]])
        assert result[(1, 2)] == 1
        assert result[(1, 3)] == 1
        assert result[(2, 3)] == 2
        assert result[(2, 4)] == 1
        assert result[(3, 4)] == 1


@pytest.mark.parametrize(
    "collections, expected",
    [
        ([], {}),
        ([["x"]], {}),
        ([["x", "y"]], {("x", "y"): 1}),
        (
            [["a", "b"], ["a", "b"], ["a", "c"]],
            {("a", "b"): 2, ("a", "c"): 1},
        ),
    ],
)
def test_parametrized_examples(collections, expected):
    """A small table of representative examples checked parametrically."""
    assert tag_cooccurrence_pair_counter(collections) == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])