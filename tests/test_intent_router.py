"""Tests for src.intent_router.classify()."""
import pytest

from src.intent_router import classify


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
            "add meeting Tuesday 3pm",
            {
                "platform": "calendar",
                "action": "create",
                "time_info": {"day": "Tuesday"},
            },
            id="calendar-create-tuesday",
        ),
        pytest.param(
            "fix bug in auth.py",
            {"platform": "code"},
            id="code-fix-bug",
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
def test_classify(text, expected):
    """classify() should extract the correct platform/action/contact fields."""
    result = classify(text)

    for key, expected_value in expected.items():
        actual_value = result[key]
        assert actual_value == expected_value, (
            f"For input {text!r}: "
            f"expected {key}={expected_value!r}, got {actual_value!r}"
        )
