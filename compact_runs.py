"""compact_runs: group consecutive identical elements into runs."""

from typing import Any, Callable, Iterable, Iterator, Optional, Tuple


def compact_runs(
    iterable: Iterable[Any],
    key: Optional[Callable[[Any], Any]] = None,
) -> Iterator[Tuple[Any, int]]:
    """Group consecutive runs of identical elements in an iterable.

    Iterates the given iterable and yields ``(element, count)`` tuples for
    each maximal run of consecutive elements that compare equal (or that
    produce equal keys when ``key`` is provided).

    Parameters
    ----------
    iterable:
        Any iterable (list, tuple, set, generator, string, ...).
    key:
        Optional callable used to extract a comparison key from each
        element. Elements with equal keys are treated as part of the same
        run. The yielded element is always the original item (not the
        computed key).

    Yields
    ------
    tuple
        ``(element, count)`` pairs, one for each run of consecutive
        identical elements. The first element of each pair is the
        original element that started the run.

    Examples
    --------
    >>> list(compact_runs([1, 1, 2, 2, 2, 3, 1]))
    [(1, 2), (2, 3), (3, 1), (1, 1)]
    >>> list(compact_runs('aabbbc'))
    [('a', 2), ('b', 3), ('c', 1)]
    >>> list(compact_runs(sorted({3, 1, 2})))
    [(1, 1), (2, 1), (3, 1)]
    """
    it = iter(iterable)
    try:
        first = next(it)
    except StopIteration:
        return

    current_element = first
    current_key = key(first) if key is not None else first
    count = 1

    for item in it:
        item_key = key(item) if key is not None else item
        if item_key == current_key:
            count += 1
        else:
            yield (current_element, count)
            current_element = item
            current_key = item_key
            count = 1

    yield (current_element, count)


if __name__ == "__main__":
    # Simple smoke test when run as a script.
    data = [1, 1, 2, 2, 2, 3, 1, 1]
    print(list(compact_runs(data)))