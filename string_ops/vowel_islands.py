"""Implementation of vowel_islands: extract maximal runs of vowels."""


_VOWELS = set("aeiouAEIOU")


def vowel_islands(s):
    """Return a list of all maximal contiguous vowel substrings in ``s``.

    A *vowel island* is a maximal run of consecutive vowel characters
    (``a``, ``e``, ``i``, ``o``, ``u`` — case-insensitive) within the input
    string. Non-letter characters (digits, whitespace, punctuation) act as
    separators between islands.

    Args:
        s: The string to scan for vowel islands.

    Returns:
        A list of strings, each representing one vowel island, in the order
        they appear in ``s``. Returns an empty list if no vowels are found or
        the input is empty.

    Raises:
        TypeError: If ``s`` is not a string.
    """
    if not isinstance(s, str):
        raise TypeError(f"vowel_islands expected a string, got {type(s).__name__}")

    islands = []
    current = []

    for char in s:
        if char in _VOWELS:
            current.append(char)
        else:
            if current:
                islands.append("".join(current))
                current = []

    # Flush any trailing vowel run.
    if current:
        islands.append("".join(current))

    return islands


__all__ = ["vowel_islands"]