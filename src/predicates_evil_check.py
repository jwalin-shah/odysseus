"""
predicates_evil_check
====================

A small predicate utility that decides whether a given text is "evil".

In the context of pull-request description checks (see
``/.github/scripts/check-pr-description.js``) a description is considered
"evil" -- and therefore rejected -- when, after stripping HTML-comment
markers, nothing meaningful remains.  Typical offenders are:

* ``None`` / missing values
* empty strings
* strings containing only whitespace
* strings that are *only* an HTML comment such as ``<!-- placeholder -->``
* several HTML comments back-to-back with no real prose

The Python port mirrors the JavaScript helper that does:

    function strip(text) {
        return (text ?? '').replace(/<!--[\\s\\S]*?-->/g, '').trim();
    }

and returns ``True`` when the stripped result is empty.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["predicates_evil_check"]

# Matches a complete HTML comment, including the multi-line form
# ``<!-- ... -->``.  The ``[\s\S]*?`` part is the Python equivalent of
# the JavaScript ``[\s\S]*?`` non-greedy match.
_HTML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def predicates_evil_check(text: Any) -> bool:
    """Return ``True`` when *text* is "evil".

    A value is evil if it is ``None``, not a string, empty, contains only
    whitespace, or contains only HTML comment placeholders (with optional
    surrounding whitespace).

    Parameters
    ----------
    text:
        Arbitrary value to inspect.  ``None`` is treated as evil.

    Returns
    -------
    bool
        ``True`` when *text* should be considered evil, ``False`` otherwise.

    Examples
    --------
    >>> predicates_evil_check("")
    True
    >>> predicates_evil_check("   \\n  ")
    True
    >>> predicates_evil_check("<!-- placeholder -->")
    True
    >>> predicates_evil_check("<!-- a --><!-- b -->")
    True
    >>> predicates_evil_check("<!-- marker -->\\nReal content")
    False
    >>> predicates_evil_check("Looks good to me!")
    False
    """

    # ``None`` (or any missing value) is treated as evil -- the JavaScript
    # reference does the same with the ``?? ''`` fallback.
    if text is None:
        return True

    # Anything that is not a string is considered evil; this keeps the
    # predicate total and avoids surprising ``AttributeError``s on
    # ``.strip()`` for ints, bytes, etc.
    if not isinstance(text, str):
        return True

    # Remove every HTML comment and then look at the remainder.  The
    # JavaScript reference trims the result before checking it; we use
    # ``str.strip()`` for the same effect.
    stripped = _HTML_COMMENT_RE.sub("", text).strip()
    return stripped == ""