"""Thin wrapper around the inbox server's LinkedIn endpoints.

LinkedIn data is produced by a CDP-based scraper that runs inside the
inbox process. The scraper is feature-flagged by the
``INBOX_ENABLE_LINKEDIN_SCRAPER`` environment variable — when it is not
set to ``"1"`` the LinkedIn routes are not registered, and the helpers in
this module will raise :class:`LinkedInScannerOff` with instructions on
how to turn the scanner on.

Server (inbox process) listens on ``http://localhost:9849`` and exposes::

    GET  /linkedin/dms                 -> recent DMs
    GET  /linkedin/connections         -> recent connections
    GET  /linkedin/profile/{person}    -> profile info
    POST /linkedin/dm                  -> send a DM
"""

from __future__ import annotations

import os
from typing import Any

from src.inbox_tool import inbox_get, inbox_post, InboxError


_BASE_URL = "http://localhost:9849"
_ENABLE_ENV = "INBOX_ENABLE_LINKEDIN_SCRAPER"
_ENABLE_VALUE = "1"


class LinkedInScannerOff(Exception):
    """Raised when a LinkedIn helper is called but the scanner is off.

    Enable the scanner by exporting ``INBOX_ENABLE_LINKEDIN_SCRAPER=1`` in
    the environment that starts the inbox server, then restart the
    inbox process, e.g.::

        INBOX_ENABLE_LINKEDIN_SCRAPER=1 inbox-server

    or via the ``.env`` file consumed by the inbox process::

        INBOX_ENABLE_LINKEDIN_SCRAPER=1
    """


def check_enabled() -> bool:
    """Return ``True`` iff ``INBOX_ENABLE_LINKEDIN_SCRAPER=1`` is set."""
    return os.environ.get(_ENABLE_ENV) == _ENABLE_VALUE


def _require_enabled() -> None:
    """Raise :class:`LinkedInScannerOff` when the scanner flag is missing."""
    if not check_enabled():
        raise LinkedInScannerOff(
            "LinkedIn scanner is disabled. Set INBOX_ENABLE_LINKEDIN_SCRAPER=1 "
            "in the environment that runs the inbox server and restart it "
            "before calling LinkedIn bridge helpers."
        )


def _wrap_inbox_error(action: str, exc: InboxError) -> LinkedInScannerOff:
    """Translate an :class:`InboxError` into a :class:`LinkedInScannerOff`.

    The inbox server returns errors for every LinkedIn route when the
    scanner is disabled, so any failure on a LinkedIn call is almost
    always a configuration problem rather than a transient network one.
    """
    return LinkedInScannerOff(
        f"Inbox server refused the LinkedIn {action} — is "
        f"INBOX_ENABLE_LINKEDIN_SCRAPER=1 set on the inbox process? "
        f"Underlying error: {exc}"
    )


def get_dms(limit: int = 10) -> list[dict[str, Any]]:
    """Return up to ``limit`` recent LinkedIn DMs."""
    _require_enabled()
    try:
        return inbox_get(f"{_BASE_URL}/linkedin/dms", params={"limit": limit})
    except InboxError as exc:
        raise _wrap_inbox_error("DM fetch", exc) from exc


def get_connections(limit: int = 20) -> list[dict[str, Any]]:
    """Return up to ``limit`` recent LinkedIn connections."""
    _require_enabled()
    try:
        return inbox_get(
            f"{_BASE_URL}/linkedin/connections",
            params={"limit": limit},
        )
    except InboxError as exc:
        raise _wrap_inbox_error("connections fetch", exc) from exc


def get_profile(person: str) -> dict[str, Any]:
    """Return profile info for ``person`` (vanity slug or user id)."""
    _require_enabled()
    try:
        return inbox_get(f"{_BASE_URL}/linkedin/profile/{person}")
    except InboxError as exc:
        raise _wrap_inbox_error("profile fetch", exc) from exc


def send_dm(connection_id: str, message: str) -> dict[str, Any]]:
    """Send ``message`` to ``connection_id`` and return the server response."""
    _require_enabled()
    try:
        return inbox_post(
            f"{_BASE_URL}/linkedin/dm",
            json={"connection_id": connection_id, "message": message},
        )
    except InboxError as exc:
        raise _wrap_inbox_error("DM send", exc) from exc
