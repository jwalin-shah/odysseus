from typing import Sequence, Iterator, List, TypeVar

T = TypeVar('T')


def chunked(seq: Sequence[T], n: int) -> Iterator[List[T]]:
    """Yield successive lists of size n from seq; the last list may be shorter."""
    for i in range(0, len(seq), n):
        yield list(seq[i:i + n])
