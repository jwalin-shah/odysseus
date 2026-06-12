"""Red-gate tests for the per-agent direct chat tool (tla_chat)."""
import asyncio
import json
import os
import subprocess
import sys

import pytest

from src import tool_implementations


def test_tla_chat_requires_agent_and_message():
    """Both agent and message are required."""
    r = asyncio.run(tool_implementations.do_tla_chat("{}"))
    assert r["exit_code"] == 1
    assert "agent is required" in r["error"]

    r = asyncio.run(tool_implementations.do_tla_chat(
        json.dumps({"agent": "claude"})
    ))
    assert r["exit_code"] == 1
    assert "message is required" in r["error"]


def test_tla_chat_rejects_unknown_agent():
    r = asyncio.run(tool_implementations.do_tla_chat(
        json.dumps({"agent": "no-such-agent", "message": "hi"})
    ))
    assert r["exit_code"] == 1
    assert "unknown agent" in r["error"]
    # Should also surface the known agents list so the caller can self-correct.
    assert "known_agents" in r
    assert "claude" in r["known_agents"]
    assert "ca" in r["known_agents"]
    assert "cb" in r["known_agents"]


def test_tla_chat_runs_an_agent(monkeypatch):
    """A real (mocked) agent run returns a structured result."""
    from src import odysseus
    def fake_run_agent(agent, prompt, cwd=None, timeout=180):
        return 0, f"ECHO from {agent}: {prompt}", "", 0.4
    monkeypatch.setattr(odysseus, "run_agent", fake_run_agent)

    r = asyncio.run(tool_implementations.do_tla_chat(
        json.dumps({"agent": "cb", "message": "summarize this in one line"})
    ))
    assert r["exit_code"] == 0
    assert r["agent"] == "cb"
    assert "ECHO from cb" in r["response"]
    assert r["duration"] == 0.4


def test_tla_chat_handles_agent_failure(monkeypatch):
    """If the agent CLI exits non-zero, tla_chat surfaces that."""
    from src import odysseus
    def fake_run_agent(agent, prompt, cwd=None, timeout=180):
        return 1, "", "rate limit hit", 0.1
    monkeypatch.setattr(odysseus, "run_agent", fake_run_agent)

    r = asyncio.run(tool_implementations.do_tla_chat(
        json.dumps({"agent": "claude", "message": "do the thing"})
    ))
    assert r["exit_code"] == 1
    assert "rate limit hit" in r["stderr"]
