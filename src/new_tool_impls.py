"""Handler implementations for inbox_read and inbox_send tools.

These handlers are wired into the Odysseus agent tool registry. inbox_read
dispatches to the appropriate integration; inbox_send is a strict approval
gate and never performs the actual send.
"""

from typing import Any, Dict

# Integration calls live in the odysseus.integrations package. Adjust import
# paths if your codebase organizes integrations differently.
from odysseus.integrations.calendar import get_calendar_upcoming
from odysseus.integrations.gmail import get_gmail_unread
from odysseus.integrations.imessage import (
    get_imessage_contacts,
    get_imessage_thread,
    get_imessage_unread,
)
from odysseus.integrations.linkedin import get_linkedin_dms


def do_inbox_read(args: Dict[str, Any]) -> Any:
    """Dispatch an inbox read request to the correct platform integration.

    Args:
        args: Tool input. Required: platform, action. Optional: contact, limit.

    Returns:
        Result from the underlying integration, or an error dict for
        unsupported platform/action combinations.
    """
    platform = args["platform"]
    action = args["action"]
    limit = args.get("limit", 10)

    if platform == "imessage" and action == "contacts":
        return get_imessage_contacts(limit)

    if platform == "imessage" and action == "thread":
        contact = args.get("contact")
        if not contact:
            return {"error": "contact is required for action='thread'"}
        return get_imessage_thread(contact, limit)

    if platform == "imessage" and action == "unread":
        return get_imessage_unread()

    if platform == "gmail" and action == "unread":
        return get_gmail_unread(limit)

    if platform == "calendar" and action == "upcoming":
        return get_calendar_upcoming()

    if platform == "linkedin" and action == "dms":
        return get_linkedin_dms(limit)

    return {
        "error": f"unsupported platform/action combination: {platform}/{action}"
    }


def do_inbox_send(args: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare a send request for human approval.

    This function NEVER sends a message. It always returns a payload flagged
    for approval; the agent runtime is responsible for surfacing it to a
    human and invoking the real send function only after confirmation.

    Args:
        args: Tool input. Required: to, body, platform. Optional: subject
            (used only when platform='gmail').

    Returns:
        {"needs_approval": True, "payload": {...}} with the full message
        details for the approver to review.
    """
    payload: Dict[str, Any] = {
        "platform": args["platform"],
        "to": args["to"],
        "body": args["body"],
    }

    # Preserve subject (gmail only) so the approver sees the complete message.
    subject = args.get("subject")
    if subject:
        payload["subject"] = subject

    return {"needs_approval": True, "payload": payload}
