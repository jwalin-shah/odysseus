"""Balanced group parser implementation."""


def balanced_group_parser(s, open_delim='(', close_delim=')'):
    """Find all balanced delimiter groups in a string.

    Scans the string and identifies all balanced groups of nested delimiters.
    Each group is returned as a substring that includes both the opening and
    closing delimiters. Inner groups appear before outer groups in the
    resulting list (depth-first order). A backslash escapes the next
    character so it is treated as a literal and not interpreted as a
    delimiter.

    Args:
        s: The input string to parse.
        open_delim: The opening delimiter character. Defaults to ``'('``.
        close_delim: The closing delimiter character. Defaults to ``')'``.

    Returns:
        A list of strings, each containing a balanced group including its
        delimiters. Returns an empty list if no balanced groups are found.

    Examples:
        >>> balanced_group_parser("()")
        ['()']
        >>> balanced_group_parser("(a)(b)")
        ['(a)', '(b)']
        >>> balanced_group_parser("((a))")
        ['(a)', '((a))']
    """
    results = []
    stack = []  # Stack of indices where open delimiters were found

    i = 0
    n = len(s)
    while i < n:
        # Handle escape sequences: backslash escapes the next character.
        if s[i] == '\\' and i + 1 < n:
            i += 2
            continue

        if s[i] == open_delim:
            stack.append(i)
        elif s[i] == close_delim:
            if stack:
                start = stack.pop()
                results.append(s[start:i + 1])

        i += 1

    return results