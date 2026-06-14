"""Count contiguous vowel islands in a string.

A vowel island is a maximal contiguous sequence of vowels in the string.
For example, "education" contains 4 islands: "e", "u", "a", and "io".
"""

VOWELS = set("aeiouAEIOU")


def string_ops_vowel_islands(s):
    """Return the number of contiguous vowel groups (islands) in ``s``.

    Parameters
    ----------
    s : str
        Input string to analyze.

    Returns
    -------
    int
        Number of contiguous vowel groups found. Returns 0 for an empty
        string or a string with no vowels.

    Examples
    --------
    >>> string_ops_vowel_islands("education")
    4
    >>> string_ops_vowel_islands("aeiou")
    1
    >>> string_ops_vowel_islands("bcdfg")
    0
    >>> string_ops_vowel_islands("")
    0
    """
    if not isinstance(s, str) or not s:
        return 0

    count = 0
    in_island = False
    for ch in s:
        if ch in VOWELS:
            if not in_island:
                count += 1
                in_island = True
        else:
            in_island = False
    return count