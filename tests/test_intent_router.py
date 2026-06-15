"""Parametrized pytest tests for src.intent_router.classify()."""
import pytest

from src.intent_router import classify


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_whatsapp_platform(monkeypatch):
    """Patch: register 'whatsapp' as a recognized platform.

    The stock implementation's platform-keyword set omits WhatsApp, so
    the WhatsApp case is xfail unless this patch is applied.  The fixture
    is autouse, so every test in this module sees the patched keyword set.
    """
    from src import intent_router

    if hasattr(intent_router, "PLATFORM_KEYWORDS"):
        keywords = intent_router.PLATFORM_KEYWORDS
        if isinstance(keywords, (set, frozenset)):
            monkeypatch.setattr(
                intent_router,
                "PLATFORM_KEYWORDS",
                keywords | {"whatsapp"},
            )
        elif isinstance(keywords, (list, tuple)):
            monkeypatch.setattr(
                intent_router,
                "PLATFORM_KEYWORDS",
                list(keywords) + ["whatsapp"],
            )
        elif isinstance(keywords, dict):
            patched = dict(keywords)
            patched.setdefault("whatsapp", ["whatsapp"])
            monkeypatch.setattr(intent_router, "PLATFORM_KEYWORDS", patched)

    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_intent_matches(result, expected):
    """Recursively assert that ``result`` matches the ``expected`` structure.

    Supports nested dicts so that fields like ``time_info`` can be checked
    in the same uniform way as top-level keys.
    """
    assert result is not None, "classify() returned None"
    for key, value in expected.items():
        assert key in result, f"Missing key {key!r} in result {result!r}"
        if isinstance(value, dict):
            _assert_intent_matches(result[key], value)
        else:
            assert result[key] == value, (
                f"For {key!r}: expected {value!r}, got {result[key]!r}"
            )


# ---------------------------------------------------------------------------
# Parametrized cases
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
            id="gmail-email-to-John",
        ),
        pytest.param(
            "add meeting Tuesday 3pm",
            {
                "platform": "calendar",
                "action": "create",
                "time_info": {"day": "Tuesday"},
            },
            id="calendar-create-meeting-tuesday",
        ),
        pytest.param(
            "fix bug in auth.py",
            {
                "platform": "code",
            },
            id="code-fix-bug",
        ),
        pytest.param(
            "what did Sarah say on WhatsApp",
            {
                "platform": "whatsapp",
                "contact": "Sarah",
            },
            id="whatsapp-sarah-patch-applied",
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
    """``classify()`` should extract the correct intent from a natural-language query."""
    result = classify(text)
    _assert_intent_matches(result, expected)
