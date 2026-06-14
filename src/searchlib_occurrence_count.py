"""Module providing substring occurrence counting functionality."""


def searchlib_occurrence_count(text, pattern, overlap=True):
    """Count occurrences of ``pattern`` in ``text``.

    Args:
        text: The string to search within.
        pattern: The substring to count occurrences of.
        overlap: If True (default), count overlapping occurrences.
                 If False, count only non-overlapping occurrences
                 (i.e. each match consumes ``len(pattern)`` characters).

    Returns:
        The number of times ``pattern`` appears in ``text``.

    Raises:
        TypeError: If ``text`` or ``pattern`` is not a string.
    """
    if not isinstance(text, str) or not isinstance(pattern, str):
        raise TypeError("text and pattern must be strings")
    if pattern == "" or text == "":
        return 0
    if len(pattern) > len(text):
        return 0

    count = 0
    start = 0
    step = 1 if overlap else len(pattern)

    while True:
        index = text.find(pattern, start)
        if index == -1:
            break
        count += 1
        start = index + step

    return count