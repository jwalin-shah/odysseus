"""Parametrized tests for src.intent_router.classify()."""
import pytest

from src.intent_router import classify


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "reply to mom's text",
            {
                "platform": "imessage",
                "action": "reply",
                "contact": "mom",
            },
        ),
        (
            "send email to John about the deal",
            {
                "platform": "gmail",
                "contact": "John",
            },
        ),
        (
            "add meeting Tuesday 3pm",
            {
                "platform": "calendar",
                "action": "create",
                "time_info": {"day": "Tuesday"},
            },
        ),
        (
            "fix bug in auth.py",
            {
                "platform": "code",
            },
        ),
        (
            "show my LinkedIn DMs",
            {
                "platform": "linkedin",
                "action": "read",
            },
        ),
    ],
    ids=[
        "imessage_reply_mom",
        "gmail_email_john",
        "calendar_create_tuesday",
        "code_fix_bug",
        "linkedin_read_dms",
    ],
)
def test_classify_expected_fields(text, expected):
    """classify() should return at least the expected fields for each input."""
    result = classify(text)

    assert isinstance(result, dict), f"classify() must return a dict, got {type(result)!r}"

    for key, value in expected.items():
        assert key in result, f"Missing key {key!r} in result {result!r}"

        if key == "time_info":
            assert isinstance(result[key], dict), (
                f"time_info must be a dict, got {type(result[key])!r}"
            )
            assert result[key].get("day") == value["day"], (
                f"Expected time_info.day == {value['day']!r}, "
                f"got {result[key].get('day')!r}"
            )
        else:
            assert result[key] == value, (
                f"Expected {key} == {value!r}, got {result.get(key)!r}"
            )


@pytest.mark.xfail(
    reason="WhatsApp platform detection pending upstream patch",
    strict=False,
)
def test_classify_whatsapp_sarah():
    """Pending patch: classify() should detect WhatsApp and extract contact 'Sarah'."""
    result = classify("what did Sarah say on WhatsApp")

    assert result.get("platform") == "whatsapp", (
        f"Expected platform 'whatsapp', got {result.get('platform')!r}"
    )
    assert result.get("contact") == "Sarah", (
        f"Expected contact 'Sarah', got {result.get('contact')!r}"
    )
