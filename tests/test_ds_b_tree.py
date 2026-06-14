import sys
import os
import pytest

# Add repo root to sys.path so we can import the module directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from b_tree import BTree


def test_empty_tree_search_returns_false():
    tree = BTree(order=3)
    assert tree.search(1) is False
    assert tree.search(0) is False
    assert tree.search(-100) is False


def test_empty_tree_traverse_returns_empty_list():
    tree = BTree(order=3)
    result = tree.traverse()
    assert result == []
    assert isinstance(result, list)


def test_single_insert_and_search():
    tree = BTree(order=3)
    tree.insert(42)
    assert tree.search(42) is True
    assert tree.search(41) is False
    assert tree.search(43) is False


def test_single_insert_traverse():
    tree = BTree(order=3)
    tree.insert(42)
    assert tree.traverse() == [42]


def test_multiple_inserts_sorted_traverse():
    tree = BTree(order=3)
    for key in [10, 5, 20, 15, 25, 1, 30]:
        tree.insert(key)
    assert tree.traverse() == [1, 5, 10, 15, 20, 25, 30]


def test_search_finds_all_inserted():
    tree = BTree(order=3)
    keys = [50, 30, 70, 20, 40, 60, 80]
    for key in keys:
        tree.insert(key)
    for key in keys:
        assert tree.search(key) is True, f"Key {key} not found"


def test_search_missing_key_returns_false():
    tree = BTree(order=3)
    for key in [10, 20, 30, 40, 50]:
        tree.insert(key)
    for missing in [5, 15, 25, 35, 45, 55, 100, 0]:
        assert tree.search(missing) is False, f"Key {missing} should not be found"


def test_node_split_with_small_order():
    # With order=2 (minimum degree t=1 or t=2 depending on convention),
    # inserting several keys forces node splits and exercises the B-tree logic.
    tree = BTree(order=2)
    for key in [1, 2, 3, 4, 5, 6, 7]:
        tree.insert(key)
    assert tree.traverse() == [1, 2, 3, 4, 5, 6, 7]
    for key in [1, 2, 3, 4, 5, 6, 7]:
        assert tree.search(key) is True
    assert tree.search(8) is False
    assert tree.search(0) is False


def test_larger_order():
    tree = BTree(order=5)
    values = list(range(1, 21))
    for v in values:
        tree.insert(v)
    assert tree.traverse() == values
    for v in values:
        assert tree.search(v) is True
    assert tree.search(21) is False
    assert tree.search(0) is False


def test_return_types_are_correct():
    tree = BTree(order=3)
    # search must return a bool
    assert isinstance(tree.search(1), bool)
    assert tree.search(1) is False
    # traverse must return a list
    assert isinstance(tree.traverse(), list)
    assert tree.traverse() == []
    # after insert, types remain consistent
    tree.insert(1)
    assert isinstance(tree.search(1), bool)
    assert tree.search(1) is True
    assert isinstance(tree.traverse(), list)
    assert tree.traverse() == [1]