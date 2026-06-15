"""Thin wrapper around the inbox server's WhatsApp routes.

The inbox server (http://localhost:9849) exposes WhatsApp-specific endpoints
that require WhatsApp.app to be open on macOS with Accessibility permission
granted to the inbox server. This module is the only place those details
live; callers talk to ``get_contacts``/``get_thread``/``send`` and never see
the HTTP layer.

Typical use::

    from src.whatsapp_bridge import (
        WhatsAppNotReady, check_ready, get_contacts, get_thread, send,
    )

    try:
        check_ready()
    except WhatsAppNotReady as exc:
        log.error(exc)
        return

    for contact in get_contacts():
        msgs = get_thread(contact["id"], limit=10)
        ...
"""

from __future__ import annotations

from typing import Any

from src.inbox_tool import InboxError, inbox_get, inbox_post


__all__ = [
    "BASE_URL",
    "WhatsAppNotReady",
    "check_ready",
    "get_contacts",
    "get_thread",
    "send",
]


BASE_URL = "http://localhost:9849"

WHATSAPP_NOT_READY_HINT = (
    "WhatsApp is not ready. To fix this:\n"
    "  1. Open WhatsApp.app on this Mac and bring it to the foreground.\n"
    "  2. Grant the inbox server macOS Accessibility permission "
    "(System Settings -> Privacy & Security -> Accessibility).\n"
    "  3. Retry once WhatsApp is in the foreground and contacts are loaded."
)


class WhatsAppNotReady(Exception):
    """Raised when the inbox server cannot reach WhatsApp.

    Typical causes:

    * WhatsApp.app is not running.
    * The inbox server has not been granted macOS Accessibility
      permission, in which case the server returns HTTP 403 for
      WhatsApp routes.
    * WhatsApp is open but has not loaded any contacts yet, so the
      server returns a 200 with an empty list.
    """

    def __init__(
        self,
        message: str = WHATSAPP_NOT_READY_HINT,
        *,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


def _is_403(exc: InboxError) -> bool:
    """Return True if an ``InboxError`` corresponds to HTTP 403."""
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if value == 403:
            return True
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if status == 403:
            return True
    # Last resort: some wrappers only embed the status in the message.
    return "403" in str(exc)


def _extract_list(response: Any, key: str) -> list[dict[str, Any]]:
    """Coerce a JSON response into a list of items.

    Accepts either a bare JSON list or a dict wrapping the list under
    ``key``. Anything else degrades to an empty list rather than raising,
    so callers can rely on ``not contacts`` as a readiness signal.
    """
    if response is None:
        return []
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        value = response.get(key)
        if isinstance(value, list):
            return value
    return []


def check_ready() -> bool:
    """Probe the inbox server's WhatsApp contacts endpoint.

    Returns ``True`` when WhatsApp is reachable and at least one contact
    is known. Raises :class:`WhatsAppNotReady` otherwise, carrying an
    actionable hint for the operator.

    Raises:
        WhatsAppNotReady: on HTTP 403 (Accessibility permission missing)
            or an empty contact list (WhatsApp.app not open / not loaded).
        InboxError: for any other transport or server failure.
    """
    try:
        response = inbox_get("/whatsapp/contacts", base_url=BASE_URL)
    except InboxError as exc:
        if _is_403(exc):
            raise WhatsAppNotReady(status_code=403) from exc
        raise

    contacts = _extract_list(response, "contacts")
    if not contacts:
        raise WhatsAppNotReady()

    return True


def get_contacts() -> list[dict[str, Any]]:
    """Return WhatsApp contacts known to the inbox server.

    Does not call :func:`check_ready`; callers that want fail-fast
    behaviour should invoke it explicitly first.
    """
    response = inbox_get("/whatsapp/contacts", base_url=BASE_URL)
    return _extract_list(response, "contacts")


def get_thread(contact_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return messages from a WhatsApp thread.

    Args:
        contact_id: The contact identifier as returned by
            :func:`get_contacts`.
        limit: Maximum number of messages to fetch. Forwarded to the
            inbox server as a ``?limit=`` query parameter.

    Returns:
        A list of message dicts in the server's preferred order
        (typically newest first).
    """
    if not contact_id:
        raise ValueError("contact_id is required")
    if limit <= 0:
        raise ValueError("limit must be a positive integer")

    path = f"/whatsapp/messages/{contact_id}?limit={int(limit)}"
    response = inbox_get(path, base_url=BASE_URL)
    return _extract_list(response, "messages")


def send(to: str, body: str) -> dict[str, Any]:
    """Send a WhatsApp message through the inbox server.

    Intentionally NOT gated by :func:`check_ready`: the inbox server is
    the source of truth and will reject the request with 403/empty if
    WhatsApp is not actually ready. This keeps the send path cheap and
    side-effect-free on the client side.

    Args:
        to: Destination contact id (or phone number, per the server's
            accepted format).
        body: Message text.

    Returns:
        The server's JSON response as a dict.
    """
    if not to:
        raise ValueError("'to' is required")
    if not body:
        raise ValueError("'body' is required")

    payload = {"source": "whatsapp", "to": to, "body": body}
    response = inbox_post("/messages/send", json=payload, base_url=BASE_URL)
    return response if isinstance(response, dict) else {"raw": response}
