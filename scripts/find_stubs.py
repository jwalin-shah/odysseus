#!/usr/bin/env python3
"""Find stub functions in the odysseus codebase.

A function/method body is considered a stub when it consists of:
  * the ``pass`` statement
  * the ``...`` (Ellipsis) literal
  * ``raise NotImplementedError`` (with or without a message)
  * a single TODO comment (no executable statements)

Usage::

    python scripts/find_stubs.py
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {
    "tests",
    "__pycache__",
    "venv",
    ".venv",
    ".git",
    "node_modules",
    ".tox",
    "build",
    "dist",
    ".eggs",
}


def _body_is_todo_comment(func_node: ast.AST, source_lines: list[str]) -> bool:
    """Detect a function whose only body content is a TODO comment.

    Comments are not represented in the AST, so we look at the source
    lines between the ``def`` line and the closing line for a TODO marker.
    """
    if func_node.body:
        return False
    lineno = getattr(func_node, "lineno", None)
    end_lineno = getattr(func_node, "end_lineno", None)
    if lineno is None or end_lineno is None:
        return False
    for i in range(lineno, min(end_lineno, len(source_lines))):
        stripped = source_lines[i].strip()
        if not stripped:
            continue
        return "# TODO" in stripped
    return False


def _is_stub_body(func_node: ast.AST, source_lines: list[str]) -> bool:
    """Return True if ``func_node`` has a stub-like body."""
    body = getattr(func_node, "body", None)
    if not body:
        return _body_is_todo_comment(func_node, source_lines)
    if len(body) != 1:
        return False
    stmt = body[0]
    # pass
    if isinstance(stmt, ast.Pass):
        return True
    # ...  (Ellipsis literal)
    if (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and stmt.value.value is Ellipsis
    ):
        return True
    # raise NotImplementedError
    if isinstance(stmt, ast.Raise) and stmt.exc is not None:
        exc = stmt.exc
        if isinstance(exc, ast.Call):
            func = exc.func
            if isinstance(func, ast.Name) and func.id == "NotImplementedError":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "NotImplementedError":
                return True
    return False


def _qualified(node: ast.AST, prefix: str) -> str:
    name = getattr(node, "name", "")
    return f"{prefix}.{name}" if prefix else name


def _walk(
    tree: ast.AST,
    path: Path,
    source_lines: list[str],
    prefix: str = "",
) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, qualified_name)`` for each stub function/method."""
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_stub_body(node, source_lines):
                yield path, _qualified(node, prefix)
        elif isinstance(node, ast.ClassDef):
            cls_name = _qualified(node, prefix)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if _is_stub_body(item, source_lines):
                        yield path, _qualified(item, cls_name)
                # Recurse into nested classes to find their methods too.
                yield from _walk(item, path, source_lines, cls_name)


def find_stubs_in_file(path: Path) -> Iterator[tuple[Path, str]]:
    """Yield ``(path, qualified_name)`` for every stub found in ``path``."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return
    yield from _walk(tree, path, source.splitlines())


def main() -> int:
    stubs: list[tuple[Path, str]] = []
    py_count = 0

    for root, dirs, files in os.walk(REPO_ROOT):
        # Prune excluded directories in-place so os.walk skips them.
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
        for fname in sorted(files):
            if not fname.endswith(".py"):
                continue
            py_count += 1
            full = Path(root) / fname
            stubs.extend(find_stubs_in_file(full))

    for path, name in stubs:
        rel = path.relative_to(REPO_ROOT)
        print(f"{rel}:{name}")

    print(f"\nTotal: {len(stubs)} stub(s) found in {py_count} Python file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())