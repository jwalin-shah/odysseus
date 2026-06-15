"""Tests for src.intent_router.classify().

Parametrized checks across the main intent categories plus a
focused test for the WhatsApp contact-extraction patch path.
"""
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
            "show my LinkedIn DMs",
            {"platform": "linkedin", "action": "read"},
            id="linkedin-read-dms",
        ),
    ],
)
def test_classify(text, expected):
    result = classify(text)
    for key, value in expected.items():
        if isinstance(value, dict):
            assert key in result, f"Missing key {key!r} in result {result!r}"
            for sub_key, sub_value in value.items():
                assert result[key].get(sub_key) == sub_value, (
                    f"For input {text!r}, expected "
                    f"{key}.{sub_key}={sub_value!r}, "
                    f"got {result[key].get(sub_key)!r}"
                )
        else:
            assert result.get(key) == value, (
                f"For input {text!r}, expected {key}={value!r}, "
                f"got {result.get(key)!r}"
            )


def test_classify_whatsapp_with_contact_patch(monkeypatch):
    """Once the contact resolver is patched, the WhatsApp intent
    should surface the contact name alongside the platform."""
    from src import intent_router

    def fake_resolve_contact(text):
        return "Sarah" if "Sarah" in text else None

    monkeypatch.setattr(
        intent_router, "resolve_contact", fake_resolve_contact
    )

    result = classify("what did Sarah say on WhatsApp")
    assert result["platform"] == "whatsapp"
    assert result.get("contact") == "Sarah"
