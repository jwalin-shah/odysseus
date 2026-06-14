"""
Unix Path Simplifier
====================

A small utility module that simplifies Unix-style absolute paths following
the standard rules used by shells like bash and the POSIX specification.

Rules implemented:
  * ``.``       -> refers to the current directory, ignored
  * ``..``      -> refers to the parent directory, pops one level from the
                   current stack (but never goes above the root ``/``)
  * ``//``      -> consecutive slashes are treated as a single slash
  * trailing ``/`` -> removed (except when the canonical path is the root)

The function is intentionally implemented with an explicit stack rather than
``pathlib`` because ``pathlib.PurePosixPath`` does not perform lexical
``..`` resolution, which is what is required here.
"""

from __future__ import annotations

from typing import List


def simplify_path(path: str) -> str:
    """Return the canonical simplified form of a Unix-style absolute path.

    Parameters
    ----------
    path:
        An absolute Unix-style path.  An empty string is treated as the
        root directory and therefore returns ``"/"``.

    Returns
    -------
    str
        The simplified canonical path, always starting with ``"/"`` and
        never containing a trailing slash (except for the root itself).

    Examples
    --------
    >>> simplify_path("/home/")
    '/home'
    >>> simplify_path("/../")
    '/'
    >>> simplify_path("/home//foo/")
    '/home/foo'
    >>> simplify_path("/a/./b/../../c/")
    '/c'
    """
    # Defensive: an empty (or ``None``-like) input collapses to root.
    if not path:
        return "/"

    # Splitting on "/" gives us an easy way to ignore empty fragments
    # that come from leading, trailing or consecutive separators.
    # The fragments we care about are non-empty strings that are not
    # "." (current dir) or ".." (parent dir).
    parts: List[str] = path.split("/")
    stack: List[str] = []

    for part in parts:
        if part == "" or part == ".":
            # Empty fragment (from "//") or explicit "current dir".
            continue
        if part == "..":
            # Go up one level, but never above the root.
            if stack:
                stack.pop()
            # If the stack is already empty we are at the root, so the
            # ".." is silently discarded (matches POSIX behaviour).
            continue
        # Otherwise it's a real directory name; keep it.
        stack.append(part)

    # Reassemble the canonical path.  An empty stack means we are at
    # the root, so the result must be exactly "/".
    return "/" + "/".join(stack)