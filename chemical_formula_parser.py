"""
Chemical formula parser.

Parses a chemical formula string into a dictionary mapping element symbols
to their counts.

Supports:
  * One- and two-letter element symbols (e.g. ``H``, ``He``, ``Na``, ``Cl``,
    ``Fe``).
  * Subscripts -- positive integers following an element or a parenthesised
    group.
  * Parentheses for grouping, including nested parentheses.
  * Whitespace (spaces, tabs, newlines) anywhere in the formula is ignored.

Examples:
    >>> parse_chemical_formula("H2O")
    {'H': 2, 'O': 1}
    >>> parse_chemical_formula("Ca(OH)2")
    {'Ca': 1, 'O': 2, 'H': 2}
    >>> parse_chemical_formula("Al2(SO4)3")
    {'Al': 2, 'S': 3, 'O': 12}
"""


def parse_chemical_formula(formula):
    """Parse a chemical formula and return a dictionary of element counts.

    Args:
        formula: A string representing a chemical formula.  ``None`` and
            empty strings (or whitespace-only strings) return an empty
            dictionary.

    Returns:
        A ``dict`` mapping each element symbol to its total count in the
        formula.

    Raises:
        TypeError: If ``formula`` is not a string or ``None``.
        ValueError: If the formula is malformed -- e.g. contains an
            unexpected character, a leading digit, or has unmatched
            parentheses.
    """
    if formula is None:
        return {}

    if not isinstance(formula, str):
        raise TypeError("formula must be a string or None")

    # Strip all whitespace.
    formula = "".join(formula.split())
    if not formula:
        return {}

    n = len(formula)
    pos = 0

    def read_number():
        """Read a non-negative integer starting at ``pos``.

        Returns 1 if the next character is not a digit.
        """
        nonlocal pos
        start = pos
        while pos < n and formula[pos].isdigit():
            pos += 1
        if pos > start:
            return int(formula[start:pos])
        return 1

    def parse_group(allow_close):
        """Parse a (possibly nested) group of elements.

        When ``allow_close`` is ``True`` a ``)`` character ends the group
        and the current dict is returned.  When ``False`` an unmatched
        ``)`` raises a :class:`ValueError`.
        """
        nonlocal pos
        result = {}
        while pos < n:
            ch = formula[pos]
            if ch == ")":
                if not allow_close:
                    raise ValueError(
                        "Unmatched ')' at position {}".format(pos)
                    )
                return result
            if ch == "(":
                pos += 1  # consume '('
                subgroup = parse_group(allow_close=True)
                if pos >= n or formula[pos] != ")":
                    raise ValueError(
                        "Unmatched '(' in formula at position {}".format(pos)
                    )
                pos += 1  # consume ')'
                count = read_number()
                for elem, cnt in subgroup.items():
                    result[elem] = result.get(elem, 0) + cnt * count
            elif ch.isupper():
                elem = ch
                pos += 1
                while pos < n and formula[pos].islower():
                    elem += formula[pos]
                    pos += 1
                count = read_number()
                result[elem] = result.get(elem, 0) + count
            elif ch.isdigit():
                raise ValueError(
                    "Unexpected digit '{}' at position {}".format(ch, pos)
                )
            else:
                raise ValueError(
                    "Invalid character '{}' at position {}".format(ch, pos)
                )
        return result

    return parse_group(allow_close=False)