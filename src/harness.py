from dataclasses import dataclass, field
import os
from typing import Callable

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
_PLATFORM_READERS: dict[str, Callable[[], object]] = {
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
    model = (context or {}).get("model") or os.environ.get(
        "PI_MODEL", "tokenrouter/MiniMax-M3"
    )
    try:
        result = pi_call(model, user_text)
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
