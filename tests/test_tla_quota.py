"""Red-gate tests for do_tla_quota.

do_tla_quota must delegate to the canonical `/Users/jwalinshah/bin/quota --json`
binary (or a mock under test) and return a normalized shape. It must NOT
read .credit-lab/quota.db — that is the dispatch-internal budget, exposed
via do_list_missions / the feedback ledger.
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make src importable
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

import tool_implementations as ti


SAMPLE_QUOTA_JSON = {
    "as_of": "2026-06-12T20:00:00+00:00",
    "providers": {
        "pioneer": {
            "status": "VERIFIED",
            "used_credits": 1711.36,
            "limit_credits": 10000.0,
            "remaining_credits": 8288.64,
        },
        "codex": {
            "status": "VERIFIED",
            "primary_pct": 43,
            "secondary_pct": 100,
            "primary_reset_at": "2026-06-12T22:35:41+00:00",
        },
        "agy": {
            "status": "VERIFIED",
            "models": {
                "Gemini": {"weekly_pct": 70, "five_hour_pct": 87},
                "Claude": {"weekly_pct": None, "five_hour_pct": 10},
            },
        },
    },
}


class _FakeProc:
    def __init__(self, rc=0, stdout=b"", stderr=b""):
        self.returncode = rc
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


def _fake_exec_factory(payload=None, rc=0, stderr=b""):
    """Build a fake asyncio.create_subprocess_exec that returns our payload."""
    if payload is None:
        payload = SAMPLE_QUOTA_JSON
    out = json.dumps(payload).encode()
    fake = _FakeProc(rc=rc, stdout=out, stderr=stderr)

    async def fake_exec(*args, **kwargs):
        return fake
    return fake_exec


def test_tla_quota_returns_all_providers():
    async def run():
        with patch("asyncio.create_subprocess_exec",
                   side_effect=_fake_exec_factory()):
            r = await ti.do_tla_quota("{}")
        assert r["exit_code"] == 0
        assert r["as_of"] == SAMPLE_QUOTA_JSON["as_of"]
        assert set(r["quota"]) == {"pioneer", "codex", "agy"}
    asyncio.run(run())


def test_tla_quota_filters_to_single_agent():
    async def run():
        with patch("asyncio.create_subprocess_exec",
                   side_effect=_fake_exec_factory()):
            r = await ti.do_tla_quota('{"agent": "codex"}')
        assert r["exit_code"] == 0
        assert list(r["quota"]) == ["codex"]
        assert r["quota"]["codex"]["primary_pct"] == 43
    asyncio.run(run())


def test_tla_quota_rejects_unknown_agent_with_actionable_error():
    async def run():
        with patch("asyncio.create_subprocess_exec",
                   side_effect=_fake_exec_factory()):
            r = await ti.do_tla_quota('{"agent": "bogus"}')
        assert r["exit_code"] == 1
        assert "bogus" in r["error"]
        # error should list known agents so the caller can self-correct
        assert "pioneer" in r["error"]
        assert "codex" in r["error"]
    asyncio.run(run())


def test_tla_quota_handles_binary_failure():
    async def run():
        fake = _FakeProc(rc=1, stderr=b"oops quota crashed")
        async def fake_exec(*a, **kw): return fake
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            r = await ti.do_tla_quota("{}")
        assert r["exit_code"] == 1
        assert "oops quota crashed" in r["error"]
    asyncio.run(run())


def test_tla_quota_handles_invalid_json_output():
    async def run():
        fake = _FakeProc(rc=0, stdout=b"not json {")
        async def fake_exec(*a, **kw): return fake
        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            r = await ti.do_tla_quota("{}")
        assert r["exit_code"] == 1
        assert "parse" in r["error"].lower()
    asyncio.run(run())


def test_tla_quota_does_not_read_credit_lab_db(tmp_path, monkeypatch):
    """The function must NOT touch .credit-lab/quota.db."""
    fake_db = tmp_path / "quota.db"
    fake_db.write_text("this is not a real db")
    monkeypatch.setenv("ODY_QUOTA_BIN", "/nonexistent/quota-binary")
    async def run():
        r = await ti.do_tla_quota("{}")
        # The binary doesn't exist, so the function must return a clean
        # 'binary not found' error without ever opening the fake db.
        assert r["exit_code"] == 1
        assert "not found" in r["error"]
        # And the fake db must not have been touched
        assert "this is not a real db" in fake_db.read_text()
    asyncio.run(run())


def test_tla_quota_agy_uses_new_weekly_five_hour_schema():
    """agy responses must come through with the new {weekly_pct, five_hour_pct}
    schema intact, not collapsed to the old available_pct field."""
    async def run():
        with patch("asyncio.create_subprocess_exec",
                   side_effect=_fake_exec_factory()):
            r = await ti.do_tla_quota('{"agent": "agy"}')
        agy = r["quota"]["agy"]
        assert agy["status"] == "VERIFIED"
        gem = agy["models"]["Gemini"]
        assert gem["weekly_pct"] == 70
        assert gem["five_hour_pct"] == 87
    asyncio.run(run())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
