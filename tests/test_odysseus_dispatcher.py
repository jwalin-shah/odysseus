import asyncio
import json
import subprocess

from src import tool_implementations
from tests.helpers.cli_loader import load_script


def test_do_dispatch_mission_rejects_invalid_m3_brief_before_spawn(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **k: calls.append(1)
    )
    monkeypatch.setattr(tool_implementations, "MISSION_LOG_DIR", tmp_path, raising=False)
    payload = json.dumps({
        "mission": "fix bug",
        "brief": {
            "affected_files": [],
            "proposed_fix": "Fix the bug.",
            "proposed_test": "pytest -q",
            "mission_prompt": "Fix the bug.",
            "confidence": 0.9,
        },
    })

    result = asyncio.run(tool_implementations.do_dispatch_mission(payload))

    assert result["exit_code"] == 1
    assert result["gate"] == "mission_brief"
    assert result["field"] == "affected_files"
    assert calls == []


def test_do_dispatch_mission_rejects_halt_prompt_before_spawn(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **k: calls.append(1)
    )
    monkeypatch.setattr(tool_implementations, "MISSION_LOG_DIR", tmp_path, raising=False)

    result = asyncio.run(tool_implementations.do_dispatch_mission(json.dumps({
        "mission": "I cannot comply with this request",
    })))

    assert result["exit_code"] == 1
    assert result["gate"] == "halt"
    assert calls == []


def test_do_dispatch_mission_stamps_preflight_task_hash(tmp_path, monkeypatch):
    class Process:
        pid = 123

    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: Process())
    monkeypatch.setattr(tool_implementations, "MISSION_LOG_DIR", tmp_path, raising=False)

    result = asyncio.run(tool_implementations.do_dispatch_mission(json.dumps({
        "mission": "fix bug",
        "lane": "code",
    })))

    record = json.loads((tmp_path / "dispatch-dedup.jsonl").read_text().strip())
    assert result["task_hash"] == record["task_hash"]
    assert len(result["task_hash"]) == 64


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
