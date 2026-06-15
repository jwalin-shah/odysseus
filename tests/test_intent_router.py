"""Parametrized tests for src.intent_router.classify()."""
import pytest

from src.intent_router import classify


def _assert_intent(result, *, platform=None, action=None, contact=None, time_info=None):
    """Assert that the classify() result matches the expected fields.

    Only the fields explicitly provided are checked, so each test case
    can focus on the fields relevant to its intent.
    """
    if platform is not None:
        assert result.platform == platform, (
            f"platform: expected {platform!r}, got {result.platform!r}"
        )
    if action is not None:
        assert result.action == action, (
            f"action: expected {action!r}, got {result.action!r}"
        )
    if contact is not None:
        assert result.contact == contact, (
            f"contact: expected {contact!r}, got {result.contact!r}"
        )
    if time_info is not None:
        for key, expected_value in time_info.items():
            actual_value = result.time_info.get(key)
            assert actual_value == expected_value, (
                f"time_info[{key!r}]: expected {expected_value!r}, "
                f"got {actual_value!r}"
            )


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
            id="reply-to-mom-imessage",
        ),
        pytest.param(
            "send email to John about the deal",
            {
                "platform": "gmail",
                "contact": "John",
            },
            id="email-to-john-gmail",
        ),
        pytest.param(
            "add meeting Tuesday 3pm",
            {
                "platform": "calendar",
                "action": "create",
                "time_info": {"day": "Tuesday"},
            },
            id="add-meeting-tuesday-calendar",
        ),
        pytest.param(
            "fix bug in auth.py",
            {
                "platform": "code",
            },
            id="fix-bug-in-code-file",
        ),
        pytest.param(
            "what did Sarah say on WhatsApp",
            {
                "platform": "whatsapp",
                "contact": "Sarah",
            },
            id="sarah-message-on-whatsapp",
        ),
        pytest.param(
            "show my LinkedIn DMs",
            {
                "platform": "linkedin",
                "action": "read",
            },
            id="read-linkedin-dms",
        ),
    ],
)
def test_classify(text, expected):
    """classify() should map each natural-language input to the correct intent."""
    result = classify(text)
    _assert_intent(result, **expected)


def test_classify_returns_non_empty_platform():
    """Sanity check: every input must produce a non-empty platform identifier."""
    result = classify("do something random")
    assert result.platform
    assert isinstance(result.platform, str)
