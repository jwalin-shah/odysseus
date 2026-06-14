def double_letter_fall_collapse(s):
    """Remove consecutive duplicate characters iteratively.

    The function repeatedly scans the string and removes every pair of
    adjacent identical characters, continuing until no more pairs can be
    removed. The check is case-sensitive, so 'a' and 'A' are treated as
    different characters and never collapse with each other.

    Examples
    --------
    >>> double_letter_fall_collapse("abccba")
    ''
    >>> double_letter_fall_collapse("aabbcc")
    ''
    >>> double_letter_fall_collapse("abc")
    'abc'
    >>> double_letter_fall_collapse("abbc")
    'ac'
    """
    if s is None:
        return s
    if len(s) < 2:
        return s

    changed = True
    while changed:
        changed = False
        i = 0
        result = []
        while i < len(s):
            if i + 1 < len(s) and s[i] == s[i + 1]:
                changed = True
                i += 2
            else:
                result.append(s[i])
                i += 1
        s = "".join(result)
    return s