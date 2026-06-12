"""Red-gate tests for the ody_supervisor chat-tool wiring.

The supervisor (src/ody_supervisor.py) is already a working CLI
(supervise_main accepts --action status|enqueue|propose|run). These
tests verify the chat-tool surface that fronts it: registration,
description, and the dispatch wrapper's translation of JSON to argv.
"""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# Defer the heavy module imports until after sys.path is set so the
# circular import between src.agent_tools <-> src.tool_parsing resolves.
import importlib
agent_tools = importlib.import_module("src.agent_tools")
tool_execution = importlib.import_module("src.tool_execution")
tool_implementations = importlib.import_module("src.tool_implementations")
tool_index = importlib.import_module("src.tool_index")
tool_schemas = importlib.import_module("src.tool_schemas")


def test_ody_supervisor_in_tool_tags():
    """The settings panel /admin/tools endpoint reads TOOL_TAGS. Without
    this entry, ody_supervisor would be unknown and the admin disable/enable
    flow would not surface it."""
    assert "ody_supervisor" in agent_tools.TOOL_TAGS


def test_ody_supervisor_in_always_available():
    """Always-on: RAG retrieval should not be able to hide the supervisor."""
    assert "ody_supervisor" in tool_index.ALWAYS_AVAILABLE


def test_ody_supervisor_in_builtin_descriptions():
    """A description is required for the RAG selector to embed it."""
    desc = tool_index.BUILTIN_TOOL_DESCRIPTIONS.get("ody_supervisor", "")
    assert desc, "ody_supervisor must have a BUILTIN_TOOL_DESCRIPTIONS entry"
    # Description should mention the bounded / queue nature so RAG retrieves
    # it for "check the queue" / "propose missions" prompts.
    assert "bounded" in desc.lower() or "queue" in desc.lower()


def test_ody_supervisor_json_schema_is_registered():
    """The function-call schema must be present so the model can invoke it."""
    schemas = None
    for attr in ("FUNCTION_TOOL_SCHEMAS", "TOOL_SCHEMAS", "ALL_SCHEMAS"):
        schemas = getattr(tool_schemas, attr, None)
        if schemas:
            break
    assert schemas is not None, "no schema list found in tool_schemas"
    names = [s.get("function", {}).get("name") for s in schemas]
    assert "ody_supervisor" in names, "ody_supervisor schema missing"


def test_do_ody_supervisor_rejects_unknown_action():
    """Unknown actions must return a clean error, not crash."""
    async def run():
        r = await tool_implementations.do_ody_supervisor(
            '{"action": "explode"}'
        )
        assert r["exit_code"] == 1
        assert "action" in r["error"]
        assert "status|enqueue|propose|run" in r["error"]
    asyncio.run(run())


def test_do_ody_supervisor_dispatches_status_action():
    """status action should be wired through to supervise_main and return
    its JSON output under .result. We mock the subprocess to avoid the
    real CLI and verify the argv + cwd are correct."""
    canned = json.dumps({"pending": 0, "ledger": "/tmp/ledger.jsonl",
                         "queue": "/tmp/queue.jsonl"})

    class _Fake:
        returncode = 0
        async def communicate(self):
            return canned.encode(), b""

    async def fake_exec(*args, **kwargs):
        return _Fake()

    async def run():
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            r = await tool_implementations.do_ody_supervisor(
                '{"action": "status"}'
            )
        assert r["exit_code"] == 0
        assert r["action"] == "status"
        assert r["result"] == json.loads(canned)
        # No stderr on the happy path
        assert r["stderr"] == ""

    asyncio.run(run())


def test_do_ody_supervisor_passes_action_first():
    """supervise_main is an argparse CLI: action must be the leading
    positional, then the flag/value pairs. Verify the argv shape."""
    captured = {}

    class _Fake:
        returncode = 0
        async def communicate(self):
            return b'{"pending": 0}', b""

    async def fake_exec(*args, **kwargs):
        captured["argv"] = args
        captured["cwd"] = kwargs.get("cwd")
        return _Fake()

    async def run():
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            await tool_implementations.do_ody_supervisor(
                '{"action": "enqueue", "mission": "fix the bug", '
                '"test": "pytest -q", "max_attempts": 3}'
            )
        # Pull out the supervisor module + flags from the captured argv.
        # args is: (python, "-m", "src.ody_supervisor", *flags)
        argv = list(captured["argv"])
        # We launch via `python -c "..."` + runpy.run_module('src.ody_supervisor').
        # The argv we capture is (python, -c, <inline>, action, *flags).
        assert any("src.ody_supervisor" in a for a in argv[:3]), (
            f"supervisor module not invoked: {argv}"
        )
        # action is the first positional after the -c inline
        assert argv[3] == "enqueue", (
            f"action 'enqueue' must be the first positional after the inline, "
            f"got {argv[3]!r}"
        )
        # flags follow
        flag_str = " ".join(argv[4:])
        assert "--mission" in flag_str and "fix the bug" in flag_str
        assert "--test" in flag_str and "pytest -q" in flag_str
        assert "--max-attempts" in flag_str and "3" in flag_str

    asyncio.run(run())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
