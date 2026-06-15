"""Parametrized tests for intent_router.classify().

Run with:
    pytest tests/test_intent_router.py -v
"""

import sys
from pathlib import Path

import pytest

# Ensure the src/ package is importable regardless of where pytest is invoked
# from. This keeps `from intent_router import classify` working in the typical
# layout:
#   <repo>/
#     src/intent_router.py
#     tests/test_intent_router.py
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from intent_router import classify  # noqa: E402


# Each test case is (input text, expected field mapping).
#
# Nested mappings (e.g. time_info) are checked key-by-key rather than with
# full dict equality, so classify() is free to attach additional metadata
# (timestamps, confidence scores, etc.) without breaking these tests.
CASES = [
    pytest.param(
        "reply to mom's text",
        {
            "platform": "imessage",
            "action": "reply",
            "contact": "mom",
        },
        id="imessage_reply_mom",
    ),
    pytest.param(
        "send email to John about the deal",
        {
            "platform": "gmail",
            "contact": "John",
        },
        id="gmail_email_john",
    ),
    pytest.param(
        "add meeting Tuesday 3pm",
        {
            "platform": "calendar",
            "action": "create",
            "time_info": {"day": "Tuesday"},
        },
        id="calendar_create_tuesday",
    ),
    pytest.param(
        "fix bug in auth.py",
        {
            "platform": "code",
        },
        id="code_fix_bug",
    ),
    pytest.param(
        "what did Sarah say on WhatsApp",
        {
            "platform": "whatsapp",
            "contact": "Sarah",
        },
        # Contact extraction from the "what did <X> say on <platform>" pattern
        # depends on the WhatsApp/intent patch. Will fail until that lands.
        id="whatsapp_sarah",
    ),
    pytest.param(
        "show my LinkedIn DMs",
        {
            "platform": "linkedin",
            "action": "read",
        },
        id="linkedin_read_dms",
    ),
]


@pytest.mark.parametrize("text, expected", CASES)
def test_classify_expected_fields(text, expected):
    """classify() should populate the expected fields for each input."""
    result = classify(text)

    for key, expected_value in expected.items():
        assert key in result, f"Missing key {key!r} in classify({text!r}) -> {result!r}"

        if isinstance(expected_value, dict):
            # For nested mappings (e.g. time_info) verify each specified sub-key
            # individually so additional fields don't trigger false failures.
            nested = result[key]
            assert isinstance(nested, dict), (
                f"Expected {key!r} to be a mapping for classify({text!r}), "
                f"got {type(nested).__name__}: {nested!r}"
            )
            for sub_key, sub_value in expected_value.items():
                assert sub_key in nested, (
                    f"Missing sub-key {sub_key!r} under {key!r} "
                    f"in classify({text!r}) -> {result!r}"
                )
                assert nested[sub_key] == sub_value, (
                    f"classify({text!r}): expected {key}.{sub_key}={sub_value!r}, "
                    f"got {nested[sub_key]!r}"
                )
        else:
            assert result[key] == expected_value, (
                f"classify({text!r}): expected {key}={expected_value!r}, "
                f"got {result[key]!r}"
            )
