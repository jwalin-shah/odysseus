"""Thin wrapper around the inbox server's WhatsApp routes.

The inbox server is a small local HTTP service (default
http://localhost:9849) that exposes WhatsApp operations. WhatsApp itself
runs through WhatsApp.app on macOS, which must be open with the
Accessibility permission granted to the inbox server.

We surface that runtime requirement as a :class:`WhatsAppNotReady`
exception with a short fix-it message, so callers can render it back to
the user instead of a stack trace.
"""
from __future__ import annotations

from typing import Any

from src.inbox_tool import InboxError, inbox_get, inbox_post


# HTTP 403 from the inbox server means "WhatsApp is not reachable". We
# treat it as a readiness failure rather than a transport error because
# the user can fix it by opening WhatsApp / granting Accessibility.
_STATUS_FORBIDDEN = 403

# Short, user-facing instructions shown when WhatsApp is not ready.
# Kept terse so it can be shown verbatim in a chat reply or log line.
_READY_INSTRUCTIONS = (
    "WhatsApp isn't ready. Open WhatsApp on this Mac, then grant "
    "Accessibility access to the inbox server (System Settings → "
    "Privacy & Security → Accessibility), and try again."
)


class WhatsAppNotReady(Exception):
    """Raised when the WhatsApp routes cannot service a request.

    The inbox server returns HTTP 403 when it cannot talk to WhatsApp
    (WhatsApp.app is not running, or the Accessibility permission has
    not been granted). The exception message contains a short fix-it
    recipe suitable for showing back to the user.
    """


def _coerce_list(data: Any) -> list:
    """Normalize an inbox response into a list.

    The inbox server may return either a bare JSON array or an object
    wrapping one (e.g. ``{"contacts": [...]}``). Anything else is
    treated as an empty list so callers can iterate safely.
    """
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("contacts", "messages", "items", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def check_ready() -> bool:
    """Return True if WhatsApp is usable, otherwise raise.

    A "not ready" condition is either:

    * the inbox server returns HTTP 403 for the contacts route, or
    * the contacts list is empty (fresh install, or a session that
      hasn't synced yet).

    The ``bool`` return type describes the success path. On failure
    the function raises :class:`WhatsAppNotReady` with a short
    remediation message, so callers don't have to special-case 403 or
    empty lists themselves.
    """
    contacts = get_contacts()  # raises WhatsAppNotReady on 403
    if not contacts:
        raise WhatsAppNotReady(_READY_INSTRUCTIONS)
    return True


def get_contacts() -> list:
    """Return the WhatsApp contact list from the inbox server.

    Raises :class:`WhatsAppNotReady` if the inbox server responds with
    HTTP 403 — that means WhatsApp.app is not open or the Accessibility
    permission has not been granted. An empty list is *not* an error
    here; use :func:`check_ready` if you want the stricter check.
    """
    try:
        data = inbox_get("/whatsapp/contacts")
    except InboxError as exc:
        if getattr(exc, "status_code", None) == _STATUS_FORBIDDEN:
            raise WhatsAppNotReady(_READY_INSTRUCTIONS) from exc
        raise
    return _coerce_list(data)


def get_thread(contact_id: str, limit: int = 20) -> list:
    """Return up to ``limit`` messages in the thread with ``contact_id``.

    The inbox server does the slicing; we forward ``limit`` as a query
    parameter so the server can honor it. The default of 20 matches
    the most common "recent messages" use case.
    """
    if not contact_id:
        raise ValueError("contact_id is required")
    path = f"/whatsapp/messages/{contact_id}?limit={int(limit)}"
    return _coerce_list(inbox_get(path))


def send(to: str, body: str) -> dict:
    """Send a WhatsApp message via the inbox server.

    Readiness is intentionally *not* gated here: a caller that has
    decided to send a message has already opted in, and the inbox
    server will surface its own error if WhatsApp isn't usable. We
    only validate the obvious inputs so we fail fast on programmer
    error rather than producing a confusing 400 from the server.
    """
    if not to:
        raise ValueError("to is required")
    if body is None:
        raise ValueError("body is required")
    payload = {"source": "whatsapp", "to": to, "body": body}
    return inbox_post("/messages/send", json=payload)
