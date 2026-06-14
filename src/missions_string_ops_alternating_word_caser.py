"""Alternating word caser mission.

Provides a function that converts a string by alternating the case of
its whitespace-separated words: words at even indices (0, 2, 4, ...)
are converted to UPPERCASE and words at odd indices (1, 3, 5, ...) are
converted to lowercase.
"""


def alternating_word_caser(text):
    """Return a new string with alternating word case.

    The first word is uppercased, the second is lowercased, the third
    is uppercased, and so on. Words are split on any whitespace and
    rejoined with a single space.

    Parameters
    ----------
    text : str
        The input string to transform.

    Returns
    -------
    str
        The transformed string with alternating word case. Returns the
        input unchanged if it is empty.

    Raises
    ------
    TypeError
        If ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"expected str, got {type(text).__name__}"
        )
    if not text:
        return text

    words = text.split()
    transformed = []
    for index, word in enumerate(words):
        if index % 2 == 0:
            transformed.append(word.upper())
        else:
            transformed.append(word.lower())
    return " ".join(transformed)


if __name__ == "__main__":
    # Quick demo / smoke test when run as a script.
    samples = [
        "hello world",
        "The quick brown fox jumps over the lazy dog",
        "PYTHON is fun",
        "",
        "solo",
    ]
    for sample in samples:
        print(f"{sample!r} -> {alternating_word_caser(sample)!r}")