"""Parametrized tests for ``src.intent_router.classify()``.

These tests exercise the intent router across the most common surface
areas: platform detection, action verb, contact extraction, and basic
time-info parsing.  Each case asserts only the fields that the spec
calls out, so changes to unrelated fields (e.g. confidence scores) do
not break the suite.
"""

from __future__ import annotations

import pytest

from src.intent_router import classify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(intent, key, default=None):
    """Return ``intent[key]`` whether ``intent`` is a dict or an object."""
    if intent is None:
        return default
    if isinstance(intent, dict):
        return intent.get(key, default)
    return getattr(intent, key, default)


def _time_day(intent):
    """Return ``intent.time_info.day`` for either a dict- or object-style result."""
    time_info = _get(intent, "time_info")
    if time_info is None:
        return None
    if isinstance(time_info, dict):
        return time_info.get("day")
    return getattr(time_info, "day", None)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

_CASES = [
    pytest.param(
        "reply to mom's text",
        {"platform": "imessage", "action": "reply", "contact": "mom"},
        id="reply-to-mom-text-imessage",
    ),
    pytest.param(
        "send email to John about the deal",
        {"platform": "gmail", "contact": "John"},
        id="email-john-gmail",
    ),
    pytest.param(
        "add meeting Tuesday 3pm",
        {"platform": "calendar", "action": "create", "time_day": "Tuesday"},
        id="add-meeting-tuesday-3pm-calendar",
    ),
    pytest.param(
        "fix bug in auth.py",
        {"platform": "code"},
        id="fix-bug-auth-py-code",
    ),
    pytest.param(
        "what did Sarah say on WhatsApp",
        {"platform": "whatsapp", "contact": "Sarah"},
        id="whatsapp-sarah-say-pending-patch",
        # The contact extractor for WhatsApp requires an upstream patch.
        # ``strict=True`` so the test fails (XPASS) once the patch lands
        # and this mark must be removed.
        marks=pytest.mark.xfail(
            reason="WhatsApp contact extraction requires upstream patch",
            strict=True,
        ),
    ),
    pytest.param(
        "show my LinkedIn DMs",
        {"platform": "linkedin", "action": "read"},
        id="show-linkedin-dms-read",
    ),
]


@pytest.mark.parametrize("text, expected", _CASES)
def test_classify_matches_expected(text, expected):
    """``classify(text)`` should return an intent matching ``expected``."""
    intent = classify(text)

    # The router must always produce *something* for a known input.
    assert intent is not None, f"classify({text!r}) returned None"

    # --- platform (always required) -------------------------------------
    assert _get(intent, "platform") == expected["platform"], (
        f"platform mismatch for {text!r}: "
        f"expected {expected['platform']!r}, got {_get(intent, 'platform')!r}"
    )

    # --- optional fields ------------------------------------------------
    if "action" in expected:
        assert _get(intent, "action") == expected["action"], (
            f"action mismatch for {text!r}: "
            f"expected {expected['action']!r}, got {_get(intent, 'action')!r}"
        )

    if "contact" in expected:
        assert _get(intent, "contact") == expected["contact"], (
            f"contact mismatch for {text!r}: "
            f"expected {expected['contact']!r}, got {_get(intent, 'contact')!r}"
        )

    if "time_day" in expected:
        assert _time_day(intent) == expected["time_day"], (
            f"time_info.day mismatch for {text!r}: "
            f"expected {expected['time_day']!r}, got {_time_day(intent)!r}"
        )


@pytest.mark.parametrize("text, expected", _CASES)
def test_classify_platform_is_string(text, expected):
    """Platform should be a non-empty string for every supported input."""
    intent = classify(text)
    platform = _get(intent, "platform")
    assert isinstance(platform, str) and platform, (
        f"platform should be a non-empty string for {text!r}, got {platform!r}"
    )
