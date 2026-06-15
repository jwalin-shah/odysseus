"""Thin wrapper around the inbox server's WhatsApp routes.

The inbox server (default: http://localhost:9849) exposes three routes for
interacting with WhatsApp on macOS:

    GET  /whatsapp/contacts
    GET  /whatsapp/messages/{contact_id}
    POST /messages/send          {source: "whatsapp", to: str, body: str}

Because WhatsApp automation on macOS depends on AppleScript + the macOS
Accessibility API, the inbox server requires:

    * WhatsApp.app to be running, and
    * the controlling terminal/process to have Accessibility permission
      (System Settings -> Privacy & Security -> Accessibility).

This module surfaces a `WhatsAppNotReady` error when those prerequisites
are not met so callers can show a clear remediation message instead of
dealing with opaque HTTP errors.
"""

from __future__ import annotations

from typing import Any

from src.inbox_tool import InboxError, inbox_get, inbox_post


__all__ = [
    "WhatsAppNotReady",
    "check_ready",
    "get_contacts",
    "get_thread",
    "send",
]


# Default base URL for the inbox server. Kept here as a constant so tests
# can monkeypatch it (or so operators can point the bridge at a different
# host/port without touching the inbox_tool internals).
INBOX_BASE_URL = "http://localhost:9849"

# Path constants -- isolated so the rest of the codebase (and tests) can
# reference them without re-typing strings.
CONTACTS_PATH = "/whatsapp/contacts"
THREAD_PATH_TEMPLATE = "/whatsapp/messages/{contact_id}"
SEND_PATH = "/messages/send"


# macOS Accessibility permission instructions. Kept as a single string so
# it can be displayed verbatim in logs, CLI errors, or UI prompts.
ACCESSIBILITY_INSTRUCTIONS = (
    "WhatsApp automation requires two things on macOS:\n"
    "  1. WhatsApp.app must be open and running.\n"
    "  2. The terminal (or process) running the inbox server must have\n"
    "     Accessibility permission:\n"
    "         System Settings -> Privacy & Security -> Accessibility\n"
    "     Add and enable the relevant Terminal / iTerm / Python entry,\n"
    "     then restart the inbox server."
)


class WhatsAppNotReady(Exception):
    """Raised when the inbox server cannot reach WhatsApp.

    Typical causes:
      * WhatsApp.app is not running.
      * Accessibility permission is not granted to the inbox server.
      * The inbox server returned an empty contact list (often a sign
        that WhatsApp has not finished initialising).
    """

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _status_from_error(exc: InboxError) -> int | None:
    """Best-effort extraction of an HTTP status code from an InboxError.

    Different HTTP libraries expose the status code in different places
    (`.status_code`, `.response.status_code`, `.code`, ...). This helper
    tries the common ones so the bridge works regardless of which client
    `inbox_tool` is built on.
    """
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    if response is not None:
        value = getattr(response, "status_code", None)
        if isinstance(value, int):
            return value
    return None


def _inbox_get_json(path: str) -> Any:
    """Wrapper around `inbox_get` that normalises 403 into WhatsAppNotReady.

    The inbox server returns 403 when the Accessibility permission check
    fails. We surface that as `WhatsAppNotReady` so callers do not need
    to know about HTTP status codes.
    """
    try:
        return inbox_get(path)
    except InboxError as exc:
        if _status_from_error(exc) == 403:
            raise WhatsAppNotReady(
                f"Inbox server denied access to {path} (HTTP 403).\n"
                f"{ACCESSIBILITY_INSTRUCTIONS}",
                status_code=403,
            ) from exc
        raise


def check_ready() -> bool:
    """Return True if the inbox server can talk to WhatsApp.

    This is a non-throwing probe: it returns False on any failure
    (network error, permission error, empty contact list) so it can be
    used as a simple health check from CLI, tests, or startup banners.
    """
    try:
        contacts = get_contacts()
    except (WhatsAppNotReady, InboxError):
        return False
    return bool(contacts)


def get_contacts() -> list:
    """Return the list of WhatsApp contacts from the inbox server.

    Raises:
        WhatsAppNotReady: if the server returns 403 (Accessibility
            permission missing) or an empty list (WhatsApp.app not
            running / not yet initialised).
    """
    payload = _inbox_get_json(CONTACTS_PATH)

    # The inbox server is expected to return a JSON array. Be defensive
    # in case it returns an object wrapper like `{"contacts": [...]}`.
    if isinstance(payload, dict):
        contacts = payload.get("contacts", [])
    else:
        contacts = payload

    if not contacts:
        raise WhatsAppNotReady(
            "Inbox server returned no WhatsApp contacts.\n"
            f"{ACCESSIBILITY_INSTRUCTIONS}"
        )

    return list(contacts)


def get_thread(contact_id: str, limit: int = 20) -> list:
    """Return the most recent messages in the thread with `contact_id`.

    Args:
        contact_id: The contact identifier as used by the inbox server
            (typically a phone number or JID).
        limit: Maximum number of messages to retrieve. Defaults to 20.
            Trimming is performed client-side so it works regardless of
            whether the inbox server supports a `?limit=` query param.

    Returns:
        A list of message objects, ordered as returned by the inbox
        server (most-recent-last by convention).
    """
    if not contact_id:
        raise ValueError("contact_id is required")
    if limit < 0:
        raise ValueError("limit must be non-negative")

    path = THREAD_PATH_TEMPLATE.format(contact_id=contact_id)
    payload = _inbox_get_json(path)

    if isinstance(payload, dict):
        messages = payload.get("messages", [])
    else:
        messages = payload

    messages = list(messages)
    if messages and len(messages) > limit:
        # Preserve the server's ordering but keep only the trailing
        # `limit` entries (assumed to be the most recent).
        messages = messages[-limit:]
    return messages


def send(to: str, body: str) -> dict:
    """Send a WhatsApp message via the inbox server.

    Intentionally not gated by `check_ready()`: callers that have already
    confirmed connectivity (e.g. immediately after fetching contacts)
    should not pay the latency cost of an extra probe. If WhatsApp is
    not actually ready, the inbox server will surface that as a 403,
    which we re-raise as `WhatsAppNotReady` so the user still gets
    actionable guidance.
    """
    if not to:
        raise ValueError("'to' is required")
    if not body:
        raise ValueError("'body' is required")

    try:
        return inbox_post(
            SEND_PATH,
            json={"source": "whatsapp", "to": to, "body": body},
        )
    except InboxError as exc:
        if _status_from_error(exc) == 403:
            raise WhatsAppNotReady(
                "Inbox server denied WhatsApp send (HTTP 403).\n"
                f"{ACCESSIBILITY_INSTRUCTIONS}",
                status_code=403,
            ) from exc
        raise
