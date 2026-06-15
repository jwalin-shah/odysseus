# src/linkedin_bridge.py
"""Wrapper for LinkedIn data exposed by the inbox server.

The LinkedIn scanner runs inside the CDP-based inbox server and must be
explicitly enabled with the INBOX_ENABLE_LINKEDIN_SCRAPER=1 environment
variable. When disabled, every public function raises LinkedInScannerOff
with a message describing how to turn it on.
"""

import os
from typing import Any, Dict, List, Optional

from src.inbox_tool import inbox_get, inbox_post, InboxError

BASE_URL = "http://localhost:9849"
ENABLE_ENV_VAR = "INBOX_ENABLE_LINKEDIN_SCRAPER"


class LinkedInScannerOff(Exception):
    """Raised when the LinkedIn CDP scanner is not enabled.

    To enable it, set INBOX_ENABLE_LINKEDIN_SCRAPER=1 in the environment
    before launching the inbox server.
    """

    DEFAULT_MESSAGE = (
        "LinkedIn scanner is disabled. Set the {env}=1 environment "
        "variable and restart the inbox server to enable it."
    ).format(env=ENABLE_ENV_VAR)

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message or self.DEFAULT_MESSAGE)


def check_enabled() -> bool:
    """Return True if the LinkedIn scanner env var is set to '1'."""
    return os.environ.get(ENABLE_ENV_VAR) == "1"


def _ensure_enabled() -> None:
    """Raise LinkedInScannerOff when the scanner is not enabled."""
    if not check_enabled():
        raise LinkedInScannerOff()


def _extract_list(payload: Any, *keys: str) -> list:
    """Best-effort extraction of a list from a server response."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def get_dms(limit: int = 10) -> list:
    """Fetch the most recent LinkedIn DMs from the inbox server."""
    _ensure_enabled()
    response = inbox_get(
        f"{BASE_URL}/linkedin/dms",
        params={"limit": limit},
    )
    return _extract_list(response, "dms", "messages", "items")


def get_connections(limit: int = 20) -> list:
    """Fetch the most recent LinkedIn connections from the inbox server."""
    _ensure_enabled()
    response = inbox_get(
        f"{BASE_URL}/linkedin/connections",
        params={"limit": limit},
    )
    return _extract_list(response, "connections", "items")


def get_profile(person: str) -> dict:
    """Fetch LinkedIn profile information for the given person."""
    _ensure_enabled()
    response = inbox_get(f"{BASE_URL}/linkedin/profile/{person}")
    if isinstance(response, dict):
        return response.get("profile", response)
    return {}


def send_dm(connection_id: str, message: str) -> dict:
    """Send a DM to a LinkedIn connection.

    Returns the server response, typically containing a status / id field.
    Raises LinkedInScannerOff if the scanner is disabled, and InboxError
    for any transport-level failure.
    """
    _ensure_enabled()
    response = inbox_post(
        f"{BASE_URL}/linkedin/dm",
        json={"connection_id": connection_id, "message": message},
    )
    if isinstance(response, dict):
        return response
    return {"result": response}
