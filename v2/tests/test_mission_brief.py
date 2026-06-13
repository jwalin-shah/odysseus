"""Adversarial spec-tests for mission_brief.validate().

M3 evidence: top failure modes are wrong-file, malformed-diff, test-never-ran.
These map directly to briefs that are missing target files, fix instructions,
or validation commands.

validate(brief) -> MissionValidated
  raises MissionInvalid on any block.

Three required fields:
  1. affected_files   — at least one path, all non-empty strings (wrong-file defence)
  2. proposed_fix     — non-empty string (malformed-diff defence)
  3. proposed_test    — non-empty string (test-never-ran defence)

Additional checks:
  4. mission_prompt   — non-empty string (executor has something to run with)
  5. confidence       — 0 < float <= 1.0 (briefs with zero confidence are noise)

All tests must FAIL before mission_brief.py exists,
and PASS after the correct implementation ships.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mission_brief import validate, MissionValidated, MissionInvalid

# ── helpers ───────────────────────────────────────────────────────────────────

def _good() -> dict:
    """Return a minimal valid brief."""
    return {
        "affected_files": ["v2/src/sys_quota.py"],
        "proposed_fix": "Add the missing early-return when quota is None.",
        "proposed_test": "pytest -q v2/tests/test_quota.py::TestQuotaEnforcement",
        "mission_prompt": "Fix the quota check in sys_quota.py so it returns early when quota_state is None.",
        "confidence": 0.85,
        "failure_mode": "test-never-ran",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. Happy path
# ─────────────────────────────────────────────────────────────────────────────

class TestHappyPath:
    def test_valid_brief_passes(self):
        result = validate(_good())
        assert isinstance(result, MissionValidated)
        assert result.valid is True

    def test_validated_carries_brief(self):
        brief = _good()
        result = validate(brief)
        assert result.brief is brief

    def test_multiple_affected_files_passes(self):
        b = _good()
        b["affected_files"] = ["v2/src/a.py", "v2/src/b.py", "v2/tests/test_a.py"]
        result = validate(b)
        assert result.valid is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. affected_files — wrong-file defence
# ─────────────────────────────────────────────────────────────────────────────

class TestAffectedFiles:
    def test_missing_key_blocked(self):
        b = _good()
        del b["affected_files"]
        with pytest.raises(MissionInvalid, match="affected_files"):
            validate(b)

    def test_empty_list_blocked(self):
        b = _good()
        b["affected_files"] = []
        with pytest.raises(MissionInvalid, match="affected_files"):
            validate(b)

    def test_none_blocked(self):
        b = _good()
        b["affected_files"] = None
        with pytest.raises(MissionInvalid, match="affected_files"):
            validate(b)

    def test_list_with_empty_string_blocked(self):
        b = _good()
        b["affected_files"] = [""]
        with pytest.raises(MissionInvalid, match="affected_files"):
            validate(b)

    def test_list_with_blank_string_blocked(self):
        b = _good()
        b["affected_files"] = ["   "]
        with pytest.raises(MissionInvalid, match="affected_files"):
            validate(b)

    def test_non_list_string_blocked(self):
        b = _good()
        b["affected_files"] = "v2/src/sys_quota.py"  # string, not list
        with pytest.raises(MissionInvalid, match="affected_files"):
            validate(b)

    def test_mixed_valid_empty_blocked(self):
        b = _good()
        b["affected_files"] = ["v2/src/a.py", ""]
        with pytest.raises(MissionInvalid, match="affected_files"):
            validate(b)


# ─────────────────────────────────────────────────────────────────────────────
# 3. proposed_fix — malformed-diff defence
# ─────────────────────────────────────────────────────────────────────────────

class TestProposedFix:
    def test_missing_key_blocked(self):
        b = _good()
        del b["proposed_fix"]
        with pytest.raises(MissionInvalid, match="proposed_fix"):
            validate(b)

    def test_empty_string_blocked(self):
        b = _good()
        b["proposed_fix"] = ""
        with pytest.raises(MissionInvalid, match="proposed_fix"):
            validate(b)

    def test_whitespace_only_blocked(self):
        b = _good()
        b["proposed_fix"] = "   \n  "
        with pytest.raises(MissionInvalid, match="proposed_fix"):
            validate(b)

    def test_none_blocked(self):
        b = _good()
        b["proposed_fix"] = None
        with pytest.raises(MissionInvalid, match="proposed_fix"):
            validate(b)


# ─────────────────────────────────────────────────────────────────────────────
# 4. proposed_test — test-never-ran defence
# ─────────────────────────────────────────────────────────────────────────────

class TestProposedTestCommand:
    def test_missing_key_blocked(self):
        b = _good()
        del b["proposed_test"]
        with pytest.raises(MissionInvalid, match="proposed_test"):
            validate(b)

    def test_empty_string_blocked(self):
        b = _good()
        b["proposed_test"] = ""
        with pytest.raises(MissionInvalid, match="proposed_test"):
            validate(b)

    def test_whitespace_only_blocked(self):
        b = _good()
        b["proposed_test"] = "\t"
        with pytest.raises(MissionInvalid, match="proposed_test"):
            validate(b)

    def test_none_blocked(self):
        b = _good()
        b["proposed_test"] = None
        with pytest.raises(MissionInvalid, match="proposed_test"):
            validate(b)


# ─────────────────────────────────────────────────────────────────────────────
# 5. mission_prompt — executor needs something to act on
# ─────────────────────────────────────────────────────────────────────────────

class TestMissionPrompt:
    def test_missing_key_blocked(self):
        b = _good()
        del b["mission_prompt"]
        with pytest.raises(MissionInvalid, match="mission_prompt"):
            validate(b)

    def test_empty_string_blocked(self):
        b = _good()
        b["mission_prompt"] = ""
        with pytest.raises(MissionInvalid, match="mission_prompt"):
            validate(b)

    def test_none_blocked(self):
        b = _good()
        b["mission_prompt"] = None
        with pytest.raises(MissionInvalid, match="mission_prompt"):
            validate(b)


# ─────────────────────────────────────────────────────────────────────────────
# 6. confidence — noise filter
# ─────────────────────────────────────────────────────────────────────────────

class TestConfidence:
    def test_zero_confidence_blocked(self):
        b = _good()
        b["confidence"] = 0.0
        with pytest.raises(MissionInvalid, match="confidence"):
            validate(b)

    def test_negative_confidence_blocked(self):
        b = _good()
        b["confidence"] = -0.1
        with pytest.raises(MissionInvalid, match="confidence"):
            validate(b)

    def test_missing_confidence_blocked(self):
        b = _good()
        del b["confidence"]
        with pytest.raises(MissionInvalid, match="confidence"):
            validate(b)

    def test_none_confidence_blocked(self):
        b = _good()
        b["confidence"] = None
        with pytest.raises(MissionInvalid, match="confidence"):
            validate(b)

    def test_1_0_confidence_passes(self):
        b = _good()
        b["confidence"] = 1.0
        assert validate(b).valid is True

    def test_above_1_blocked(self):
        b = _good()
        b["confidence"] = 1.1
        with pytest.raises(MissionInvalid, match="confidence"):
            validate(b)

    def test_small_positive_passes(self):
        b = _good()
        b["confidence"] = 0.01
        assert validate(b).valid is True


# ─────────────────────────────────────────────────────────────────────────────
# 7. MissionInvalid carries field name
# ─────────────────────────────────────────────────────────────────────────────

class TestMissionInvalidDetails:
    def test_exception_has_field(self):
        b = _good()
        b["proposed_test"] = ""
        with pytest.raises(MissionInvalid) as exc_info:
            validate(b)
        assert exc_info.value.field == "proposed_test"

    def test_exception_has_reason(self):
        b = _good()
        del b["affected_files"]
        with pytest.raises(MissionInvalid) as exc_info:
            validate(b)
        assert exc_info.value.reason  # non-empty string
        assert exc_info.value.field == "affected_files"
