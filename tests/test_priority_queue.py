import pytest

from priority_queue import PriorityQueue


def test_is_empty_true_on_fresh_queue():
    pq = PriorityQueue()
    assert pq.is_empty() is True


def test_is_empty_false_after_enqueue():
    pq = PriorityQueue()
    pq.push("item", priority=1)
    assert pq.is_empty() is False


def test_is_empty_true_again_after_drain():
    pq = PriorityQueue()
    pq.push("a", priority=1)
    pq.push("b", priority=2)
    assert pq.is_empty() is False

    pq.pop()
    assert pq.is_empty() is False

    pq.pop()
    assert pq.is_empty() is True
