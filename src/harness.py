from dataclasses import dataclass, field
from typing import Callable, Optional

from src.intent_router import classify
from src.inbox_tool import (
    get_calendar_upcoming,
    get_gmail_unread,
    get_imessage_contacts,
    get_linkedin_dms,
)
from src.pi_call import pi_call


@dataclass
class HarnessResult:
    content: str
    action_taken: str
    needs_approval: bool = False
    approval_payload: dict = field(default_factory=dict)


# Platform -> reader function dispatch for the "read" intent.
_PLATFORM_READERS: dict[str, Callable] = {
    "imessage": get_imessage_contacts,
    "gmail": get_gmail_unread,
    "calendar": get_calendar_upcoming,
    "linkedin": get_linkedin_dms,
}


def _handle_read(user_text: str, context: dict) -> HarnessResult:
    platform = (context or {}).get("platform", "gmail")
    reader = _PLATFORM_READERS.get(platform)
    if reader is None:
        return HarnessResult(
            content=f"Unsupported platform for read: {platform}",
            action_taken="read_unsupported",
        )
    try:
        items = reader()
    except Exception as exc:  # noqa: BLE001 - surface error to caller
        return HarnessResult(
            content=f"Failed to read {platform}: {exc}",
            action_taken="read_error",
        )
    return HarnessResult(
        content=str(items),
        action_taken=f"read_{platform}",
    )


def _handle_send_or_reply(user_text: str, context: dict, kind: str) -> HarnessResult:
    return HarnessResult(
        content=f"{kind.capitalize()} requires approval before dispatch.",
        action_taken=f"{kind}_pending",
        needs_approval=True,
        approval_payload={
            "kind": kind,
            "text": user_text,
            "platform": (context or {}).get("platform"),
        },
    )


def _handle_calendar_create(user_text: str, context: dict) -> HarnessResult:
    return HarnessResult(
        content="Calendar event creation requires approval.",
        action_taken="calendar_create_pending",
        needs_approval=True,
        approval_payload={
            "kind": "calendar_create",
            "text": user_text,
            "context": context or {},
        },
    )


def _handle_code(user_text: str, context: dict) -> HarnessResult:
    try:
        result = pi_call("tokenrouter/MiniMax-M3", user_text)
    except Exception as exc:  # noqa: BLE001 - surface error to caller
        return HarnessResult(
            content=f"Code generation failed: {exc}",
            action_taken="code_error",
        )
    return HarnessResult(
        content=str(result),
        action_taken="code_generated",
    )


def _handle_general(user_text: str, context: dict) -> HarnessResult:
    return HarnessResult(
        content="I can help with iMessage, Gmail, WhatsApp, Calendar, LinkedIn, or code.",
        action_taken="general_help",
    )


_HANDLERS: dict[str, Callable[[str, dict], HarnessResult]] = {
    "read": _handle_read,
    "send": lambda t, c: _handle_send_or_reply(t, c, "send"),
    "reply": lambda t, c: _handle_send_or_reply(t, c, "reply"),
    "calendar_create": _handle_calendar_create,
    "code": _handle_code,
    "general": _handle_general,
}


def _resolve_intent(classified) -> str:
    """Normalize the classify() return value to an intent name string."""
    if hasattr(classified, "intent"):
        return str(classified.intent)
    if isinstance(classified, dict):
        return str(classified.get("intent", "general"))
    return str(classified) if classified else "general"


def route(user_text: str, context: Optional[dict] = None) -> HarnessResult:
    """Classify intent and dispatch to deterministic handler."""
    if context is None:
        context = {}

    try:
        classified = classify(user_text)
    except Exception as exc:  # noqa: BLE001 - surface error to caller
        return HarnessResult(
            content=f"Intent classification failed: {exc}",
            action_taken="classify_error",
        )

    intent_name = _resolve_intent(classified)
    handler = _HANDLERS.get(intent_name, _handle_general)
    return handler(user_text, context)
