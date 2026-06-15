"""Thin wrapper around the inbox server's WhatsApp routes.

The inbox server (default: http://localhost:9849) exposes a small
WhatsApp bridge that proxies to WhatsApp.app on macOS via the
Accessibility API. This module is intentionally minimal: it just
turns the HTTP routes into Python functions and adds a single
readiness probe so callers get a clear error message instead of
mysterious empty results.
"""
from __future__ import annotations

from typing import Any

from src.inbox_tool import InboxError, inbox_get, inbox_post


BASE_URL = "http://localhost:9849"


class WhatsAppNotReady(RuntimeError):
    """Raised when the WhatsApp bridge is not usable.

    On macOS this almost always means one of two things:

      1. **WhatsApp.app is not open** (or not signed in).
      2. **Accessibility permission has not been granted** to this
         terminal / process in
         System Settings → Privacy & Security → Accessibility.

    Fix both, then re-run. The inbox server does not surface a
    nicely-typed error for these conditions, so we synthesise one
    here from the symptoms we *can* see: a 403 from the bridge, or
    a contacts list that comes back empty.
    """

    DEFAULT_HINT = (
        "WhatsApp bridge is not ready. On macOS, make sure:\n"
        "  1. WhatsApp.app is open and signed in.\n"
        "  2. This terminal / process has Accessibility permission\n"
        "     in System Settings → Privacy & Security → Accessibility.\n"
        "Then try the operation again."
    )

    def __init__(self, message: str = "", *, hint: str | None = None) -> None:
        if not message:
            message = hint or self.DEFAULT_HINT
        super().__init__(message)
        self.hint = hint or self.DEFAULT_HINT


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _is_forbidden(err: InboxError) -> bool:
    """Best-effort detection of a 403 from inside an InboxError."""
    for attr in ("status_code", "code", "status"):
        value = getattr(err, attr, None)
        if value == 403 or value == "403":
            return True
    # Fall back to substring matching against the message — InboxError
    # may wrap a requests.HTTPError whose str() includes the status.
    return "403" in str(err) or "forbidden" in str(err).lower()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_ready() -> bool:
    """Probe the WhatsApp bridge and raise if it isn't usable.

    Returns True on success. Raises WhatsAppNotReady when the bridge
    rejects access (403) or returns no contacts at all, which is the
    signal that WhatsApp.app / Accessibility permission are missing.

    Other errors (server down, network unreachable, etc.) propagate as
    InboxError so the caller can distinguish "bridge is up but WhatsApp
    is not ready" from "bridge is down entirely".
    """
    try:
        contacts = get_contacts()
    except InboxError as err:
        if _is_forbidden(err):
            raise WhatsAppNotReady() from err
        raise

    if not contacts:
        raise WhatsAppNotReady(
            "WhatsApp bridge returned no contacts. "
            "Open WhatsApp.app and ensure you are signed in."
        )
    return True


def get_contacts() -> list:
    """Return the list of WhatsApp contacts known to the bridge."""
    return inbox_get(f"{BASE_URL}/whatsapp/contacts")


def get_thread(contact_id: str, limit: int = 20) -> list:
    """Return up to `limit` messages from the thread with `contact_id`.

    Newest messages are typically last; the exact ordering is whatever
    the inbox server hands us.
    """
    if not contact_id:
        raise ValueError("contact_id is required")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be a positive integer")

    path = f"{BASE_URL}/whatsapp/messages/{contact_id}"
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = int(limit)

    return inbox_get(path, params=params or None)


def send(to: str, body: str) -> dict:
    """Send a WhatsApp message via the inbox server.

    Deliberately NOT gated by check_ready() — the inbox server
    enforces the actual permission / app-open requirements, and
    callers that want a pre-flight check should call check_ready()
    themselves. This keeps `send` cheap and side-effect-only.
    """
    if not to:
        raise ValueError("`to` is required")
    if body is None:
        raise ValueError("`body` is required")

    payload = {"source": "whatsapp", "to": to, "body": body}
    return inbox_post(f"{BASE_URL}/messages/send", json=payload)
