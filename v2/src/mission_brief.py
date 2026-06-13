"""mission_brief: validation gate for M3-generated mission queue entries.

M3 extracts failure patterns from bg-fleet evidence and generates briefs.
Not every brief is worth executing — briefs with missing target files, no
proposed fix, or no test command waste ody runs and inflate wrong-file /
malformed-diff / test-never-ran failure counts further.

validate(brief) -> MissionValidated
  raises MissionInvalid on any blocked field.

Five required fields (derived from M3 top failure modes):
  affected_files  — non-empty list of non-empty path strings  (wrong-file)
  proposed_fix    — non-empty string                           (malformed-diff)
  proposed_test   — non-empty string                           (test-never-ran)
  mission_prompt  — non-empty string                           (executor input)
  confidence      — float in (0.0, 1.0]                        (noise filter)

Dependency-free: no imports from the rest of the Odysseus stack.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Result / exception types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MissionValidated:
    valid: bool
    brief: dict


class MissionInvalid(Exception):
    """Raised when a mission brief fails validation.

    Attributes
    ----------
    field:  Name of the field that caused the failure.
    reason: Human-readable explanation.
    """
    def __init__(self, field: str, reason: str) -> None:
        super().__init__(reason)
        self.field = field
        self.reason = reason


# ─────────────────────────────────────────────────────────────────────────────
# Field validators
# ─────────────────────────────────────────────────────────────────────────────

def _require_nonempty_string(brief: dict, field: str) -> None:
    val = brief.get(field)
    if not isinstance(val, str) or not val.strip():
        raise MissionInvalid(
            field=field,
            reason=(
                f"Brief is missing or empty for required field {field!r}. "
                f"Got: {val!r}"
            ),
        )


def _require_file_list(brief: dict, field: str = "affected_files") -> None:
    val = brief.get(field)
    if not isinstance(val, list) or not val:
        raise MissionInvalid(
            field=field,
            reason=(
                f"Brief must have a non-empty list for {field!r}. "
                f"Got: {val!r}"
            ),
        )
    for item in val:
        if not isinstance(item, str) or not item.strip():
            raise MissionInvalid(
                field=field,
                reason=(
                    f"{field!r} contains an empty or non-string entry: {item!r}. "
                    f"Every entry must be a non-empty file path."
                ),
            )


def _require_confidence(brief: dict) -> None:
    val = brief.get("confidence")
    if val is None:
        raise MissionInvalid(
            field="confidence",
            reason="Brief is missing required field 'confidence'.",
        )
    try:
        f = float(val)
    except (TypeError, ValueError):
        raise MissionInvalid(
            field="confidence",
            reason=f"'confidence' must be numeric. Got: {val!r}",
        )
    if not (0.0 < f <= 1.0):
        raise MissionInvalid(
            field="confidence",
            reason=(
                f"'confidence' must be in (0.0, 1.0]. Got: {f}. "
                f"Zero-confidence briefs are noise; >1.0 is invalid."
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def validate(brief: dict) -> MissionValidated:
    """Validate a mission brief before ody execution.

    Gates are evaluated in order — all must pass:
      1. affected_files  (non-empty list of paths)
      2. proposed_fix    (non-empty string)
      3. proposed_test   (non-empty string)
      4. mission_prompt  (non-empty string)
      5. confidence      (float in (0.0, 1.0])

    Returns MissionValidated(valid=True, brief=brief) on pass.
    Raises MissionInvalid with .field and .reason on any failure.
    """
    _require_file_list(brief, "affected_files")
    _require_nonempty_string(brief, "proposed_fix")
    _require_nonempty_string(brief, "proposed_test")
    _require_nonempty_string(brief, "mission_prompt")
    _require_confidence(brief)
    return MissionValidated(valid=True, brief=brief)
