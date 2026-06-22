"""
Tests for worker_runtime — write-scope interceptor.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from worker_runtime import intercept_tool_call, ScopeViolation


# ---------------------------------------------------------------------------
# Read-only scope
# ---------------------------------------------------------------------------

def test_read_only_rejects_write():
    with pytest.raises(ScopeViolation) as exc_info:
        intercept_tool_call("Write", "/foo/bar.py", scope="read-only")
    assert exc_info.value.tool == "Write"
    assert exc_info.value.scope == "read-only"
    assert "not allowed" in exc_info.value.reason


def test_read_only_rejects_bash():
    with pytest.raises(ScopeViolation) as exc_info:
        intercept_tool_call("Bash", "", scope="read-only")
    assert exc_info.value.tool == "Bash"
    assert exc_info.value.scope == "read-only"
    assert "not allowed" in exc_info.value.reason


def test_read_only_allows_read_tools():
    for tool in ("Read", "Glob", "Grep", "LS", "WebFetch"):
        intercept_tool_call(tool, "/foo/bar.py", scope="read-only")  # no exception


# ---------------------------------------------------------------------------
# Scoped write
# ---------------------------------------------------------------------------

def test_write_scoped_allows_listed_path():
    intercept_tool_call("Write", "/allowed/file.py", scope="write=/allowed/file.py")


def test_write_scoped_rejects_other_path():
    with pytest.raises(ScopeViolation) as exc_info:
        intercept_tool_call("Write", "/other/file.py", scope="write=/allowed/file.py")
    assert exc_info.value.tool == "Write"
    assert "not in allowed paths" in exc_info.value.reason


def test_write_scoped_allows_bash_read_only_but_rejects_writes():
    """In write-scoped scope, Bash is always rejected."""
    # Bash is always denied in scoped write mode.
    with pytest.raises(ScopeViolation):
        intercept_tool_call("Bash", "", scope="write=/allowed/file.py")
    # Writes to allowed path succeed.
    intercept_tool_call("Write", "/allowed/file.py", scope="write=/allowed/file.py")
    # Writes to disallowed path fail.
    with pytest.raises(ScopeViolation):
        intercept_tool_call("Edit", "/other/file.py", scope="write=/allowed/file.py")


# ---------------------------------------------------------------------------
# Environment variable default
# ---------------------------------------------------------------------------

def test_env_var_default(monkeypatch):
    monkeypatch.setenv("ODY_SCOPE", "read-only")
    with pytest.raises(ScopeViolation):
        intercept_tool_call("Write", "/foo.py", scope="")
    monkeypatch.setenv("ODY_SCOPE", "write=/allowed/x.py")
    intercept_tool_call("Write", "/allowed/x.py", scope="")
    monkeypatch.delenv("ODY_SCOPE")


# ---------------------------------------------------------------------------
# Unrestricted scope
# ---------------------------------------------------------------------------

def test_unrestricted_scope_allows_everything():
    for scope in ("unrestricted", "write=*"):
        intercept_tool_call("Write", "/anything.py", scope=scope)
        intercept_tool_call("Edit", "/anything.py", scope=scope)
        intercept_tool_call("Bash", "", scope=scope)
        intercept_tool_call("Read", "/anything.py", scope=scope)
