"""
Thin wrapper around the inbox server's WhatsApp routes.

The inbox server is expected to be running at http://localhost:9849 and to
expose the WhatsApp desktop client's data via macOS Accessibility APIs. As
a result, the bridge is only usable when:

  * WhatsApp.app is open on the same machine as the inbox server, and
  * The inbox server helper has been granted the macOS Accessibility
    permission (System Settings -> Privacy & Security -> Accessibility).

If either condition is not met, GET /whatsapp/contacts will respond with
HTTP 403 (driver unavailable / permission denied) or 200 with an empty
list. Both cases are surfaced as `WhatsAppNotReady` so callers can show a
clear remediation message instead of silently returning nothing.
"""
from __future__ import annotations

from typing import Any

from src.inbox_tool import InboxError, inbox_get, inbox_post


class WhatsAppNotReady(Exception):
    """Raised when the WhatsApp bridge is unreachable or not authorised.

    See the module docstring for the most common causes and remediation.
    """


_READY_INSTRUCTIONS = (
    "WhatsApp bridge is not ready. To fix:\n"
    "  1. Open WhatsApp.app and sign in.\n"
    "  2. Grant Accessibility permission to the inbox server helper\n"
    "     (System Settings -> Privacy & Security -> Accessibility).\n"
    "  3. Make sure the inbox server is running at http://localhost:9849."
)


def _extract_list(payload: Any, *keys: str) -> list:
    """Best-effort normalisation: pull a list out of `payload`.

    The inbox server may return a bare JSON list or a dict wrapping the
    results under one of `keys` (e.g. {"contacts": [...]}). Anything else
    is treated as an empty list so callers always get a list back.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _fetch_contacts() -> list:
    """GET /whatsapp/contacts, normalising the response shape.

    Returns:
        A (possibly empty) list of contacts on success.

    Raises:
        InboxError: for transport or non-403 server errors. We deliberately
            do not swallow these so callers can distinguish a down inbox
            server from an unready WhatsApp bridge. A 403 is collapsed to
            an empty list and handled by the readiness logic in the public
            API.
    """
    try:
        return _extract_list(
            inbox_get("/whatsapp/contacts"),
            "contacts", "data", "results",
        )
    except InboxError as e:
        status = getattr(e, "status_code", None) or getattr(e, "code", None)
        if status == 403:
            return []
        raise


def check_ready() -> bool:
    """Return True if the WhatsApp bridge appears to be operational.

    The bridge is considered ready when /whatsapp/contacts returns a
    non-empty contact list with a non-403 status. This is a soft probe: it
    never raises `WhatsAppNotReady`, so it is safe to use in startup
    checks or status displays.
    """
    return bool(_fetch_contacts())


def get_contacts() -> list:
    """Return the list of WhatsApp contacts.

    Raises:
        WhatsAppNotReady: if the inbox server responds with HTTP 403
            (Accessibility permission missing or driver unavailable) or
            with an empty contact list (WhatsApp.app not running, not
            signed in, or no chats yet).
    """
    contacts = _fetch_contacts()
    if not contacts:
        raise WhatsAppNotReady(_READY_INSTRUCTIONS)
    return contacts


def get_thread(contact_id: str, limit: int = 20) -> list:
    """Return the messages in a WhatsApp thread.

    Args:
        contact_id: WhatsApp chat / contact identifier as returned by
            `get_contacts`.
        limit: maximum number of messages to fetch. Forwarded as the
            `limit` query parameter to the inbox server.

    Returns:
        A list of message dicts. Returns an empty list if the thread is
        unknown or the server returned no messages. Callers are expected
        to have already verified readiness via `get_contacts()`.
    """
    if not contact_id:
        raise ValueError("contact_id is required")
    payload = inbox_get(
        f"/whatsapp/messages/{contact_id}",
        params={"limit": limit},
    )
    return _extract_list(payload, "messages", "data", "results")


def send(to: str, body: str) -> dict:
    """Send a WhatsApp message via the inbox server.

    This is a mutating action and is intentionally NOT gated by
    `check_ready` / `get_contacts`: readiness is the caller's
    responsibility (typically a single `get_contacts()` call at the start
    of a session), and "explicit call" is the safeguard against an agent
    firing off messages on its own. Do not invoke this from a loop, a
    background poller, or any auto-reply flow without a human-in-the-loop
    approval step upstream.

    Args:
        to: destination contact identifier (as returned by `get_contacts`).
        body: message text to send.

    Returns:
        The inbox server's JSON response (typically includes an ack / id).
    """
    if not to:
        raise ValueError("`to` is required")
    if body is None:
        raise ValueError("`body` is required")
    return inbox_post(
        "/messages/send",
        json={"source": "whatsapp", "to": to, "body": body},
    )
