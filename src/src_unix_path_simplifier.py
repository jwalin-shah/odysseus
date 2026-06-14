"""Unix path simplifier.

Given an absolute Unix-style path, returns the canonical (simplified) version
with redundant slashes collapsed, ``.`` components removed, and ``..``
components resolved against the parent directory. ``..`` references that
would go above the root are silently dropped.
"""


def simplify_path(path: str) -> str:
    """Return the simplified canonical form of a Unix-style absolute path.

    The input is assumed to be an absolute path (starting with ``/``).
    The function processes each ``/``-separated component:

    * ``""`` (empty) and ``"."`` are skipped.
    * ``".."`` pops the last directory from the stack if the stack is
      non-empty; otherwise it is discarded (we are already at the root).
    * Any other component is appended to the stack.

    The result is always an absolute path.  An empty input maps to ``"/"``,
    which is also the result when the simplified path is the root itself.

    Examples
    --------
    >>> simplify_path("/home/")
    '/home'
    >>> simplify_path("/a/./b/../../c/")
    '/c'
    >>> simplify_path("/a//b/")
    '/a/b'
    >>> simplify_path("/../")
    '/'
    """
    if not path:
        return "/"

    stack = []
    for component in path.split("/"):
        if not component or component == ".":
            # Collapse empty pieces (from leading or duplicate '/') and
            # the current-directory reference.
            continue
        if component == "..":
            # Pop the parent directory if we have one; otherwise stay at
            # the root because we cannot go above it.
            if stack:
                stack.pop()
            continue
        stack.append(component)

    return "/" + "/".join(stack)