"""worker_runtime: write-scope interceptor for Odysseus agent workers.

F1 from FABLE_BLUEPRINT.md / operator-contract.md.

intercept_tool_call(tool, path, scope, role="implementer") -> bool

  scope="read-only"         → blocks Write, Edit, Bash, Delete always
  scope="write=<p1>,<p2>"  → Write/Edit allowed only inside listed path prefixes;
                              Bash always blocked (can't scope a shell)
  scope="full-access"       → allows everything (for trusted worktree context only)
  scope=anything else/None  → DEFAULT DENY (missing evidence = deny)

  role="reviewer"           → hard read-only regardless of scope string
  role="implementer"        → falls through to scope rules (default)

Raises ScopeViolation on any blocked call.
Returns True on every allowed call.

This module is deliberately small and dependency-free — it is the innermost
safety layer and must not import anything from the rest of the Odysseus stack.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Exception
# ─────────────────────────────────────────────────────────────────────────────

class ScopeViolation(Exception):
    """Raised when a tool call violates the declared scope or role."""


# ─────────────────────────────────────────────────────────────────────────────
# Tool classification
# ─────────────────────────────────────────────────────────────────────────────

# Tools that mutate filesystem state.
_WRITE_TOOLS = frozenset({"write", "edit", "delete", "multiedit"})

# Bash is always a special case — even a "read" bash command can write via
# redirection, so it's treated as mutating unless scope=full-access.
_SHELL_TOOLS = frozenset({"bash", "shell", "run"})

# Tools that are unconditionally read-only.
_READ_TOOLS = frozenset({
    "read", "glob", "grep", "ls", "find", "search",
    "list", "view", "cat", "head", "tail",
})


def _normalise_tool(tool: str) -> str:
    return (tool or "").strip().lower()


def _is_write_tool(tool_norm: str) -> bool:
    return tool_norm in _WRITE_TOOLS


def _is_shell_tool(tool_norm: str) -> bool:
    return tool_norm in _SHELL_TOOLS


def _is_read_tool(tool_norm: str) -> bool:
    return tool_norm in _READ_TOOLS


# ─────────────────────────────────────────────────────────────────────────────
# Path helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_path(raw: str) -> Path:
    """Resolve and normalise a path, collapsing .. segments."""
    return Path(raw).resolve()


def _path_under_any(target: Path, allowed_prefixes: list[str]) -> bool:
    """Return True if target is a sub-path of any allowed prefix."""
    for prefix_str in allowed_prefixes:
        try:
            prefix = _resolve_path(prefix_str)
            target.relative_to(prefix)
            return True
        except ValueError:
            continue
    return False


def _parse_write_paths(scope: str) -> list[str]:
    """Parse 'write=/a,/b/c' into ['/a', '/b/c']."""
    after = scope[len("write="):]
    return [p.strip() for p in after.split(",") if p.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Main interceptor
# ─────────────────────────────────────────────────────────────────────────────

def intercept_tool_call(
    tool: str,
    path: str,
    scope: Optional[str],
    role: str = "implementer",
) -> bool:
    """Evaluate whether a tool call is permitted under the given scope and role.

    Returns True if the call is allowed.
    Raises ScopeViolation if the call is blocked.

    Parameters
    ----------
    tool:  Tool name as reported by the agent harness (e.g. "Write", "Bash").
    path:  File path or shell command string (used for path-restricted scopes).
    scope: Scope declaration. See module docstring for valid values.
    role:  Agent role. "reviewer" forces read-only regardless of scope.
    """
    t = _normalise_tool(tool)

    # ── Classify tool mutability ──────────────────────────────────────────
    # Unknown tools (not in any frozenset) are treated as potentially mutating.
    # Default-deny posture: if we don't know it's safe to read, we block it.
    is_read = _is_read_tool(t)
    is_shell = _is_shell_tool(t)

    # ── Read-only tools: always allowed regardless of role or scope ───────
    if is_read:
        return True

    # ── Reviewer role: hard read-only, no exceptions ──────────────────────
    # Any non-read tool is blocked for reviewer, including unknown tools.
    if (role or "").strip().lower() == "reviewer":
        raise ScopeViolation(
            f"ScopeViolation: tool={tool!r} is blocked for role='reviewer' "
            f"(reviewer is always read-only, scope={scope!r} is ignored)"
        )

    # ── Normalise scope ───────────────────────────────────────────────────
    scope_str = (scope or "").strip().lower()

    # ── full-access scope (must be explicit, not default) ─────────────────
    if scope_str == "full-access":
        return True

    # ── read-only scope ───────────────────────────────────────────────────
    if scope_str == "read-only":
        raise ScopeViolation(
            f"ScopeViolation: tool={tool!r} is blocked in scope='read-only' "
            f"(path={path!r})"
        )

    # ── write=<paths> scope ───────────────────────────────────────────────
    if scope_str.startswith("write="):
        # Bash is always blocked in path-scoped mode — can't scope a shell
        if _is_shell_tool(t):
            raise ScopeViolation(
                f"ScopeViolation: tool={tool!r} (shell) is blocked even in "
                f"write-path scope (scope={scope!r}). Bash cannot be path-scoped."
            )
        allowed = _parse_write_paths(scope_str)
        if not allowed:
            raise ScopeViolation(
                f"ScopeViolation: scope={scope!r} has no allowed paths — "
                f"defaulting to deny for tool={tool!r}"
            )
        target = _resolve_path(path)
        if _path_under_any(target, allowed):
            return True
        raise ScopeViolation(
            f"ScopeViolation: tool={tool!r} path={path!r} is outside allowed "
            f"paths {allowed} (scope={scope!r})"
        )

    # ── Default: unknown/empty/None scope → DENY ──────────────────────────
    raise ScopeViolation(
        f"ScopeViolation: tool={tool!r} blocked — unknown or missing scope "
        f"{scope!r}. Default posture is deny. "
        f"Use scope='read-only', 'write=<paths>', or 'full-access'."
    )
