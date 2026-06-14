import sys
import os

# Allow `import missions_stack_sorted_frequency_rainbow_popper` regardless of
# how pytest is invoked, by ensuring the `src/` directory is on sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from missions_stack_sorted_frequency_rainbow_popper import (
    missions_stack_sorted_frequency_rainbow_popper,
)


def test_empty_stack():
    """An empty stack should return an empty list."""
    assert missions_stack_sorted_frequency_rainbow_popper([]) == []


def test_single_item():
    """A stack with a single item should return that item."""
    assert missions_stack_sorted_frequency_rainbow_popper(['alpha']) == ['alpha']


def test_all_unique_items_preserves_order():
    """All items with frequency 1 should remain in their original order."""
    stack = ['alpha', 'beta', 'gamma', 'delta']
    assert missions_stack_sorted_frequency_rainbow_popper(stack) == [
        'alpha', 'beta', 'gamma', 'delta'
    ]


def test_three_way_tie_resolved_by_stack_position():
    """
    When multiple items share the same frequency, ties must be broken by
    the items' original positions in the stack (stable ordering).
    """
    stack = ['alpha', 'beta', 'gamma', 'delta']
    result = missions_stack_sorted_frequency_rainbow_popper(stack)
    assert result == ['alpha', 'beta', 'gamma', 'delta']


def test_mixed_frequencies_with_ties():
    """
    Higher-frequency items come first; items with the same frequency are
    ordered by their first appearance in the stack.
    Input: ['alpha', 'beta', 'gamma', 'beta', 'gamma', 'delta']
    Frequencies: alpha=1, beta=2, gamma=2, delta=1
    First positions: alpha=0, beta=1, gamma=2, delta=5
    Expected: beta (freq 2, pos 1), gamma (freq 2, pos 2),
              alpha (freq 1, pos 0), delta (freq 1, pos 5)
    """
    stack = ['alpha', 'beta', 'gamma', 'beta', 'gamma', 'delta']
    assert missions_stack_sorted_frequency_rainbow_popper(stack) == [
        'beta', 'gamma', 'alpha', 'delta'
    ]


def test_single_dominant_item():
    """
    The most frequent item should come first; the remaining items (all
    frequency 1) should follow in their original stack order.
    """
    stack = ['alpha', 'beta', 'gamma', 'gamma', 'delta', 'gamma']
    assert missions_stack_sorted_frequency_rainbow_popper(stack) == [
        'gamma', 'alpha', 'beta', 'delta'
    ]


def test_all_same_item():
    """A stack with only one unique item should return a single-element list."""
    assert missions_stack_sorted_frequency_rainbow_popper(
        ['alpha', 'alpha', 'alpha']
    ) == ['alpha']


def test_ties_between_high_and_low_frequency_groups():
    """
    Items tied at a higher frequency should come before items tied at a
    lower frequency; within each group, original stack order is preserved.
    """
    stack = ['a', 'b', 'c', 'a', 'b', 'd']
    # freq: a=2, b=2, c=1, d=1
    # positions: a=0, b=1, c=2, d=5
    assert missions_stack_sorted_frequency_rainbow_popper(stack) == [
        'a', 'b', 'c', 'd'
    ]