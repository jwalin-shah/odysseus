"""Thin wrapper around the inbox server's WhatsApp routes.

The inbox server (default: http://localhost:9849) must be running and
have been granted Accessibility permission on macOS for this to work.
"""

from __future__ import annotations

from typing import Any

from src.inbox_tool import InboxError, inbox_get, inbox_post


INBOX_BASE = "http://localhost:9849"


class WhatsAppNotReady(Exception):
    """Raised when WhatsApp.app is not reachable through the inbox bridge.

    Typical causes on macOS:
      * WhatsApp.app is not running.
      * The host app does not have Accessibility permission
        (System Settings -> Privacy & Security -> Accessibility).
      * The inbox server is not running, or the user is signed out.
    """

    INSTRUCTIONS = (
        "WhatsApp bridge is not ready. To fix:\n"
        "  1. Open WhatsApp.app on this Mac and stay signed in.\n"
        "  2. Grant the inbox server Accessibility permission:\n"
        "       System Settings -> Privacy & Security -> Accessibility\n"
        "     (add Terminal / the host app and toggle it on).\n"
        "  3. Make sure the inbox server is running at "
        f"{INBOX_BASE}.\n"
        "  4. Retry once WhatsApp is responsive."
    )

    def __init__(self, message: str | None = None, *, cause: Exception | None = None):
        super().__init__(message or self.INSTRUCTIONS)
        if cause is not None:
            self.__cause__ = cause


# --- internal helpers -------------------------------------------------------

def _status_of(resp: Any) -> int | None:
    """Best-effort extraction of an HTTP status code from a response."""
    return getattr(resp, "status_code", None)


def _json_of(resp: Any) -> Any:
    """Best-effort JSON decode; returns the raw object if it isn't a Response."""
    decoder = getattr(resp, "json", None)
    if callable(decoder):
        return decoder()
    return resp


# --- public API -------------------------------------------------------------

def check_ready() -> bool:
    """Probe the WhatsApp bridge and confirm it has at least one contact.

    Returns True when WhatsApp is ready. Raises WhatsAppNotReady when:
      * the contacts endpoint returns HTTP 403 (no Accessibility
        permission, or app not authorised), or
      * the contacts endpoint returns an empty list (app open but no
        conversations, or the bridge cannot see any), or
      * the inbox server itself errors out.

    Call this once at the start of a session, or whenever you suspect
    the bridge has gone stale, before invoking `get_thread` / `send`.
    """
    try:
        resp = inbox_get("/whatsapp/contacts")
    except InboxError as exc:
        # Connection refused, server down, etc.
        raise WhatsAppNotReady(
            f"Could not reach the inbox server at {INBOX_BASE}: {exc}",
            cause=exc,
        ) from exc

    status = _status_of(resp)
    if status == 403:
        raise WhatsAppNotReady(
            "WhatsApp contacts endpoint returned 403 Forbidden. "
            "The inbox server likely lacks Accessibility permission.\n"
            + WhatsAppNotReady.INSTRUCTIONS
        )

    try:
        contacts = _json_of(resp)
    except ValueError as exc:
        raise WhatsAppNotReady(
            f"WhatsApp contacts endpoint returned invalid JSON: {exc}",
            cause=exc,
        ) from exc

    if not contacts:
        raise WhatsAppNotReady(
            "WhatsApp returned no contacts. Make sure WhatsApp.app is "
            "open and has at least one conversation, then retry.\n"
            + WhatsAppNotReady.INSTRUCTIONS
        )

    return True


def get_contacts() -> list:
    """Return the list of WhatsApp contacts from the inbox server.

    Raises WhatsAppNotReady on a 403, so callers can use this as a
    lightweight readiness probe if they don't need the boolean return
    of `check_ready`.
    """
    resp = inbox_get("/whatsapp/contacts")
    if _status_of(resp) == 403:
        raise WhatsAppNotReady()
    contacts = _json_of(resp)
    return list(contacts) if contacts is not None else []


def get_thread(contact_id: str, limit: int = 20) -> list:
    """Return up to `limit` messages from the thread with `contact_id`.

    The contact_id is whatever the inbox server uses to identify a
    contact (typically a phone number or JID).
    """
    if not contact_id:
        raise ValueError("contact_id is required")

    resp = inbox_get(
        f"/whatsapp/messages/{contact_id}",
        params={"limit": limit},
    )
    messages = _json_of(resp)
    return list(messages) if messages is not None else []


def send(to: str, body: str) -> dict:
    """Send a WhatsApp message via the inbox server.

    Intentionally NOT gated by `check_ready`: the inbox server's send
    route is the only path that should ever invoke the macOS-side
    WhatsApp automation, and we want callers to be able to decide their
    own readiness policy (e.g. send-and-pray vs. verify-first).
    """
    if not to:
        raise ValueError("`to` is required")
    if body is None:
        raise ValueError("`body` is required")

    payload = {"source": "whatsapp", "to": to, "body": body}
    return inbox_post("/messages/send", json=payload)
