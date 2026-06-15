"""Thin wrapper around the inbox server's WhatsApp routes.

The inbox server (default: http://localhost:9849) must be running with
WhatsApp.app open and Accessibility permission granted on macOS:

    System Settings -> Privacy & Security -> Accessibility
"""
from src.inbox_tool import InboxError, inbox_get, inbox_post


_INSTRUCTIONS = (
    "WhatsApp bridge is not ready. On macOS, ensure:\n"
    "  1. WhatsApp.app is open and signed in.\n"
    "  2. Accessibility permission is granted to this terminal/host app\n"
    "     (System Settings -> Privacy & Security -> Accessibility).\n"
    "Then retry the operation."
)


class WhatsAppNotReady(Exception):
    """Raised when the WhatsApp bridge is unavailable.

    Common causes: WhatsApp.app is closed/not signed in, Accessibility
    permission has not been granted, or the inbox server returned an
    empty contact list.
    """

    def __init__(
        self,
        message: str = _INSTRUCTIONS,
        *,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause


def _status_of(err: InboxError) -> int | None:
    """Best-effort extraction of HTTP status code from an InboxError."""
    return getattr(err, "status_code", None) or getattr(err, "code", None)


def check_ready() -> bool:
    """Return True iff /whatsapp/contacts succeeds and is non-empty.

    Never raises: readiness issues collapse to False so callers can probe
    the bridge without try/except boilerplate.
    """
    try:
        return bool(get_contacts())
    except (WhatsAppNotReady, InboxError):
        return False


def get_contacts() -> list:
    """Return the list of WhatsApp contacts from the inbox server.

    Raises:
        WhatsAppNotReady: if the server returns 403 (typically Accessibility
            permission missing) or an empty contact list.
        InboxError: for any other transport/server error.
    """
    try:
        data = inbox_get("/whatsapp/contacts")
    except InboxError as e:
        if _status_of(e) == 403:
            raise WhatsAppNotReady(cause=e) from e
        raise

    # Tolerate either {"contacts": [...]} or a bare list response.
    contacts = data.get("contacts", data) if isinstance(data, dict) else data
    if not contacts:
        raise WhatsAppNotReady(
            "WhatsApp returned no contacts. Is WhatsApp.app open and signed in?"
        )
    return list(contacts)


def get_thread(contact_id: str, limit: int = 20) -> list:
    """Return up to ``limit`` messages from a contact's WhatsApp thread.

    Raises:
        WhatsAppNotReady: if the inbox server returns 403 (same permission
            requirement as ``get_contacts``).
        InboxError: for any other transport/server error.
    """
    path = f"/whatsapp/messages/{contact_id}"
    try:
        data = inbox_get(path, params={"limit": limit})
    except InboxError as e:
        if _status_of(e) == 403:
            raise WhatsAppNotReady(cause=e) from e
        raise

    messages = data.get("messages", data) if isinstance(data, dict) else data
    return list(messages)


def send(to: str, body: str) -> dict:
    """Send a WhatsApp message via ``POST /messages/send``.

    This function is intentionally NOT gated by readiness checks — sending
    is treated as an explicit user-initiated action. The caller is
    responsible for confirming intent and handling transport failures.
    """
    return inbox_post(
        "/messages/send",
        {"source": "whatsapp", "to": to, "body": body},
    )
