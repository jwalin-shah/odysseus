"""Thin wrapper around the inbox server's WhatsApp routes.

The inbox server (default http://localhost:9849) proxies these calls to a
local WhatsApp client. On macOS, that requires WhatsApp.app to be running
and Accessibility permission to be granted to the helper process.

If the inbox server can't reach WhatsApp it responds with HTTP 403, or
with an empty contact list. Both situations are surfaced here as
`WhatsAppNotReady` so callers can handle them in one place.
"""

from __future__ import annotations

from typing import Any

from src.inbox_tool import InboxError, inbox_get, inbox_post


class WhatsAppNotReady(Exception):
    """Raised when the WhatsApp backend isn't usable from the inbox server.

    Typical causes:
      - WhatsApp.app isn't running on this Mac.
      - Accessibility permission hasn't been granted to the helper
        process used by the inbox server (System Settings -> Privacy &
        Security -> Accessibility).
    """

    INSTRUCTIONS = (
        "To make WhatsApp ready:\n"
        "  1. Open WhatsApp.app on this Mac and sign in.\n"
        "  2. Open System Settings -> Privacy & Security -> Accessibility,\n"
        "     and make sure the helper process used by the inbox server\n"
        "     is toggled ON.\n"
        "  3. Restart the inbox server, then retry."
    )

    def __init__(
        self,
        message: str = "WhatsApp is not ready",
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(f"{message}\n\n{self.INSTRUCTIONS}")
        if cause is not None:
            self.__cause__ = cause


def _is_403(exc: BaseException) -> bool:
    """Best-effort detection of an HTTP 403 inside an `InboxError`."""
    status = getattr(exc, "status_code", None)
    if status == 403:
        return True
    text = str(exc).lower()
    return "403" in text or "forbidden" in text


def check_ready() -> bool:
    """Return True iff WhatsApp responds with a non-empty contact list.

    Diagnostic helper: never raises. Returns False when the inbox server
    replies 403 or with an empty list. Other errors propagate as
    `InboxError` so the caller can distinguish "WhatsApp not ready" from
    "inbox server is broken".
    """
    try:
        data = inbox_get("/whatsapp/contacts")
    except InboxError as exc:
        if _is_403(exc):
            return False
        raise
    return bool(data)


def get_contacts() -> list[dict[str, Any]]:
    """Return the WhatsApp contact list from the inbox server.

    Raises `WhatsAppNotReady` if the inbox server returns 403 or an
    empty list — both indicate WhatsApp.app isn't usable.
    """
    try:
        data = inbox_get("/whatsapp/contacts")
    except InboxError as exc:
        if _is_403(exc):
            raise WhatsAppNotReady(
                "Inbox server denied access to WhatsApp contacts",
                cause=exc,
            ) from exc
        raise

    if not data:
        raise WhatsAppNotReady(
            "WhatsApp returned no contacts (app closed or not signed in)"
        )
    return data


def get_thread(contact_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return up to `limit` messages from the thread with `contact_id`.

    Gated by the same readiness check as `get_contacts`: reading a
    thread requires WhatsApp to be accessible, so we surface
    `WhatsAppNotReady` here too rather than letting a generic HTTP
    error bubble up.
    """
    if not check_ready():
        raise WhatsAppNotReady("Cannot read thread: WhatsApp is not ready")
    path = f"/whatsapp/messages/{contact_id}"
    return inbox_get(path, params={"limit": limit})


def send(to: str, body: str) -> dict[str, Any]:
    """Send a WhatsApp message via the inbox server.

    Intentionally NOT gated by `check_ready`: this is the explicit,
    "I really mean to send" entry point. The caller is responsible for
    confirming the recipient and that WhatsApp is usable. Server-side
    errors propagate as `InboxError`.
    """
    payload = {"source": "whatsapp", "to": to, "body": body}
    return inbox_post("/messages/send", json=payload)
