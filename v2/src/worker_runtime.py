"""
worker_runtime.py — Write-scope interceptor for Odysseus cockpit workers.

Usage:

    from worker_runtime import intercept_tool_call, ScopeViolation

    def handle_tool_call(tool, path, scope):
        try:
            intercept_tool_call(tool, path, scope)
            # proceed
        except ScopeViolation:
            # reject, rollback, or warn

Reads ODY_SCOPE env var as the default scope if not explicitly passed.
"""

import os


class ScopeViolation(Exception):
    """Raised when a tool call violates the current write scope."""

    def __init__(self, tool: str, path: str = "", scope: str = "", reason: str = ""):
        self.tool = tool
        self.path = path
        self.scope = scope
        self.reason = reason
        super().__init__(
            f"ScopeViolation: tool={tool}, path={path}, scope={scope}, reason={reason}"
        )


# Tools that modify files on disk.
_WRITE_TOOLS = frozenset({"Write", "Edit"})

# Tools that are inherently write-side (shell execution).
_WRITE_BASH = frozenset({"Bash"})

# Tools considered read-only (always allowed under any scope).
_READ_TOOLS = frozenset({
    "Read", "Glob", "Grep", "LS", "Agent", "TaskRead", "Skill",
    "NotebookRead", "WebFetch", "BashOutput", "ProcessAssert",
    "TaskList", "TaskOutput", "ExitWorktree",
})

# All known tool names — anything not in write or read sets is treated as read-only.
_ALL_TOOLS = _WRITE_TOOLS | _WRITE_BASH | _READ_TOOLS

# Unrestricted scope values that permit every tool.
_UNRESTRICTED = frozenset({"unrestricted", "write=*"})


def _parse_write_paths(scope: str) -> list[str]:
    """Extract per-path allowlist from a 'write=<paths>' scope string."""
    raw = scope.split("=", 1)[1]
    if not raw or raw.strip() == "":
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def intercept_tool_call(tool: str, path: str = "", scope: str = "") -> None:
    """
    Validate a tool call against the current scope.

    Args:
        tool: Tool name, e.g. "Write", "Edit", "Bash", "Read".
        path: File/directory path the tool operates on (for Write/Edit; ignored for others).
        scope: Scope string. Defaults to ODY_SCOPE env var if empty.

    Raises:
        ScopeViolation: If the tool call is not permitted under the current scope.
    """
    if not scope:
        scope = os.environ.get("ODY_SCOPE", "")

    scope_lower = scope.lower().strip()

    # Read tools are always allowed.
    if tool in _READ_TOOLS:
        return

    # Unrestricted scopes allow everything.
    if scope_lower in _UNRESTRICTED:
        return

    # Read-only scope: reject all write tools.
    if scope_lower == "read-only":
        if tool in _WRITE_TOOLS:
            raise ScopeViolation(
                tool=tool,
                path=path,
                scope=scope,
                reason=f"write tool '{tool}' is not allowed in read-only scope",
            )
        if tool in _WRITE_BASH:
            raise ScopeViolation(
                tool=tool,
                path=path,
                scope=scope,
                reason=f"bash is not allowed in read-only scope",
            )
        # Anything unrecognized but not a read tool: reject in read-only.
        if tool not in _READ_TOOLS:
            raise ScopeViolation(
                tool=tool,
                path=path,
                scope=scope,
                reason=f"unknown tool '{tool}' is not allowed in read-only scope",
            )
        return

    # write=<paths> scope: allow listed tools/paths only.
    if scope_lower.startswith("write="):
        allowed_paths = _parse_write_paths(scope)
        if tool in _WRITE_TOOLS:
            if not allowed_paths:
                raise ScopeViolation(
                    tool=tool,
                    path=path,
                    scope=scope,
                    reason=f"no write paths configured in scope '{scope}'",
                )
            if not _path_matches_any(path, allowed_paths):
                raise ScopeViolation(
                    tool=tool,
                    path=path,
                    scope=scope,
                    reason=f"path '{path}' not in allowed paths {allowed_paths}",
                )
            return
        if tool in _WRITE_BASH:
            raise ScopeViolation(
                tool=tool,
                path=path,
                scope=scope,
                reason=f"bash is not allowed in scoped write scope '{scope}'",
            )
        # Non-write, non-read tools: treat as read, allow.
        if tool not in _READ_TOOLS:
            return  # pass through for tools we don't classify

        return

    # Unknown scope: reject everything except known read tools.
    if tool in _WRITE_TOOLS:
        raise ScopeViolation(
            tool=tool,
            path=path,
            scope=scope,
            reason=f"unknown scope '{scope}' does not permit write tool '{tool}'",
        )
    if tool in _WRITE_BASH:
        raise ScopeViolation(
            tool=tool,
            path=path,
            scope=scope,
            reason=f"unknown scope '{scope}' does not permit bash",
        )


def _path_matches_any(path: str, allowed: list[str]) -> bool:
    """Check if *path* matches any entry in *allowed* (supports prefix matching)."""
    import os as _os
    normalized = _os.path.normpath(path)
    for entry in allowed:
        entry_norm = _os.path.normpath(entry)
        if normalized == entry_norm:
            return True
        # Allow writes within a directory (prefix match with /).
        if normalized.startswith(entry_norm + "/"):
            return True
    return False
