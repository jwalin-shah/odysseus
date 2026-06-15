import pytest
from src.intent_router import classify


@pytest.mark.parametrize(
    "query, expected",
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
            id="code-fix-auth",
        ),
        pytest.param(
            "what did Sarah say on WhatsApp",
            {"platform": "whatsapp", "contact": "Sarah"},
            id="whatsapp-sarah",
            marks=pytest.mark.xfail(
                reason="WhatsApp contact extraction requires upstream patch"
            ),
        ),
        pytest.param(
            "show my LinkedIn DMs",
            {"platform": "linkedin", "action": "read"},
            id="linkedin-read-dms",
        ),
    ],
)
def test_classify(query, expected):
    """Parametrized tests for src.intent_router.classify()."""
    result = classify(query)

    for key, value in expected.items():
        if key == "time_info":
            # Only assert the specified sub-keys (e.g. 'day') so the test
            # remains resilient to extra fields like 'time' or 'timezone'.
            for sub_key, sub_value in value.items():
                assert result.get("time_info", {}).get(sub_key) == sub_value, (
                    f"Expected time_info['{sub_key}'] == {sub_value!r} "
                    f"for query {query!r}, got {result.get('time_info')!r}"
                )
        else:
            assert result.get(key) == value, (
                f"Expected {key} == {value!r} for query {query!r}, "
                f"got {result.get(key)!r}"
            )
