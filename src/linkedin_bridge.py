"""Wrapper for LinkedIn data via the inbox server.

LinkedIn data is collected by a CDP-based scraper that runs inside the
inbox server on ``localhost:9849``. The scraper is gated behind the
``INBOX_ENABLE_LINKEDIN_SCRAPER=1`` environment variable; if that
variable is not set, the server rejects every LinkedIn request and this
module raises :class:`LinkedInScannerOff` with a hint on how to enable
it.

Endpoints used:
    GET  /linkedin/dms              -> recent DMs
    GET  /linkedin/connections      -> recent connections
    GET  /linkedin/profile/{person} -> profile info
    POST /linkedin/dm               -> send a DM
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from src.inbox_tool import inbox_get, inbox_post, InboxError


SCANNER_ENV_VAR = "INBOX_ENABLE_LINKEDIN_SCRAPER"
SCANNER_ENABLED_VALUE = "1"

_OFF_HINT = (
    f"LinkedIn scanner is not enabled. Set {SCANNER_ENV_VAR}="
    f"{SCANNER_ENABLED_VALUE} in the inbox server's environment and "
    "restart it."
)


class LinkedInScannerOff(Exception):
    """Raised when the LinkedIn scraper is not enabled on the inbox server.

    The CDP-based LinkedIn scraper is gated behind the
    ``INBOX_ENABLE_LINKEDIN_SCRAPER=1`` environment variable on the
    inbox server. To use the helpers in this module, set that variable
    in the inbox server's environment and restart it.
    """

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message or _OFF_HINT)


def check_enabled() -> bool:
    """Return ``True`` if the LinkedIn scanner is enabled locally.

    Reads the same ``INBOX_ENABLE_LINKEDIN_SCRAPER`` flag the inbox
    server looks at. The bridge and the server are expected to share
    the relevant environment for LinkedIn access to work.
    """
    return os.environ.get(SCANNER_ENV_VAR) == SCANNER_ENABLED_VALUE


def _require_scanner() -> None:
    if not check_enabled():
        raise LinkedInScannerOff()


def _coerce_list(payload: Any) -> List[dict]:
    """Normalize an inbox server response into a list of dicts."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("messages", "dms", "connections", "items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def get_dms(limit: int = 10) -> List[dict]:
    """Return the most recent LinkedIn DMs (capped at ``limit``)."""
    _require_scanner()
    try:
        payload = inbox_get("/linkedin/dms", params={"limit": limit})
    except InboxError as exc:
        raise LinkedInScannerOff(
            f"Inbox server rejected GET /linkedin/dms: {exc}. " + _OFF_HINT
        ) from exc
    return _coerce_list(payload)[:limit]


def get_connections(limit: int = 20) -> List[dict]:
    """Return the most recent LinkedIn connections (capped at ``limit``)."""
    _require_scanner()
    try:
        payload = inbox_get("/linkedin/connections", params={"limit": limit})
    except InboxError as exc:
        raise LinkedInScannerOff(
            f"Inbox server rejected GET /linkedin/connections: {exc}. "
            + _OFF_HINT
        ) from exc
    return _coerce_list(payload)[:limit]


def get_profile(person: str) -> Dict[str, Any]:
    """Return LinkedIn profile info for ``person`` (name or vanity slug)."""
    _require_scanner()
    if not person:
        raise ValueError("person is required")
    try:
        return dict(inbox_get(f"/linkedin/profile/{person}"))
    except InboxError as exc:
        raise LinkedInScannerOff(
            f"Inbox server rejected GET /linkedin/profile/{person}: {exc}. "
            + _OFF_HINT
        ) from exc


def send_dm(connection_id: str, message: str) -> Dict[str, Any]:
    """Send ``message`` to the LinkedIn connection ``connection_id``."""
    _require_scanner()
    if not connection_id:
        raise ValueError("connection_id is required")
    if not message:
        raise ValueError("message is required")
    try:
        return dict(
            inbox_post(
                "/linkedin/dm",
                json={"connection_id": connection_id, "message": message},
            )
        )
    except InboxError as exc:
        raise LinkedInScannerOff(
            f"Inbox server rejected POST /linkedin/dm to {connection_id!r}: "
            f"{exc}. " + _OFF_HINT
        ) from exc


__all__ = [
    "LinkedInScannerOff",
    "check_enabled",
    "get_dms",
    "get_connections",
    "get_profile",
    "send_dm",
]
