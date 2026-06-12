import asyncio
import json
import subprocess

from src import tool_implementations
from tests.helpers.cli_loader import load_script


def test_is_runnable_subcommand_requires_executable_file(tmp_path):
    cli = load_script("odysseus")
    sub = tmp_path / "odysseus-demo"
    sub.write_text("#!/bin/sh\n")
    sub.chmod(0o644)

    assert cli._is_runnable_subcommand(sub) is False

    sub.chmod(0o755)
    assert cli._is_runnable_subcommand(sub) is True


def test_do_dispatch_mission_dedups_within_cooldown(tmp_path, monkeypatch):
    calls = []
    log_files = []

    class Process:
        pid = 123

    def popen(*args, **kwargs):
        calls.append((args, kwargs))
        log_files.append(kwargs["stdout"])
        return Process()

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(tool_implementations, "MISSION_LOG_DIR", tmp_path, raising=False)
    payload = json.dumps({
        "mission": "fix bug in calc.py",
        "repo": "/tmp/repo",
        "test": "pytest -q",
    })

    first = asyncio.run(tool_implementations.do_dispatch_mission(payload))
    second = asyncio.run(tool_implementations.do_dispatch_mission(payload))

    assert first["exit_code"] == 0
    assert len(calls) == 1
    assert second["exit_code"] == 0
    assert second["duplicate_of"] == first["dispatch_id"]
    assert second["dispatch_id"] == first["dispatch_id"]
    assert second["pid"] == first["pid"]
    assert second["log"] == first["log"]
    assert log_files[0].closed


def test_do_dispatch_mission_allows_retry_after_cooldown(tmp_path, monkeypatch):
    calls = []
    clock = iter([1000.0, 4601.0])

    class Process:
        pid = 123

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append(1) or Process())
    monkeypatch.setattr(tool_implementations, "MISSION_LOG_DIR", tmp_path, raising=False)
    monkeypatch.setattr("time.time", lambda: next(clock))
    payload = json.dumps({"mission": "fix bug", "repo": "/tmp/repo", "test": "pytest -q"})

    asyncio.run(tool_implementations.do_dispatch_mission(payload))
    asyncio.run(tool_implementations.do_dispatch_mission(payload))

    assert len(calls) == 2


def test_do_dispatch_mission_does_not_record_failed_spawn(tmp_path, monkeypatch):
    calls = []

    def popen(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("spawn failed")

        class Process:
            pid = 123

        return Process()

    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(tool_implementations, "MISSION_LOG_DIR", tmp_path, raising=False)
    payload = json.dumps({"mission": "fix bug", "repo": "/tmp/repo", "test": "pytest -q"})

    first = asyncio.run(tool_implementations.do_dispatch_mission(payload))
    second = asyncio.run(tool_implementations.do_dispatch_mission(payload))

    assert first["exit_code"] == 1
    assert second["exit_code"] == 0
    assert len(calls) == 2
