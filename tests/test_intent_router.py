import pytest
from src.intent_router import classify


@pytest.mark.parametrize(
    "query, expected_platform, expected_action, expected_contact, expected_time_day",
    [
        ("reply to mom's text",                 "imessage", "reply",  "mom",   None),
        ("send email to John about the deal",   "gmail",    None,    "John",  None),
        ("add meeting Tuesday 3pm",             "calendar", "create", None,    "Tuesday"),
        ("fix bug in auth.py",                  "code",     None,    None,    None),
        ("what did Sarah say on WhatsApp",      "whatsapp", None,    "Sarah", None),
        ("show my LinkedIn DMs",                "linkedin", "read",  None,    None),
    ],
    ids=[
        "reply_mom_imessage",
        "email_john_gmail",
        "add_meeting_tuesday_calendar",
        "fix_bug_code",
        "whatsapp_sarah_message",
        "linkedin_dms_read",
    ],
)
def test_classify_platform(
    query, expected_platform, expected_action, expected_contact, expected_time_day
):
    """Parametrized tests for intent_router.classify()."""
    result = classify(query)

    # Platform is always expected.
    assert result.get("platform") == expected_platform

    # Optional fields are only asserted when explicitly expected.
    if expected_action is not None:
        assert result.get("action") == expected_action

    if expected_contact is not None:
        assert result.get("contact") == expected_contact

    if expected_time_day is not None:
        # time_info is expected to be a mapping with a 'day' key.
        time_info = result.get("time_info") or {}
        assert time_info.get("day") == expected_time_day
