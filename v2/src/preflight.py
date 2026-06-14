"""preflight: pre-flight gate for Odysseus mission dispatch.

F3 from FABLE_BLUEPRINT.md: pre-flight + idempotency.

check(prompt, backend_id, ledger, quota_state=None) -> PreflightResult

Three gates, evaluated in order:
  1. quota      — backend session quota >= 100% → block
  2. halt       — prompt matches known halt/refusal patterns → block
  3. duplicate  — task_hash already in ledger with non-failed outcome → block

Raises PreflightBlocked on any blocked gate.
Returns PreflightResult(allowed=True, task_hash=...) on pass.

This module is dependency-free within the Odysseus stack — it does not
import ody_backends, ody_quota, or anything with external side effects.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────────
# Result / exception types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PreflightResult:
    allowed: bool
    task_hash: str


class PreflightBlocked(Exception):
    """Raised when a mission is blocked by pre-flight checks.

    Attributes
    ----------
    gate:          Which gate blocked: "quota" | "halt" | "duplicate"
    reason:        Human-readable explanation.
    prior_outcome: For gate="duplicate", the outcome from the ledger row.
    """
    def __init__(self, gate: str, reason: str, prior_outcome: Optional[str] = None):
        super().__init__(reason)
        self.gate = gate
        self.reason = reason
        self.prior_outcome = prior_outcome


# ─────────────────────────────────────────────────────────────────────────────
# Task hash
# ─────────────────────────────────────────────────────────────────────────────

def compute_task_hash(prompt: str, backend_id: str) -> str:
    """SHA-256 of (prompt + backend_id). 64 hex chars."""
    raw = f"{prompt}\x00{backend_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Gate 1: quota
# ─────────────────────────────────────────────────────────────────────────────

def _check_quota(backend_id: str, quota_state: Optional[dict]) -> None:
    """Raise PreflightBlocked(gate='quota') if backend session is exhausted."""
    if not quota_state:
        return  # no snapshot — skip check
    providers = quota_state.get("providers", {})
    info = providers.get(backend_id, {})
    if not info:
        return  # unknown backend in snapshot → assume available
    session = info.get("windows", {}).get("session", {})
    percent = session.get("percent", 0)
    if percent >= 100:
        raise PreflightBlocked(
            gate="quota",
            reason=(
                f"Backend {backend_id!r} session quota is exhausted "
                f"({percent}%). Choose a different backend or wait for reset."
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Gate 2: halt-message loop detection
# ─────────────────────────────────────────────────────────────────────────────

# Patterns that indicate a prompt is actually a recycled agent refusal/halt.
# Ordered by specificity — most specific first.
_HALT_PATTERNS = [
    re.compile(r"Bypass Attempt #\d+", re.IGNORECASE),
    re.compile(
        r"^(I cannot|I will not|I'm not able|As an AI|I must decline|"
        r"I am not able|I am unable)\b",
        re.IGNORECASE | re.MULTILINE,
    ),
    re.compile(
        r"\b(violates my content policy|ethical constraints|inappropriate request|"
        r"not able to assist with this|cannot comply with|cannot assist with this)\b",
        re.IGNORECASE,
    ),
]


def _check_halt(prompt: str) -> None:
    """Raise PreflightBlocked(gate='halt') if prompt is a recycled refusal."""
    for pattern in _HALT_PATTERNS:
        if pattern.search(prompt):
            raise PreflightBlocked(
                gate="halt",
                reason=(
                    f"Prompt matches halt/refusal pattern — looks like a recycled "
                    f"agent refusal being re-dispatched as a new mission. "
                    f"Pattern: {pattern.pattern!r}"
                ),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Gate 3: duplicate workpack
# ─────────────────────────────────────────────────────────────────────────────

# Outcomes that mean "this workpack already ran and we shouldn't retry"
_BLOCKING_OUTCOMES = frozenset({"verified", "unverified", "analysis_only"})


def _check_duplicate(task_hash: str, ledger: list[dict]) -> None:
    """Raise PreflightBlocked(gate='duplicate') if task_hash already landed."""
    for row in ledger:
        if row.get("task_hash") == task_hash:
            outcome = row.get("outcome", "unknown")
            if outcome in _BLOCKING_OUTCOMES:
                raise PreflightBlocked(
                    gate="duplicate",
                    reason=(
                        f"duplicate: task hash {task_hash[:16]}… already exists "
                        f"in ledger with outcome={outcome!r}. Not re-dispatching."
                    ),
                    prior_outcome=outcome,
                )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def check(
    prompt: str,
    backend_id: str,
    ledger: list[dict],
    quota_state: Optional[dict] = None,
) -> PreflightResult:
    """Run all pre-flight gates and return PreflightResult if all pass.

    Gates are evaluated cheapest-first:
      quota → halt → duplicate

    Raises PreflightBlocked if any gate fails.
    """
    # Gate 1: quota (fast dict lookup)
    _check_quota(backend_id, quota_state)

    # Gate 2: halt patterns (regex, no I/O)
    _check_halt(prompt)

    # Gate 3: duplicate (ledger scan)
    task_hash = compute_task_hash(prompt, backend_id)
    _check_duplicate(task_hash, ledger)

    return PreflightResult(allowed=True, task_hash=task_hash)
