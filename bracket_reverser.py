"""
bracket_reverser
================
A small utility that reverses the characters located *inside* each pair of
matching brackets in a string.

Supported bracket types: round (), square [], and curly {}.

Examples
--------
>>> bracket_reverser("a(bc)d")
'a(cb)d'
>>> bracket_reverser("hello[world]")
'hello[dlrow]'
>>> bracket_reverser("(ab)(cd)")
'(ba)(dc)'

Edge cases
----------
* Empty strings are returned unchanged.
* Strings that contain no brackets are returned unchanged.
* Mismatched brackets are left untouched (no reversal is performed for
  a bracket that has no valid partner).
* Non-string input raises :class:`TypeError`.
"""


def bracket_reverser(s):
    """Reverse the content inside each pair of matching brackets.

    Parameters
    ----------
    s : str
        The input string to process.

    Returns
    -------
    str
        A new string where the content between every matched bracket
        pair has been reversed, leaving the brackets themselves and
        every other character in place.

    Raises
    ------
    TypeError
        If ``s`` is not a string.
    """
    if not isinstance(s, str):
        raise TypeError(
            "bracket_reverser expects a string, got {0}".format(type(s).__name__)
        )

    # Mapping of opening bracket -> its matching closing bracket
    opening_to_closing = {"(": ")", "[": "]", "{": "}"}
    # Mapping of closing bracket -> its matching opening bracket
    closing_to_opening = {v: k for k, v in opening_to_closing.items()}

    # We work on a list so we can perform in-place slice reversals.
    chars = list(s)
    # Stack of indices of opening brackets that are still looking for
    # their matching closing partner.
    open_stack = []

    for i, ch in enumerate(s):
        if ch in opening_to_closing:
            open_stack.append(i)
        elif ch in closing_to_opening:
            # Only reverse if the top of the stack holds a matching opener.
            if open_stack and s[open_stack[-1]] == closing_to_opening[ch]:
                start = open_stack.pop()
                # Reverse the slice strictly *between* the brackets.
                chars[start + 1:i] = chars[start + 1:i][::-1]
            # Mismatched closer: ignore it, leave the character in place.

    return "".join(chars)