"""
Alternating word caser.

Given an input string, splits it into whitespace-delimited words and
converts them to an alternating case pattern: the first word (index 0)
becomes UPPERCASE, the second becomes lowercase, the third UPPERCASE,
and so on.

Edge cases handled:
    * ``None`` or non-string input -> ``TypeError``.
    * Empty string or whitespace-only string -> empty string returned.
    * Multiple spaces / leading / trailing whitespace are normalised
      by :py:meth:`str.split` / :py:meth:`str.join`.
    * Punctuation attached to a word stays attached to that word; the
      case of the alphabetic characters in the word is flipped
      according to the alternating pattern.
"""

from __future__ import annotations

from typing import List

__all__ = ["alternating_word_caser"]


def alternating_word_caser(text: str) -> str:
    """Return ``text`` with alternating upper/lowercase words.

    Parameters
    ----------
    text:
        The input string to transform.

    Returns
    -------
    str
        A new string where word at even index (0, 2, 4, ...) is
        upper-cased and words at odd index (1, 3, 5, ...) are
        lower-cased.  Returns an empty string for empty or
        whitespace-only input.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"alternating_word_caser expected str, got {type(text).__name__}"
        )

    if not text or not text.strip():
        return ""

    words: List[str] = text.split()
    transformed: List[str] = []
    for index, word in enumerate(words):
        if index % 2 == 0:
            transformed.append(word.upper())
        else:
            transformed.append(word.lower())

    return " ".join(transformed)