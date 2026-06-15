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
        pytest.param(
            "what did Sarah say on WhatsApp",
            {
                "platform": "whatsapp",
                "contact": "Sarah",
            },
            marks=pytest.mark.xfail(
                reason="WhatsApp platform detection pending patch",
                strict=False,
            ),
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
        "whatsapp_sarah_xfail_until_patch",
        "linkedin_read_dms",
    ],
)
def test_classify_returns_expected_fields(text, expected):
    """classify() should extract the expected fields for each prompt."""
    result = classify(text)

    # classify() is expected to return a mapping-like object (e.g. dict).
    assert isinstance(result, dict), (
        f"classify({text!r}) must return a dict-like mapping, got {type(result).__name__}"
    )

    for key, value in expected.items():
        if isinstance(value, dict):
            # Nested structure (e.g. time_info): assert the sub-keys individually.
            assert key in result, (
                f"For {text!r}: expected key {key!r} in result, got keys {list(result)}"
            )
            nested = result[key]
            assert isinstance(nested, dict), (
                f"For {text!r}: expected {key!r} to be a dict, got {type(nested).__name__}"
            )
            for sub_key, sub_value in value.items():
                assert nested.get(sub_key) == sub_value, (
                    f"For {text!r}: expected {key}.{sub_key}={sub_value!r}, "
                    f"got {nested.get(sub_key)!r}"
                )
        else:
            assert result.get(key) == value, (
                f"For {text!r}: expected {key}={value!r}, got {result.get(key)!r}"
            )


def test_classify_returns_dict():
    """Smoke test: classify() returns a dict for any non-empty string."""
    result = classify("hello world")
    assert isinstance(result, dict)
    assert "platform" in result
