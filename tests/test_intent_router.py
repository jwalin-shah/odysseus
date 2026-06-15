"""Parametrized pytest tests for src.intent_router.classify().

These tests assert the *contract* of classify(): given a natural-language
utterance, it should return a structured intent with at minimum `platform`
and (where applicable) `action`, `contact`, and `time_info` fields.

`classify()` is treated as returning either a dict, a dataclass-like
object, or a namedtuple. The `_get` helper normalises nested access so
the assertions work regardless of the concrete return type.
"""

from __future__ import annotations

import pytest

from src.intent_router import classify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, *path):
    """Resolve a dotted path on either a dict or an attribute-bearing object.

    Returns None if any segment is missing. This lets a single test work
    whether classify() returns:
        {"platform": "imessage", ...}            # plain dict
        Intent(platform="imessage", ...)         # dataclass / SimpleNamespace
        Intent(platform=..., time_info=TimeInfo(day="Tuesday", ...))  # nested
    """
    cur = obj
    for key in path:
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param(
            "reply to mom's text",
            {
                "platform": "imessage",
                "action": "reply",
                "contact": "mom",
            },
            id="imessage-reply-to-mom",
        ),
        pytest.param(
            "send email to John about the deal",
            {
                "platform": "gmail",
                "contact": "John",
            },
            id="gmail-email-to-john",
        ),
        pytest.param(
            "add meeting Tuesday 3pm",
            {
                "platform": "calendar",
                "action": "create",
                "time_info.day": "Tuesday",
            },
            id="calendar-create-tuesday",
        ),
        pytest.param(
            "fix bug in auth.py",
            {
                "platform": "code",
            },
            id="code-fix-bug",
        ),
        pytest.param(
            # NOTE: this assertion depends on the contact-extraction patch
            # being applied. Until then, the test will fail — which is
            # the desired signal that the patch is still required.
            "what did Sarah say on WhatsApp",
            {
                "platform": "whatsapp",
                "contact": "Sarah",
            },
            id="whatsapp-read-sarah",
        ),
        pytest.param(
            "show my LinkedIn DMs",
            {
                "platform": "linkedin",
                "action": "read",
            },
            id="linkedin-read-dms",
        ),
    ],
)
def test_classify(text, expected):
    result = classify(text)

    assert result is not None, f"classify({text!r}) returned None"

    for dotted_key, expected_value in expected.items():
        path = tuple(dotted_key.split("."))
        actual = _get(result, *path)
        assert actual == expected_value, (
            f"classify({text!r}): expected {dotted_key}={expected_value!r}, "
            f"got {actual!r}"
        )


# ---------------------------------------------------------------------------
# Optional: assert that *unspecified* fields don't accidentally surface
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, must_be_none",
    [
        pytest.param(
            "fix bug in auth.py",
            ["contact", "time_info"],
            id="code-has-no-contact-or-time",
        ),
    ],
)
def test_classify_negative_fields(text, must_be_none):
    """Fields that don't apply to an intent should be absent/None."""
    result = classify(text)
    for key in must_be_none:
        assert _get(result, key) is None, (
            f"classify({text!r}): {key!r} should be None, got {_get(result, key)!r}"
        )
