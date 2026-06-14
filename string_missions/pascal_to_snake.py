"""Convert PascalCase strings to snake_case.

This module exposes :func:`pascal_to_snake`, a small utility that
converts identifiers written in PascalCase (also known as
UpperCamelCase) into the more idiomatic snake_case form used by
Python and many other languages.
"""

import re

# A pre-compiled pair of regular expressions that insert underscores
# at the appropriate word boundaries.  Splitting them into two passes
# makes it easy to keep acronyms like ``XML`` together (so that
# ``MyXMLParser`` becomes ``my_xml_parser`` rather than
# ``my_x_m_l_parser``).
_BOUNDARY_BEFORE_UPPERCASE_WITH_TAIL = re.compile(r"(.)([A-Z][a-z]+)")
_BOUNDARY_AFTER_LOWER_OR_DIGIT = re.compile(r"([a-z0-9])([A-Z])")


def pascal_to_snake(name):
    """Return the snake_case form of a PascalCase string.

    The conversion is performed in two steps so that runs of
    consecutive uppercase letters (acronyms) are preserved as a
    single word:

    1. Insert an underscore between any character and an uppercase
       letter that is followed by at least one lowercase letter.
       This splits boundaries such as ``lCase`` into ``l_Case``.
    2. Insert an underscore between a lowercase letter or digit and
       an uppercase letter.  This catches boundaries such as ``aB``
       and ``2N`` while leaving sequences like ``XML`` intact
       because the preceding character in an acronym is itself
       uppercase (and therefore does not match ``[a-z0-9]``).

    Finally the entire result is lower-cased.

    Parameters
    ----------
    name : str
        The PascalCase identifier to convert.

    Returns
    -------
    str
        The snake_case representation of ``name``.  An empty
        string yields an empty string.

    Raises
    ------
    TypeError
        If ``name`` is not a :class:`str`.

    Examples
    --------
    >>> pascal_to_snake("PascalCase")
    'pascal_case'
    >>> pascal_to_snake("MyClassName")
    'my_class_name'
    >>> pascal_to_snake("MyXMLParser")
    'my_xml_parser'
    >>> pascal_to_snake("Class2Name")
    'class2_name'
    >>> pascal_to_snake("")
    ''
    """
    if not isinstance(name, str):
        raise TypeError(
            "pascal_to_snake expected a string, got "
            f"{type(name).__name__!s}"
        )
    if not name:
        return ""

    s1 = _BOUNDARY_BEFORE_UPPERCASE_WITH_TAIL.sub(r"\1_\2", name)
    s2 = _BOUNDARY_AFTER_LOWER_OR_DIGIT.sub(r"\1_\2", s1)
    return s2.lower()