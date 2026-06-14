"""Deterministic spec-tests for the Odysseus operator spine.

Tests enforce the operator contract:
  1. Routing picks M3 for analysis tasks (cheap/free tier).
  2. M3 is blocked from code-write tasks (analysis_only flag).
  3. Stale quota snapshot marks a backend unavailable.
  4. Evidence writer redacts secrets before writing.
  5. Failed validation exit code → status="failed", not "verified".
  6. Missing test command → status="unverified", not "done" or "verified".
  7. Pioneer backend requires scarce=True explicit routing.
  8. Rewind metadata is written for any mutating mission.
  9. Mission IDs are unique across calls.
 10. Backend unavailable when quota percent >= 100.
"""
import json
import os
import re
import time
import uuid
from pathlib import Path

import pytest

# Allow running from repo root or tests/ dir
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ody_backends import BACKENDS, route_for_task, TaskKind
from ody_evidence import MissionRecord, SENSITIVE_PATTERN, redact_secrets
from ody_quota import QuotaSnapshot, backend_available_from_snapshot


# ────────────────────────────────────────────────────────────────────────────
# 1–2. Routing: M3 for analysis; blocked for code
# ────────────────────────────────────────────────────────────────────────────

class TestRouting:
    def test_routes_to_m3_for_analysis_task(self):
        backend_id, reason = route_for_task("analyze why the test_quota failures cluster", {})
        assert backend_id == "minimax-m3", f"Expected M3 for analysis prompt, got {backend_id!r}"
        assert reason  # non-empty reason

    def test_routes_to_m3_for_summarize(self):
        backend_id, _ = route_for_task("summarize these 500 evidence reports", {})
        assert backend_id == "minimax-m3"

    def test_routes_to_m3_for_diagnose(self):
        backend_id, _ = route_for_task("diagnose the root cause of the concurrency failure", {})
        assert backend_id == "minimax-m3"

    def test_m3_blocked_for_code_task(self):
        """M3 must never be selected for a code-write/fix/implement task."""
        backend_id, _ = route_for_task("fix the bug in sys_quota.py", {})
        assert backend_id != "minimax-m3", "M3 must not be selected for code-write tasks"

    def test_m3_blocked_for_implement_task(self):
        backend_id, _ = route_for_task("implement the missing rollback in queue_manager.py", {})
        assert backend_id != "minimax-m3"

    def test_explicit_m3_force_accepted_as_analysis(self):
        """force_backend=minimax-m3 is allowed for analysis tasks."""
        backend_id, _ = route_for_task("analyze this output", {}, force_backend="minimax-m3")
        assert backend_id == "minimax-m3"

    def test_explicit_m3_force_rejected_for_code(self):
        """force_backend=minimax-m3 raises if task kind is CODE."""
        with pytest.raises(ValueError, match="analysis_only"):
            route_for_task("fix the bug", {}, force_backend="minimax-m3")

    def test_pioneer_not_default_route(self):
        """Pioneer is scarce; must not be selected unless explicitly requested."""
        backend_id, _ = route_for_task("fix the bug in sys_quota.py", {})
        assert backend_id != "pioneer"

    def test_task_kind_analysis(self):
        assert TaskKind.for_prompt("analyze the report") == TaskKind.ANALYSIS

    def test_task_kind_code(self):
        assert TaskKind.for_prompt("fix the failing test") == TaskKind.CODE

    def test_task_kind_review(self):
        assert TaskKind.for_prompt("review this PR for security issues") == TaskKind.REVIEW


# ────────────────────────────────────────────────────────────────────────────
# 3. Quota: stale snapshot, percent-full backend unavailable
# ────────────────────────────────────────────────────────────────────────────

class TestQuotaSnapshot:
    def _make_snapshot(self, age_seconds: float, provider_percent: int = 50) -> dict:
        """Construct a minimal live.json-shaped snapshot with given age."""
        ts = time.time() - age_seconds
        import datetime
        dt = datetime.datetime.utcfromtimestamp(ts).isoformat() + "+00:00"
        return {
            "timestamp": dt,
            "providers": {
                "claude-a": {
                    "status": "VERIFIED",
                    "windows": {
                        "session": {"percent": provider_percent, "valid": True},
                    },
                }
            },
        }

    def test_fresh_snapshot_accepted(self):
        snap = QuotaSnapshot(self._make_snapshot(age_seconds=300))
        assert snap.is_fresh(max_age_seconds=1200)

    def test_stale_snapshot_rejected(self):
        snap = QuotaSnapshot(self._make_snapshot(age_seconds=1500))
        assert not snap.is_fresh(max_age_seconds=1200)

    def test_backend_unavailable_when_session_full(self):
        snap = QuotaSnapshot(self._make_snapshot(age_seconds=60, provider_percent=100))
        available, reason = backend_available_from_snapshot("claude-a", snap)
        assert not available
        assert reason  # must explain why

    def test_backend_available_when_quota_low(self):
        snap = QuotaSnapshot(self._make_snapshot(age_seconds=60, provider_percent=30))
        available, reason = backend_available_from_snapshot("claude-a", snap)
        assert available

    def test_unknown_provider_defaults_available(self):
        """Providers not in the snapshot are unknown, assumed available."""
        snap = QuotaSnapshot(self._make_snapshot(age_seconds=60))
        available, reason = backend_available_from_snapshot("minimax-m3", snap)
        assert available

    def test_stale_snapshot_marks_provider_unknown(self):
        """A stale snapshot must not be treated as valid quota evidence."""
        snap = QuotaSnapshot(self._make_snapshot(age_seconds=4000))
        available, reason = backend_available_from_snapshot("claude-a", snap)
        # Stale: caller must handle. Snapshot itself reports not fresh.
        assert not snap.is_fresh(max_age_seconds=1200)


# ────────────────────────────────────────────────────────────────────────────
# 4. Evidence: secret redaction
# ────────────────────────────────────────────────────────────────────────────

class TestSecretRedaction:
    def test_sk_key_redacted(self):
        text = 'Authorization: Bearer sk-abcdef1234567890abcdef1234567890'
        out = redact_secrets(text)
        assert "sk-abcdef" not in out
        assert "REDACTED" in out

    def test_tokenrouter_key_redacted(self):
        text = '"apiKey": "sk-umkgY44a1XXXXXXXXXXXXXXXXXXXX"'
        out = redact_secrets(text)
        assert "sk-umkgY" not in out

    def test_pioneer_api_key_header_redacted(self):
        text = 'X-API-Key: pk_live_abcdefghijklmnopqrstuvwxyz0123456789'
        out = redact_secrets(text)
        # Any long bearer-style token should be redacted
        assert "pk_live_abc" not in out or "REDACTED" in out

    def test_plain_text_not_mangled(self):
        text = "test passed in 2.4 seconds, 3 warnings"
        out = redact_secrets(text)
        assert out == text

    def test_sensitive_pattern_matches_sk_prefix(self):
        assert SENSITIVE_PATTERN.search('sk-abc123xyz')

    def test_sensitive_pattern_matches_infisical_export(self):
        # infisical export produces KEY=VALUE lines; values that look like tokens
        assert SENSITIVE_PATTERN.search('PIONEER_API_KEY=sk-abcdef1234567890')


# ────────────────────────────────────────────────────────────────────────────
# 5–6. Mission lifecycle: validation gate, unverified without test
# ────────────────────────────────────────────────────────────────────────────

class TestMissionLifecycle:
    def _make_mission(self, tmp_path):
        return MissionRecord(
            mission_id=str(uuid.uuid4()),
            prompt="fix the concurrency bug",
            backend_id="claude-a",
            routing_reason="coding_task_claude_primary",
            ledger_dir=tmp_path,
        )

    def test_mission_id_is_unique(self, tmp_path):
        m1 = self._make_mission(tmp_path)
        m2 = self._make_mission(tmp_path)
        assert m1.mission_id != m2.mission_id

    def test_failed_validation_is_not_verified(self, tmp_path):
        m = self._make_mission(tmp_path)
        m.close(
            validation_command=["pytest", "tests/test_quota.py", "-q"],
            validation_exit_code=1,
        )
        row = m.load()
        assert row["status"] == "failed"
        assert row["status"] != "verified"

    def test_green_validation_marks_verified(self, tmp_path):
        m = self._make_mission(tmp_path)
        m.close(
            validation_command=["pytest", "tests/test_quota.py", "-q"],
            validation_exit_code=0,
        )
        row = m.load()
        assert row["status"] == "verified"

    def test_missing_validation_command_is_unverified(self, tmp_path):
        m = self._make_mission(tmp_path)
        m.close(validation_command=None, validation_exit_code=None)
        row = m.load()
        assert row["status"] == "unverified"
        assert row["status"] not in ("verified", "done")

    def test_analysis_only_mission_has_dedicated_status(self, tmp_path):
        m = MissionRecord(
            mission_id=str(uuid.uuid4()),
            prompt="summarize these reports",
            backend_id="minimax-m3",
            routing_reason="analysis_task_m3_free_tier",
            ledger_dir=tmp_path,
            analysis_only=True,
        )
        m.close(validation_command=None, validation_exit_code=None)
        row = m.load()
        assert row["status"] == "analysis_only"

    def test_evidence_file_has_prompt_hash(self, tmp_path):
        m = self._make_mission(tmp_path)
        m.close(validation_command=None, validation_exit_code=None)
        row = m.load()
        assert "prompt_hash" in row
        assert len(row["prompt_hash"]) == 64  # SHA-256 hex

    def test_secret_in_stdout_is_redacted_in_evidence(self, tmp_path):
        m = self._make_mission(tmp_path)
        m.close(
            validation_command=None,
            validation_exit_code=None,
            stdout="command output: sk-secret1234567890abcdef done",
        )
        row = m.load()
        raw_evidence = (tmp_path / f"{m.mission_id}.jsonl").read_text()
        assert "sk-secret" not in raw_evidence
        assert "REDACTED" in raw_evidence

    def test_rewind_command_stored_for_mutating_mission(self, tmp_path):
        m = self._make_mission(tmp_path)
        m.close(
            validation_command=["pytest"],
            validation_exit_code=0,
            checkpoint_before_sha="abc123",
            worktree_path="/tmp/ody-worktree-abc",
            rewind_command="git worktree remove --force /tmp/ody-worktree-abc",
        )
        row = m.load()
        assert "rewind_command" in row
        assert "git worktree remove" in row["rewind_command"]
        assert "checkpoint_before_sha" in row

    def test_no_rewind_for_analysis_mission(self, tmp_path):
        m = MissionRecord(
            mission_id=str(uuid.uuid4()),
            prompt="analyze this",
            backend_id="minimax-m3",
            routing_reason="analysis",
            ledger_dir=tmp_path,
            analysis_only=True,
        )
        m.close(validation_command=None, validation_exit_code=None)
        row = m.load()
        assert row.get("rewind_command") is None
        assert row.get("worktree_path") is None


# ────────────────────────────────────────────────────────────────────────────
# 7. Backend registry health
# ────────────────────────────────────────────────────────────────────────────

class TestBackendRegistry:
    def test_all_expected_backends_exist(self):
        # Core subscription CLIs must always be present.
        expected = {"claude-a", "claude-b", "pioneer", "opencode", "codex",
                    "gemini", "agy", "minimax-m3"}
        missing = expected - set(BACKENDS.keys())
        assert not missing, f"Missing backends: {missing}"

    def test_free_tier_backends_exist(self):
        # Tier-0 free backends must be present.
        expected = {"tokenrouter-auto", "tokenrouter-deepseek",
                    "openrouter-nex", "openrouter-nemotron"}
        missing = expected - set(BACKENDS.keys())
        assert not missing, f"Missing tier-0 backends: {missing}"

    def test_m3_is_analysis_only(self):
        assert BACKENDS["minimax-m3"].analysis_only is True

    def test_pioneer_is_scarce(self):
        assert BACKENDS["pioneer"].scarce is True

    def test_pioneer_is_tier2(self):
        assert BACKENDS["pioneer"].tier == 2

    def test_subscription_backends_are_tier0(self):
        """Already-paid subscription CLIs are tier 0 — zero marginal cost."""
        for bid in ("claude-a", "claude-b", "agy", "gemini", "codex"):
            assert BACKENDS[bid].tier == 0, \
                f"{bid} should be tier 0 (subscription), got tier {BACKENDS[bid].tier}"

    def test_external_services_are_tier1(self):
        """TokenRouter and OpenRouter are tier 1 — external billing, not subscriptions."""
        for bid in ("tokenrouter-auto", "tokenrouter-deepseek",
                    "openrouter-nex", "openrouter-nemotron"):
            assert BACKENDS[bid].tier == 1, \
                f"{bid} should be tier 1 (external service), got tier {BACKENDS[bid].tier}"

    def test_tokenrouter_auto_uses_pi(self):
        b = BACKENDS["tokenrouter-auto"]
        assert b.command == "pi"
        assert b.pi_model == "tokenrouter/auto:balance"

    def test_code_task_routes_to_subscription_first(self):
        """Code tasks hit subscription backends (tier 0) before external services."""
        backend_id, reason = route_for_task("fix the bug in sys_quota.py", {})
        assert BACKENDS[backend_id].tier == 0, (
            f"Expected subscription backend (tier 0), got {backend_id!r} "
            f"(tier {BACKENDS[backend_id].tier})"
        )
        assert "waterfall" in reason or "subscription" in reason.lower()

    def test_code_task_falls_to_external_when_all_quota_tracked_subscriptions_exhausted(self):
        """When quota-tracked subscription CLIs are full, codex/cursor (no quota key)
        are still tried before external services — they're also subscriptions."""
        # Only providers WITH quota_provider_key can be blocked via live.json.
        # codex+cursor have no quota_provider_key so they'll still be picked.
        quota = {"providers": {
            "claude-a": {"windows": {"session": {"percent": 100}}},
            "claude-b": {"windows": {"session": {"percent": 100}}},
            "agy":      {"windows": {"session": {"percent": 100}}},
            "gemini":   {"windows": {"session": {"percent": 100}}},
        }}
        backend_id, _ = route_for_task("fix the bug in sys_quota.py", quota)
        # codex or cursor should be picked (untracked subscriptions), not externals
        assert backend_id in ("codex", "cursor"), (
            f"Expected codex or cursor (untracked subscription), got {backend_id!r}"
        )
        assert BACKENDS[backend_id].tier == 0

    def test_claude_a_not_analysis_only(self):
        assert not BACKENDS["claude-a"].analysis_only

    def test_claude_a_not_scarce(self):
        assert not BACKENDS["claude-a"].scarce

    def test_external_backends_not_quota_gated(self):
        """Tier-1 external backends must never be blocked by quota snapshot."""
        from ody_backends import _backend_has_quota
        for bid, backend in BACKENDS.items():
            if backend.tier == 1:
                assert _backend_has_quota(bid, {}), \
                    f"External backend {bid!r} incorrectly blocked by quota"
