"""Tests for the AVL tree implementation in avl_tree.py.

The implementation is expected to provide an `AVLTree` class with:
    - insert(key)
    - delete(key)
    - search(key) -> bool
    - inorder()  -> list

All insert/delete operations must keep the tree height-balanced (AVL
property), and `inorder` must yield keys in non-decreasing order.
"""
import os
import sys

# Make the repo root importable so we can `import avl_tree` directly.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

import pytest

from avl_tree import AVLTree


# ---------------------------------------------------------------------------
# Edge cases: empty and single-element trees
# ---------------------------------------------------------------------------

def test_empty_tree_inorder_returns_empty_list():
    tree = AVLTree()
    assert tree.inorder() == []


def test_empty_tree_search_returns_false():
    tree = AVLTree()
    assert tree.search(1) is False
    assert tree.search("anything") is False
    assert tree.search(None) is False


def test_single_element_insert_and_inorder():
    tree = AVLTree()
    tree.insert(42)
    assert tree.inorder() == [42]


def test_single_element_search():
    tree = AVLTree()
    tree.insert(42)
    assert tree.search(42) is True
    assert tree.search(41) is False
    assert tree.search(43) is False


# ---------------------------------------------------------------------------
# Correctness of `inorder` and AVL rebalancing after inserts
# ---------------------------------------------------------------------------

def test_inorder_returns_sorted_after_multiple_inserts():
    tree = AVLTree()
    for key in [5, 3, 7, 1, 4, 6, 8]:
        tree.insert(key)
    assert tree.inorder() == [1, 3, 4, 5, 6, 7, 8]


def test_inorder_sorted_after_strictly_decreasing_inserts():
    # Inserting in decreasing order forces right rotations (LL case).
    tree = AVLTree()
    for key in range(15, 0, -1):
        tree.insert(key)
    assert tree.inorder() == list(range(1, 16))


def test_inorder_sorted_after_strictly_increasing_inserts():
    # Inserting in increasing order forces left rotations (RR case).
    tree = AVLTree()
    for key in range(1, 16):
        tree.insert(key)
    assert tree.inorder() == list(range(1, 16))


# ---------------------------------------------------------------------------
# Delete behaviour
# ---------------------------------------------------------------------------

def test_delete_existing_key_removes_it():
    tree = AVLTree()
    for key in [10, 5, 15, 3, 7, 12, 20]:
        tree.insert(key)
    tree.delete(3)
    assert tree.search(3) is False
    assert tree.inorder() == [5, 7, 10, 12, 15, 20]


def test_delete_nonexistent_key_leaves_tree_unchanged():
    tree = AVLTree()
    for key in [10, 5, 15, 3, 7]:
        tree.insert(key)
    tree.delete(999)
    assert tree.inorder() == [3, 5, 7, 10, 15]


def test_delete_all_elements_one_by_one():
    tree = AVLTree()
    for key in [4, 2, 6, 1, 3, 5, 7]:
        tree.insert(key)
    for key in [1, 2, 3, 4, 5, 6, 7]:
        tree.delete(key)
    assert tree.inorder() == []
    for key in [1, 2, 3, 4, 5, 6, 7]:
        assert tree.search(key) is False