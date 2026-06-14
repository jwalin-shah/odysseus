"""Tests for the SkipList implementation in skip_list.py."""
import os
import sys

# Add repo root to sys.path so we can import skip_list directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from skip_list import SkipList  # noqa: E402


def test_empty_list_search_returns_none():
    """Searching any key in a freshly constructed skip list returns None."""
    sl = SkipList()
    assert sl.search(1) is None
    assert sl.search(0) is None
    assert sl.search(-1) is None
    assert sl.search("anything") is None


def test_empty_list_delete_is_safe():
    """Deleting from an empty skip list must not raise; it returns a falsy value."""
    sl = SkipList()
    result = sl.delete(1)
    assert result in (False, None)


def test_single_element_insert_and_search():
    """Insert a single (k, v) pair; search must return that value."""
    sl = SkipList()
    sl.insert(1, "a")
    assert sl.search(1) == "a"


def test_single_element_delete():
    """After inserting and then deleting the only key, search returns None."""
    sl = SkipList()
    sl.insert(1, "a")
    deleted = sl.delete(1)
    assert deleted in (True, None)
    assert sl.search(1) is None


def test_multiple_inserts_all_searchable():
    """All inserted keys must be retrievable with their associated values."""
    sl = SkipList()
    pairs = [(1, "a"), (2, "b"), (3, "c"), (4, "d"), (5, "e")]
    for k, v in pairs:
        sl.insert(k, v)
    for k, v in pairs:
        assert sl.search(k) == v


def test_delete_existing_key_keeps_others():
    """Deleting an existing key removes only that key; siblings remain intact."""
    sl = SkipList()
    sl.insert(1, "a")
    sl.insert(2, "b")
    sl.insert(3, "c")
    sl.delete(2)
    assert sl.search(2) is None
    assert sl.search(1) == "a"
    assert sl.search(3) == "c"


def test_delete_non_existent_key_is_safe():
    """Deleting a missing key is a no-op; existing entries are unaffected."""
    sl = SkipList()
    sl.insert(1, "a")
    sl.insert(2, "b")
    result = sl.delete(99)
    assert result in (False, None)
    assert sl.search(1) == "a"
    assert sl.search(2) == "b"
    assert sl.search(99) is None


def test_insert_overwrites_existing_key():
    """Inserting the same key again should update its associated value."""
    sl = SkipList()
    sl.insert(1, "original")
    sl.insert(1, "updated")
    assert sl.search(1) == "updated"


def test_search_missing_key_returns_none():
    """Searching a key that was never inserted returns None."""
    sl = SkipList()
    sl.insert(1, "a")
    sl.insert(2, "b")
    assert sl.search(3) is None
    assert sl.search(100) is None


def test_many_inserts_and_partial_deletes():
    """Stress test: insert many keys, delete half, verify the survivors and the rest."""
    sl = SkipList()
    n = 100
    for i in range(n):
        sl.insert(i, f"val_{i}")
    # All present.
    for i in range(n):
        assert sl.search(i) == f"val_{i}"
    # Remove even keys.
    for i in range(0, n, 2):
        sl.delete(i)
    # Even keys are gone; odd keys remain.
    for i in range(n):
        if i % 2 == 0:
            assert sl.search(i) is None
        else:
            assert sl.search(i) == f"val_{i}"