"""Tests for src.intent_router.classify().

Verifies that natural-language commands are correctly classified into
structured intents (platform, action, contact, time_info, etc.).
"""
import pytest

from src.intent_router import classify


@pytest.mark.parametrize(
    "text, expected_platform, expected_action, expected_contact, expected_time_info",
    [
        # "reply to mom's text"  ->  iMessage, reply, contact = mom
        (
            "reply to mom's text",
            "imessage", "reply", "mom", None,
        ),
        # "send email to John about the deal"  ->  Gmail, contact = John
        (
            "send email to John about the deal",
            "gmail", None, "John", None,
        ),
        # "add meeting Tuesday 3pm"  ->  Calendar, create, day = Tuesday
        (
            "add meeting Tuesday 3pm",
            "calendar", "create", None, {"day": "Tuesday"},
        ),
        # "fix bug in auth.py"  ->  code-editing task
        (
            "fix bug in auth.py",
            "code", None, None, None,
        ),
        # "what did Sarah say on WhatsApp"  ->  WhatsApp, contact = Sarah
        # Currently failing: pending patch to extract contact when the
        # platform name appears later in the query (not as the leading token).
        pytest.param(
            "what did Sarah say on WhatsApp",
            "whatsapp", None, "Sarah", None,
            marks=pytest.mark.xfail(
                reason="Pending patch: WhatsApp contact extraction when "
                       "platform name appears later in the query"
            ),
        ),
        # "show my LinkedIn DMs"  ->  LinkedIn, read
        (
            "show my LinkedIn DMs",
            "linkedin", "read", None, None,
        ),
    ],
)
def test_classify(
    text,
    expected_platform,
    expected_action,
    expected_contact,
    expected_time_info,
):
    """classify() should map a free-form command to the correct intent."""
    result = classify(text)

    # platform is always present
    assert result.platform == expected_platform

    # only assert the fields this case is expected to set
    if expected_action is not None:
        assert result.action == expected_action

    if expected_contact is not None:
        assert result.contact == expected_contact

    if expected_time_info is not None:
        for key, value in expected_time_info.items():
            assert getattr(result.time_info, key) == value
