"""
Tests for ``interleaved_zip_with_fill_sentinel``.

These tests verify the behaviour of the function defined in
``missions.list_transforms.interleaved_zip_with_fill_sentinel``.
"""
import pytest

from missions.list_transforms.interleaved_zip_with_fill_sentinel import (
    interleaved_zip_with_fill_sentinel,
)


class TestInterleavedZipWithFillSentinel:
    """Tests for the ``interleaved_zip_with_fill_sentinel`` function."""

    def test_equal_length_iterables(self):
        """Equal-length iterables are interleaved in round-robin order."""
        result = interleaved_zip_with_fill_sentinel([1, 2, 3], ['a', 'b', 'c'])
        assert result == [1, 'a', 2, 'b', 3, 'c']

    def test_single_iterable(self):
        """A single iterable is returned as a list of its elements."""
        result = interleaved_zip_with_fill_sentinel([1, 2, 3])
        assert result == [1, 2, 3]

    def test_first_iterable_shorter(self):
        """When the first iterable is shorter, fillvalue pads its slots."""
        result = interleaved_zip_with_fill_sentinel(
            [1, 2], ['a', 'b', 'c'], fillvalue='_'
        )
        assert result == [1, 'a', 2, 'b', '_', 'c']

    def test_second_iterable_shorter(self):
        """When the second iterable is shorter, fillvalue pads its slots."""
        result = interleaved_zip_with_fill_sentinel(
            [1, 2, 3], ['a', 'b'], fillvalue='_'
        )
        assert result == [1, 'a', 2, 'b', 3, '_']

    def test_three_iterables_varied_lengths(self):
        """Three iterables of different lengths all get padded correctly."""
        result = interleaved_zip_with_fill_sentinel(
            [1, 2, 3], ['a', 'b'], ['x', 'y', 'z', 'w'], fillvalue='F'
        )
        assert result == [
            1, 'a', 'x',
            2, 'b', 'y',
            3, 'F', 'z',
            'F', 'F', 'w',
        ]

    def test_default_fillvalue_is_none(self):
        """The default fillvalue is ``None``."""
        result = interleaved_zip_with_fill_sentinel([1, 2, 3], ['a'])
        assert result == [1, 'a', 2, None, 3, None]

    def test_empty_first_iterable(self):
        """An empty first iterable is padded entirely with fillvalue."""
        result = interleaved_zip_with_fill_sentinel([], [1, 2], fillvalue=0)
        assert result == [0, 1, 0, 2]

    def test_empty_second_iterable(self):
        """An empty second iterable is padded entirely with fillvalue."""
        result = interleaved_zip_with_fill_sentinel([1, 2], [], fillvalue=0)
        assert result == [1, 0, 2, 0]

    def test_all_empty_iterables(self):
        """All-empty iterables produce an empty result."""
        result = interleaved_zip_with_fill_sentinel([], [], fillvalue=0)
        assert result == []

    def test_no_iterables(self):
        """Calling with no iterables returns an empty list."""
        result = interleaved_zip_with_fill_sentinel()
        assert result == []

    def test_with_generators(self):
        """Generators are consumed correctly."""
        def gen1():
            yield 1
            yield 2
            yield 3

        def gen2():
            yield 'a'
            yield 'b'

        result = interleaved_zip_with_fill_sentinel(gen1(), gen2(), fillvalue='_')
        assert result == [1, 'a', 2, 'b', 3, '_']

    def test_with_strings(self):
        """Strings are iterated character by character."""
        result = interleaved_zip_with_fill_sentinel("abc", "xy", fillvalue='_')
        assert result == ['a', 'x', 'b', 'y', 'c', '_']

    def test_with_tuples(self):
        """Tuples are treated as iterables of their elements."""
        result = interleaved_zip_with_fill_sentinel((1, 2), (3, 4, 5), fillvalue=0)
        assert result == [1, 3, 2, 4, 0, 5]

    def test_fillvalue_can_be_any_type(self):
        """``fillvalue`` may be of any type, including mutable objects."""
        sentinel = {'placeholder': True}
        result = interleaved_zip_with_fill_sentinel(
            [1, 2], ['a'], fillvalue=sentinel
        )
        assert result == [1, 'a', 2, sentinel]

    def test_iterables_containing_none(self):
        """``None`` values inside the iterables are preserved, not treated as fills."""
        result = interleaved_zip_with_fill_sentinel(
            [None, 2, None], [1, None, 3], fillvalue='X'
        )
        assert result == [None, 1, 2, None, None, 3]

    def test_single_empty_iterable(self):
        """A single empty iterable produces an empty list."""
        result = interleaved_zip_with_fill_sentinel([], fillvalue=0)
        assert result == []

    def test_preserves_element_identity(self):
        """Real elements are passed through unchanged (no copying)."""
        sentinel = object()
        result = interleaved_zip_with_fill_sentinel(
            [sentinel, 'b'], [1], fillvalue=sentinel
        )
        assert result[0] is sentinel
        assert result[3] is sentinel

    def test_returns_a_list(self):
        """The return type is always a ``list``."""
        result = interleaved_zip_with_fill_sentinel([1], [2])
        assert isinstance(result, list)

    def test_keyword_only_fillvalue(self):
        """``fillvalue`` must be passed as a keyword argument."""
        result = interleaved_zip_with_fill_sentinel(
            [1, 2, 3], ['a'], fillvalue='X'
        )
        assert result == [1, 'a', 2, 'X', 3, 'X']

    def test_interleaving_order_preserved(self):
        """The order in which iterables are supplied determines their slot order."""
        a = [10, 20]
        b = [100, 200, 300]
        c = [1000]
        result = interleaved_zip_with_fill_sentinel(a, b, c, fillvalue=-1)
        # Position 0: 10, 100, 1000
        # Position 1: 20, 200, -1
        # Position 2: -1, 300, -1
        assert result == [10, 100, 1000, 20, 200, -1, -1, 300, -1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])