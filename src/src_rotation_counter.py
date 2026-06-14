def src_rotation_counter(s: str) -> int:
    """
    Count the number of distinct rotations of a string.

    A rotation of string ``s`` is formed by taking some number of characters
    from the beginning of ``s`` and appending them to the end. This function
    returns the number of *unique* rotations of ``s``.

    Args:
        s: The input string.

    Returns:
        The count of distinct rotations of ``s``. Returns ``0`` for an empty
        string, ``1`` for a string consisting of a single repeated character,
        and ``len(s)`` for a string with all distinct characters.

    Examples:
        >>> src_rotation_counter("abc")
        3
        >>> src_rotation_counter("abab")
        2
        >>> src_rotation_counter("aaaa")
        1
        >>> src_rotation_counter("")
        0
    """
    if not s:
        return 0
    n = len(s)
    seen = set()
    for i in range(n):
        rotation = s[i:] + s[:i]
        seen.add(rotation)
    return len(seen)