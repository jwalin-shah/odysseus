"""Tests for red_black_tree.py — RedBlackTree implementation."""
import os
import sys

# Add repo root to sys.path so we can import the module directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from red_black_tree import RedBlackTree


def test_empty_tree_inorder_returns_empty_list():
    tree = RedBlackTree()
    assert tree.inorder() == []


def test_empty_tree_search_returns_false():
    tree = RedBlackTree()
    assert tree.search(1) is False
    assert tree.search(0) is False
    assert tree.search(-100) is False


def test_single_element_insert_and_search():
    tree = RedBlackTree()
    tree.insert(42)
    assert tree.search(42) is True
    assert tree.search(41) is False
    assert tree.search(43) is False


def test_single_element_inorder():
    tree = RedBlackTree()
    tree.insert(7)
    assert tree.inorder() == [7]


def test_multiple_inserts_produce_sorted_inorder():
    tree = RedBlackTree()
    for v in [5, 3, 7, 1, 4, 6, 8]:
        tree.insert(v)
    assert tree.inorder() == [1, 3, 4, 5, 6, 7, 8]


def test_search_returns_bool_type():
    tree = RedBlackTree()
    tree.insert(10)
    assert isinstance(tree.search(10), bool)
    assert isinstance(tree.search(99), bool)


def test_search_finds_all_inserted_keys():
    tree = RedBlackTree()
    values = [10, 20, 5, 15, 25, 1, 7, 30]
    for v in values:
        tree.insert(v)
    for v in values:
        assert tree.search(v) is True


def test_search_returns_false_for_missing_keys():
    tree = RedBlackTree()
    for v in [10, 20, 5, 15]:
        tree.insert(v)
    for v in [0, 100, 6, 16, 21]:
        assert tree.search(v) is False


def test_handles_negative_and_zero():
    tree = RedBlackTree()
    values = [-5, 3, -10, 7, 0, -1, 2]
    for v in values:
        tree.insert(v)
    assert tree.inorder() == sorted(values)
    for v in values:
        assert tree.search(v) is True


def test_reverse_sequential_inserts_remain_sorted():
    tree = RedBlackTree()
    for v in range(20, 0, -1):
        tree.insert(v)
    assert tree.inorder() == list(range(1, 21))