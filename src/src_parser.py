"""src_parser: a simple Python source code parser.

The public entry point is :func:`parse_source`, which takes a string of
Python source code and returns a structured dictionary describing the
imports, functions, classes and module docstring found in it.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List


def parse_source(source: str) -> Dict[str, Any]:
    """Parse a Python source string and return structured information.

    Parameters
    ----------
    source:
        The Python source code to parse.

    Returns
    -------
    dict
        A dictionary with the following keys:

        * ``docstring``  - the module docstring, or ``None``.
        * ``imports``   - list of imported names (``"os"``,
          ``"sys.argv"``, etc.).
        * ``functions`` - list of ``{"name", "line", "args"}`` dicts for
          every ``def`` / ``async def`` found (at any depth).
        * ``classes``   - list of ``{"name", "line", "bases"}`` dicts
          for every ``class`` statement.
        * ``line_count``- number of lines in ``source``.
        * ``char_count``- number of characters in ``source``.
        * ``error``     - only present when ``source`` cannot be parsed;
          contains a human readable error message.

    Raises
    ------
    TypeError
        If ``source`` is not a string.
    """
    if not isinstance(source, str):
        raise TypeError(
            "source must be a string, got " + type(source).__name__
        )

    result: Dict[str, Any] = {
        "docstring": None,
        "imports": [],
        "functions": [],
        "classes": [],
        "line_count": len(source.splitlines()),
        "char_count": len(source),
    }

    # Nothing meaningful to parse; bail out early.
    if not source.strip():
        return result

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        # Capture the error in the result rather than raising so the
        # caller can still inspect whatever was extracted.
        result["error"] = "{0} (line {1})".format(exc.msg, exc.lineno)
        return result

    result["docstring"] = ast.get_docstring(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if module:
                    result["imports"].append(
                        "{0}.{1}".format(module, alias.name)
                    )
                else:
                    # Relative import such as ``from . import helper``.
                    result["imports"].append(alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entry: Dict[str, Any] = {
                "name": node.name,
                "line": node.lineno,
                "args": [a.arg for a in node.args.args],
            }
            if isinstance(node, ast.AsyncFunctionDef):
                entry["async"] = True
            result["functions"].append(entry)
        elif isinstance(node, ast.ClassDef):
            bases: List[str] = []
            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except Exception:  # pragma: no cover - extremely defensive
                    bases.append("<unparseable>")
            result["classes"].append(
                {"name": node.name, "line": node.lineno, "bases": bases}
            )

    return result


__all__ = ["parse_source"]