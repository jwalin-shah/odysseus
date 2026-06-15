"""Thin wrapper around the inbox server's WhatsApp routes.

The inbox server (http://localhost:9849) exposes a small HTTP surface that
drives WhatsApp.app via macOS Accessibility. This module is a thin Python
wrapper that:

  * Translates 403 / empty responses into WhatsAppNotReady with actionable
    instructions (open WhatsApp.app, grant Accessibility permission).
  * Normalizes response parsing so callers get plain Python data.
  * Keeps the surface area small and explicit: check readiness, list
    contacts, read a thread, send a message.

Routes used:
  GET  /whatsapp/contacts
  GET  /whatsapp/messages/{contact_id}
  POST /messages/send
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


class WhatsAppNotReady(Exception):
    """Raised when the WhatsApp bridge cannot reach WhatsApp.app.

    Typical causes:
      * WhatsApp.app is not open.
      * The process running the inbox server has not been granted
        Accessibility permission in
        System Settings -> Privacy & Security -> Accessibility.

    After fixing the cause, the inbox server may need to be restarted
    so it picks up newly granted Accessibility permission.
    """


_INSTRUCTIONS = (
    "To make the WhatsApp bridge ready:\n"
    "  1. Open WhatsApp.app on this Mac and keep it running.\n"
    "  2. Grant Accessibility permission to the process hosting the\n"
    "     inbox server (System Settings -> Privacy & Security ->\n"
    "     Accessibility). You may need to restart the inbox server\n"
    "     after granting permission."
)


def _status_and_data(resp: Any) -> tuple[int, Any]:
    """Return (status_code, parsed_body) from an inbox_get/post response.

    The inbox tool may return a requests-style Response or already-parsed
    data. Handle both shapes so this wrapper is robust to either.
    """
    status = getattr(resp, "status_code", 200)
    json_fn = getattr(resp, "json", None)
    if callable(json_fn):
        try:
            return status, json_fn()
        except Exception:
            return status, None
    return status, resp


def check_ready() -> bool:
    """Probe the WhatsApp bridge. Returns True if it can reach WhatsApp.

    Raises WhatsAppNotReady if /whatsapp/contacts returns 403 or an empty
    payload, or if the inbox server cannot be reached at all.
    """
    try:
        resp = inbox_get("/whatsapp/contacts")
    except InboxError as exc:
        raise WhatsAppNotReady(
            "Could not reach the inbox server to check WhatsApp readiness: "
            f"{exc}\n{_INSTRUCTIONS}"
        ) from exc

    status, data = _status_and_data(resp)

    if status == 403:
        raise WhatsAppNotReady(
            "WhatsApp bridge returned 403 (forbidden).\n" + _INSTRUCTIONS
        )

    if not data:
        raise WhatsAppNotReady(
            "WhatsApp bridge returned no contacts. WhatsApp.app may be closed "
            "or no chats have been indexed yet.\n" + _INSTRUCTIONS
        )

    return True


def get_contacts() -> list:
    """Return the list of WhatsApp contacts visible to the bridge.

    Raises WhatsAppNotReady if the bridge is not ready.
    """
    try:
        resp = inbox_get("/whatsapp/contacts")
    except InboxError as exc:
        raise WhatsAppNotReady(
            f"Failed to fetch WhatsApp contacts: {exc}\n" + _INSTRUCTIONS
        ) from exc

    status, data = _status_and_data(resp)

    if status == 403:
        raise WhatsAppNotReady(
            "WhatsApp bridge returned 403 (forbidden).\n" + _INSTRUCTIONS
        )

    if not data:
        raise WhatsAppNotReady(
            "WhatsApp bridge returned an empty contact list.\n" + _INSTRUCTIONS
        )

    if not isinstance(data, list):
        raise WhatsAppNotReady(
            "Unexpected contacts payload from WhatsApp bridge: "
            f"{type(data).__name__}.\n" + _INSTRUCTIONS
        )

    return data


def get_thread(contact_id: str, limit: int = 20) -> list:
    """Return recent messages in a WhatsApp thread.

    Args:
        contact_id: The contact identifier returned by get_contacts().
        limit: Maximum number of messages to request from the server.

    Raises WhatsAppNotReady if the bridge is not ready. An empty thread is
    a valid result and is returned as an empty list.
    """
    try:
        resp = inbox_get(
            f"/whatsapp/messages/{contact_id}",
            params={"limit": limit},
        )
    except InboxError as exc:
        raise WhatsAppNotReady(
            f"Failed to fetch WhatsApp thread {contact_id!r}: {exc}\n"
            + _INSTRUCTIONS
        ) from exc

    status, data = _status_and_data(resp)

    if status == 403:
        raise WhatsAppNotReady(
            "WhatsApp bridge returned 403 (forbidden).\n" + _INSTRUCTIONS
        )

    if data is None:
        return []
    if not isinstance(data, list):
        raise WhatsAppNotReady(
            "Unexpected thread payload from WhatsApp bridge: "
            f"{type(data).__name__}.\n" + _INSTRUCTIONS
        )
    return data


def send(to: str, body: str) -> dict:
    """Send a WhatsApp message through the inbox server.

    This call is explicit and intentionally not gated by check_ready():
    the caller is asserting intent to send. A 403 from the bridge is
    still translated into WhatsAppNotReady with instructions.
    """
    try:
        resp = inbox_post(
            "/messages/send",
            json={"source": "whatsapp", "to": to, "body": body},
        )
    except InboxError as exc:
        raise WhatsAppNotReady(
            f"Failed to send WhatsApp message: {exc}\n" + _INSTRUCTIONS
        ) from exc

    status, data = _status_and_data(resp)

    if status == 403:
        raise WhatsAppNotReady(
            "WhatsApp bridge refused to send (403).\n" + _INSTRUCTIONS
        )

    if isinstance(data, dict):
        return data
    if data is None:
        return {}
    return {"result": data}
