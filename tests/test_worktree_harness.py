"""Harness regression tests for the code-lane worktree dispatch.

Bugs covered (all observed in the F5 workpack-dedup failure record):

  1. The dispatcher (src/tool_implementations.py:do_dispatch_mission) spawned
     a subprocess with bare ``python3`` instead of the project venv python.
     Inside the worktree, the test_command ``pytest -q`` then failed with
     ``pytest: command not found``.

  2. The worktree-shell test invocation in src/odysseus.py:do_code ran the
     stated test_command with ``shell=True`` and inherited PATH from the
     parent process — which did not include <repo>/.venv/bin, so pytest was
     unimportable inside the worktree.

  3. core/database.py defaulted DATABASE_URL to the relative path
     ``sqlite:///./data/app.db``. When a worktree test imported any module
     that transitively imported core.database, the engine tried to open
     ``./data/app.db`` relative to the worktree cwd, which has no ``data/``
     directory, producing
     ``sqlalchemy.exc.OperationalError: unable to open database file``.

Each test is RED before the corresponding fix and GREEN after.
"""
import asyncio
import json
import os
import pathlib
import subprocess
import sys

import pytest

from src import tool_implementations


REPO = pathlib.Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# (3) core/database.py: default DATABASE_URL must be absolute                  #
# --------------------------------------------------------------------------- #

def test_default_database_url_is_absolute(monkeypatch, tmp_path):
    """The default SQLite URL must resolve to an absolute path.

    A worktree has its own cwd; a relative ``./data/app.db`` breaks the
    moment any module in the worktree imports core.database.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Re-import with no env override so we exercise the default branch
    import importlib
    monkeypatch.chdir(tmp_path)
    import core.database as dbmod
    importlib.reload(dbmod)
    assert dbmod.DATABASE_URL.startswith("sqlite:////"), (
        f"default DATABASE_URL must be absolute, got {dbmod.DATABASE_URL!r}"
    )
    abs_path = dbmod.DATABASE_URL[len("sqlite:///"):]
    assert os.path.isabs(abs_path), abs_path
    # The parent directory must already exist (the server creates ./data
    # at startup, so we don't fail on first connect).
    assert os.path.isdir(os.path.dirname(abs_path)), os.path.dirname(abs_path)


# --------------------------------------------------------------------------- #
# (1) do_dispatch_mission: must use venv python, not bare python3              #
# --------------------------------------------------------------------------- #

def test_dispatch_mission_uses_venv_python(tmp_path, monkeypatch):
    """The spawned subprocess must be the project venv's python.

    ``python3`` on PATH is the system Homebrew python; it has no pytest and
    no project deps. The worker's first action is importing the codebase,
    which crashes without the venv interpreter.
    """
    captured = {}

    class Process:
        pid = 4242

    def popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return Process()

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(tool_implementations, "MISSION_LOG_DIR", tmp_path, raising=False)
    payload = json.dumps({
        "mission": "fix bug in harness",
        "repo": str(REPO),
        "test": "pytest -q",
    })
    result = asyncio.run(tool_implementations.do_dispatch_mission(payload))
    assert result["exit_code"] == 0, result
    cmd = captured["cmd"]
    assert cmd[0] != "python3", (
        f"do_dispatch_mission must not use bare 'python3' as the launcher; "
        f"got {cmd[0]!r}. Use the project venv interpreter."
    )
    # The launcher should resolve to a python that lives under .venv/
    assert ".venv" in cmd[0], (
        f"launcher must be the project venv python; got {cmd[0]!r}"
    )
    assert os.path.isfile(cmd[0]), f"launcher does not exist: {cmd[0]}"


# --------------------------------------------------------------------------- #
# (2) do_code worktree test subprocess: venv bin must be on PATH              #
# --------------------------------------------------------------------------- #

def test_venv_bin_walks_up_to_main_repo(tmp_path, monkeypatch):
    """A worktree at <main>/.ody-worktrees/<branch>/ must resolve to the
    MAIN repo's venv, not the worktree's. Otherwise pytest is not on PATH
    in the worktree shell, which was the F5 / harness failure mode.
    """
    from src.odysseus import _venv_bin
    # Fake layout: <main>/.venv/bin and <main>/.ody-worktrees/<branch>/
    main = tmp_path / "main"
    (main / ".venv" / "bin").mkdir(parents=True)
    wt = main / ".ody-worktrees" / "ody-test"
    wt.mkdir(parents=True)
    assert _venv_bin(str(wt)) == (main / ".venv" / "bin")
    # When there is no venv at all, return None (callers fall back to system).
    no_venv = tmp_path / "no_venv"
    no_venv.mkdir()
    assert _venv_bin(str(no_venv)) is None


def test_worktree_test_subprocess_venv_on_path(tmp_path, monkeypatch):
    """The worktree-shell test invocation must put venv/bin on PATH.

    We exercise the do_code path in a way that does not need a real agent
    CLI: we mock out the worktree creation and the tool call, then capture
    the env passed to the test subprocess.
    """
    import argparse
    import src.odysseus as ody

    captured_runs = []

    def fake_run(cmd, **kwargs):
        captured_runs.append((cmd, kwargs))
        class _R:
            returncode = 0
            stdout = "1 passed in 0.01s"
            stderr = ""
        return _R()

    def fake_popen(*args, **kwargs):
        class _P:
            pid = 9999
        return _P()

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    # Make a real git repo inside tmp_path so the worktree machinery is
    # happy. We must not actually clone Odysseus; we just need .git/.
    repo = tmp_path / "fake_repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email",
                    "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name",
                    "Test"], check=True)
    (repo / "README.md").write_text("test\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m",
                    "init"], check=True)
    # Create a fake .venv/bin inside the fake repo so the harness's
    # ``<repo>/.venv/bin`` PATH-prepend actually fires. (We are not
    # installing pytest here; we are just proving the harness threads the
    # path through.)
    (repo / ".venv" / "bin").mkdir(parents=True)

    args = argparse.Namespace(
        mission="noop", repo=str(repo), test="pytest -q", timeout=60,
        hybrid=None, tool="claude", dry_run=False,
    )
    docs = ""
    ody.do_code("noop", args, docs)
    # Find the call that ran the test command.
    test_calls = [
        (cmd, kw) for (cmd, kw) in captured_runs
        if (cmd == "pytest -q" or cmd == ["pytest -q"])
    ]
    assert test_calls, (
        f"test subprocess was not invoked; got calls: "
        f"{[(c, k.get('env', {}).get('PATH', '')) for c, k in captured_runs]!r}"
    )
    _, kwargs = test_calls[0]
    env = kwargs.get("env") or os.environ
    path = env.get("PATH", "")
    venv_bin = str(repo / ".venv" / "bin")
    assert venv_bin in path.split(":"), (
        f"worktree test subprocess PATH must include {venv_bin}; got {path!r}"
    )
