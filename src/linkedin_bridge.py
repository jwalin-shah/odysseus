"""Wrapper around the inbox server's LinkedIn endpoints.

The inbox server (default: http://localhost:9849) only exposes LinkedIn data
when started with ``INBOX_ENABLE_LINKEDIN_SCRAPER=1`` in its environment. Every
public function in this module raises :class:`LinkedInScannerOff` when the
scraper is disabled, with a message telling the caller how to enable it.
"""
from src.inbox_tool import inbox_get, InboxError


BASE_URL = "http://localhost:9849"


class LinkedInScannerOff(Exception):
    """The inbox server's LinkedIn scraper is not enabled.

    Start the inbox server with ``INBOX_ENABLE_LINKEDIN_SCRAPER=1`` set in its
    environment to enable it.
    """


def _off_message() -> str:
    return (
        "LinkedIn scraper is disabled on the inbox server. "
        "Restart it with INBOX_ENABLE_LINKEDIN_SCRAPER=1 set in its environment."
    )


def check_enabled() -> bool:
    """Probe the inbox server and return True iff the LinkedIn scraper is on."""
    try:
        inbox_get(f"{BASE_URL}/linkedin/dms", params={"limit": 1})
        return True
    except InboxError:
        return False


def get_dms(limit: int = 10) -> list:
    """Return up to ``limit`` recent LinkedIn DMs."""
    if not check_enabled():
        raise LinkedInScannerOff(_off_message())
    return (
        inbox_get(f"{BASE_URL}/linkedin/dms", params={"limit": limit}).get("dms", [])
    )


def get_connections(limit: int = 20) -> list:
    """Return up to ``limit`` recent LinkedIn connections."""
    if not check_enabled():
        raise LinkedInScannerOff(_off_message())
    return (
        inbox_get(f"{BASE_URL}/linkedin/connections", params={"limit": limit})
        .get("connections", [])
    )


def send_dm(connection_id: str, message: str) -> dict:
    """Send ``message`` to the LinkedIn connection identified by ``connection_id``."""
    if not check_enabled():
        raise LinkedInScannerOff(_off_message())
    return inbox_get(
        f"{BASE_URL}/linkedin/dm/send",
        params={"connection_id": connection_id, "message": message},
        method="POST",
    )
