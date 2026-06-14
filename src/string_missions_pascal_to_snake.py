"""Convert PascalCase / CamelCase identifiers to snake_case.

This module exposes a single helper, :func:`string_missions_pascal_to_snake`,
which normalises strings written in *PascalCase* or *camelCase* into the
lower-case, underscore-separated form that is idiomatic in Python.
"""

from __future__ import annotations

from typing import Any

__all__ = ["string_missions_pascal_to_snake"]


def string_missions_pascal_to_snake(value: Any) -> str:
    """Return the *snake_case* form of *value*.

    The conversion is performed by scanning the input once and inserting
    an underscore between a character and a following uppercase letter
    whenever one of the following holds:

    * the preceding character is a lower-case letter or a digit, or
    * the preceding character is an upper-case letter **and** the
      character that follows the current one is a lower-case letter
      (this is what splits the trailing ``S`` of ``HTTPS`` from the
      ``C`` of ``Connection``).

    The resulting string is then lower-cased.

    Parameters
    ----------
    value:
        The identifier to convert.  Must be a :class:`str`; any other
        type raises :class:`TypeError`.

    Returns
    -------
    str
        The snake-case form of *value*.  An empty string is returned
        unchanged.

    Examples
    --------
    >>> string_missions_pascal_to_snake("PascalCase")
    'pascal_case'
    >>> string_missions_pascal_to_snake("camelCase")
    'camel_case'
    >>> string_missions_pascal_to_snake("HTTPSConnection")
    'https_connection'
    >>> string_missions_pascal_to_snake("XMLHttpRequest")
    'xml_http_request'
    >>> string_missions_pascal_to_snake("Hello2World")
    'hello2_world'
    """
    if not isinstance(value, str):
        raise TypeError(
            "string_missions_pascal_to_snake expected str, got "
            f"{type(value).__name__}"
        )

    if not value:
        return ""

    chars: list[str] = []
    length = len(value)
    for i, ch in enumerate(value):
        if ch.isupper() and i > 0:
            prev = value[i - 1]
            # Condition 1: a lowercase letter or a digit precedes this
            # uppercase letter -> insert a word boundary.
            if prev.islower() or prev.isdigit():
                chars.append("_")
            # Condition 2: an uppercase letter is followed by a lowercase
            # letter and is itself preceded by another uppercase letter
            # -> we are in the middle of an acronym and need to split
            # before the *last* capital (e.g. "HTTP" + "S" + "Connection").
            elif (
                prev.isupper()
                and i + 1 < length
                and value[i + 1].islower()
            ):
                chars.append("_")
        chars.append(ch)

    return "".join(chars).lower()