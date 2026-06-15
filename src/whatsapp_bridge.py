"""Thin wrapper around the inbox server's WhatsApp routes.

The inbox server (default: http://localhost:9849) exposes a small set of
WhatsApp endpoints that this module wraps in a Pythonic interface. The
underlying transport is HTTP; WhatsApp itself runs in WhatsApp.app on macOS
and is driven via the Accessibility permission that the inbox server holds.

Typical usage::

    from src.whatsapp_bridge import (
        WhatsAppNotReady, check_ready, get_contacts, get_thread, send,
    )

    if not check_ready():
        raise SystemExit("WhatsApp not ready; see instructions.")

    for contact in get_contacts():
        messages = get_thread(contact["id"], limit=20)
        ...

    send(to="+15555550100", body="hi from the agent")
"""

from __future__ import annotations

from typing import Any

from src.inbox_tool import inbox_get, inbox_post, InboxError


__all__ = [
    "WhatsAppNotReady",
    "check_ready",
    "get_contacts",
    "get_thread",
    "send",
]


# Endpoint paths on the inbox server. Kept as module-level constants so a
# future move of the inbox server only requires changing these in one place.
_CONTACTS_PATH = "/whatsapp/contacts"
_THREAD_PATH = "/whatsapp/messages/{contact_id}"
_SEND_PATH = "/messages/send"


class WhatsAppNotReady(Exception):
    """Raised when the inbox server reports WhatsApp is not usable.

    Almost always caused by one of:
      * WhatsApp.app is not running on this Mac, or
      * The host process serving the inbox server does not have
        Accessibility permission in System Settings.

    The exception message includes remediation steps the caller can surface
    to the human.
    """


# Human-readable remediation steps. Kept here (rather than inlined at every
# raise site) so the wording stays consistent across the API.
_INSTRUCTIONS = (
    "WhatsApp is not ready. To fix this:\n"
    "  1. Open WhatsApp.app on this Mac.\n"
    "  2. Open System Settings -> Privacy & Security -> Accessibility.\n"
    "  3. Enable the inbox server host (the entry that matches the process\n"
    "     serving http://localhost:9849).\n"
    "  4. Retry the operation."
)


def _raise_not_ready(reason: str) -> None:
    """Raise ``WhatsAppNotReady`` with ``reason`` and the standard instructions."""
    raise WhatsAppNotReady(f"{reason}\n\n{_INSTRUCTIONS}")


def _payload(resp: Any) -> Any:
    """Return the JSON body of ``resp`` if it has one, else ``resp`` itself.

    The inbox server's HTTP layer is expected to return an object that
    behaves like a ``requests.Response`` (has ``.json()`` and
    ``.status_code``), but tests and a few callers sometimes hand in a
    parsed ``dict``/``list`` directly. This helper makes the read-side
    functions tolerate both shapes.
    """
    return resp.json() if hasattr(resp, "json") else resp


def _is_envelope(payload: Any, key: str) -> bool:
    """Return True if ``payload`` looks like ``{key: [...]}``."""
    return isinstance(payload, dict) and key in payload and isinstance(payload[key], list)


def check_ready() -> bool:
    """Return ``True`` iff the inbox server can talk to WhatsApp.

    Performs a lightweight probe by fetching ``GET /whatsapp/contacts``. A
    403 response or an empty contact list both indicate WhatsApp is not
    ready and the function returns ``False``.

    Transport-level failures (server down, timeout, DNS error, ...) are
    *not* treated as "not ready" and are propagated as ``InboxError`` so
    the caller can distinguish "WhatsApp is unreachable because of macOS
    permissions" from "the inbox server itself is down".
    """
    resp = inbox_get(_CONTACTS_PATH)

    if getattr(resp, "status_code", 200) == 403:
        return False

    data = _payload(resp)
    if _is_envelope(data, "contacts"):
        data = data["contacts"]
    return bool(data)


def get_contacts() -> list:
    """Return the list of WhatsApp contacts.

    Raises ``WhatsAppNotReady`` if the inbox server reports WhatsApp is not
    usable (HTTP 403) or if it returns an empty contact list. The latter is
    treated as "not ready" rather than "you have no contacts" because an
    uninitialised WhatsApp session on the inbox server side manifests as
    an empty list, and the remediation is the same.
    """
    resp = inbox_get(_CONTACTS_PATH)

    if getattr(resp, "status_code", 200) == 403:
        _raise_not_ready("Inbox server returned 403 for /whatsapp/contacts.")

    data = _payload(resp)
    if _is_envelope(data, "contacts"):
        data = data["contacts"]

    if not data:
        _raise_not_ready("Inbox server returned no contacts.")

    return list(data)


def get_thread(contact_id: str, limit: int = 20) -> list:
    """Return the most recent ``limit`` messages in a WhatsApp thread.

    ``contact_id`` is the opaque identifier returned by ``get_contacts``
    (a phone number, a JID, or whatever shape the inbox server exposes).
    The order of the returned list is whatever the inbox server provides;
    downstream code is expected to treat the result as an untrusted view
    of the conversation.

    A 403 response from the inbox server is treated the same as for
    contacts: WhatsApp is not ready, so ``WhatsAppNotReady`` is raised.
    An empty thread is *not* treated as a failure -- it is a legitimate
    state for a contact the user has never messaged.
    """
    if not contact_id:
        raise ValueError("contact_id is required")
    if limit <= 0:
        raise ValueError("limit must be positive")

    path = _THREAD_PATH.format(contact_id=contact_id)
    # Pass `limit` as a query parameter so the server can avoid
    # serialising messages we are going to drop client-side. If the server
    # ignores unknown query params it is harmless.
    resp = inbox_get(path, params={"limit": limit})

    if getattr(resp, "status_code", 200) == 403:
        _raise_not_ready(
            f"Inbox server returned 403 for thread of contact {contact_id!r}."
        )

    data = _payload(resp)
    if _is_envelope(data, "messages"):
        data = data["messages"]
    return list(data or [])


def send(to: str, body: str) -> dict:
    """Send a WhatsApp message and return the inbox server's response.

    Unlike the read-side helpers, this function is intentionally NOT gated
    by a readiness check: it is a side-effecting action and the caller must
    opt in explicitly (typically by being a tool the agent has chosen to
    invoke). The inbox server still requires WhatsApp to actually be ready,
    so a 403 here will surface as ``InboxError`` from the transport layer
    rather than ``WhatsAppNotReady``.

    Parameters
    ----------
    to:
        Destination identifier. The inbox server's spec uses raw phone
        numbers (``+15555550100``) or JIDs.
    body:
        Plain-text message body.
    """
    if not to:
        raise ValueError("`to` is required")
    if not body:
        raise ValueError("`body` is required")

    payload = {"source": "whatsapp", "to": to, "body": body}
    resp = inbox_post(_SEND_PATH, json=payload)

    result = _payload(resp)
    # The inbox server is expected to return a dict describing the sent
    # message (id, timestamp, ...). If it returns something else, wrap it
    # so the caller still gets a dict per the function contract.
    return result if isinstance(result, dict) else {"raw": result}
