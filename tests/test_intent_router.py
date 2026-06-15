"""Parametrized tests for ``src.intent_router.classify``.

The router turns a free-form natural-language command into a structured
intent object exposing at least:

* ``platform``  – the destination service (e.g. ``"gmail"``, ``"imessage"``).
* ``action``    – what to do there (``"reply"``, ``"read"``, ``"create"``…).
* ``contact``   – the person involved, if any.
* ``time_info`` – a sub-object with parsed temporal details for calendar
                  commands (``day``, ``hour`` …).

Note: the WhatsApp case documents an expected behaviour that requires the
classification patch to be applied — it will fail on the un-patched router
and pass once the fix lands.
"""
import pytest

from src.intent_router import classify


# ---------------------------------------------------------------------------
# Plain platform / action / contact assertions
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param(
            "reply to mom's text",
            {"platform": "imessage", "action": "reply", "contact": "mom"},
            id="imessage-reply-mom",
        ),
        pytest.param(
            "send email to John about the deal",
            {"platform": "gmail", "contact": "John"},
            id="gmail-email-john",
        ),
        pytest.param(
            "fix bug in auth.py",
            {"platform": "code"},
            id="code-fix-authpy",
        ),
        pytest.param(
            "what did Sarah say on WhatsApp",
            {"platform": "whatsapp", "contact": "Sarah"},
            id="whatsapp-read-sarah",
        ),
        pytest.param(
            "show my LinkedIn DMs",
            {"platform": "linkedin", "action": "read"},
            id="linkedin-read-dms",
        ),
    ],
)
def test_classify_top_level_fields(text, expected):
    result = classify(text)
    for attr, value in expected.items():
        actual = getattr(result, attr, None)
        assert actual == value, (
            f"classify({text!r}): expected {attr}={value!r}, got {actual!r}"
        )


# ---------------------------------------------------------------------------
# Calendar command: time_info.day is parsed
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, expected_platform, expected_action, expected_day",
    [
        pytest.param(
            "add meeting Tuesday 3pm",
            "calendar",
            "create",
            "tuesday",
            id="calendar-create-tuesday-3pm",
        ),
    ],
)
def test_classify_calendar_time_info(text, expected_platform, expected_action, expected_day):
    result = classify(text)
    assert result.platform == expected_platform
    assert result.action == expected_action
    assert result.time_info is not None, "time_info must be populated for a calendar command"
    assert getattr(result.time_info, "day", "").lower() == expected_day
