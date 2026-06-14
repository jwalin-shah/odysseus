def decode_nested_bracket(s):
    """
    Decode a string with nested bracket notation.

    In this encoding, an integer followed by a pair of square brackets
    indicates that the substring inside the brackets should be repeated
    that many times. Brackets may be nested arbitrarily.

    Parameters
    ----------
    s : str
        The encoded string. May contain letters, digits, and the
        characters '[' and ']'. An empty string is allowed.

    Returns
    -------
    str
        The fully decoded string.

    Examples
    --------
    >>> decode_nested_bracket("3[a]")
    'aaa'
    >>> decode_nested_bracket("3[a]2[bc]")
    'aaabcbc'
    >>> decode_nested_bracket("3[a2[c]]")
    'accaccacc'
    >>> decode_nested_bracket("2[abc]3[cd]ef")
    'abcabccdcdcdef'
    >>> decode_nested_bracket("2[2[2[a]]]")
    'aaaaaaaa'
    """
    # Defensive: non-string input is returned unchanged so callers that
    # accidentally pass None or other types do not crash unexpectedly.
    if not isinstance(s, str):
        return s

    # Empty input short-circuits.
    if not s:
        return ""

    # `stack` keeps a snapshot of (current_str_prefix, repeat_count) for
    # every '[' we encounter.  When we hit the matching ']' we pop the
    # snapshot and repeat the freshly accumulated substring.
    stack = []
    current_num = 0
    current_str = []

    for ch in s:
        if ch.isdigit():
            # Support multi-digit repeat counts.
            current_num = current_num * 10 + int(ch)
        elif ch == "[":
            # Push the in-progress state and start fresh for the new
            # bracketed expression.
            stack.append((current_str, current_num))
            current_str = []
            current_num = 0
        elif ch == "]":
            if not stack:
                # Unmatched closing bracket: gracefully return the input
                # unchanged rather than raising.
                return s
            prev_str, repeat = stack.pop()
            current_str = prev_str + current_str * repeat
        else:
            current_str.append(ch)

    # Any leftover state on the stack indicates unmatched '[' brackets;
    # in that case the input was malformed, so we fall back to the
    # original string.
    if stack:
        return s

    return "".join(current_str)