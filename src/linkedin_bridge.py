"""Thin wrapper around the inbox server's LinkedIn endpoints.

The inbox server runs a CDP-based LinkedIn scraper that is gated behind
the ``INBOX_ENABLE_LINKEDIN_SCRAPER`` environment variable. When the
variable is not set to ``"1"``, every /linkedin/* route returns an error
— so we detect that locally and raise :class:`LinkedInScannerOff` with
actionable instructions, rather than letting a generic HTTP failure
bubble up.

Routes consumed (server listens on ``localhost:9849``):

* ``GET  /linkedin/dms``            → :func:`get_dms`
* ``GET  /linkedin/connections``    → :func:`get_connections`
* ``GET  /linkedin/profile/{p}``   → :func:`get_profile`
* ``POST /linkedin/send_dm``        → :func:`send_dm`
"""

from __future__ import annotations

import os

from src.inbox_tool import inbox_get, inbox_post, InboxError

# Server config ---------------------------------------------------------------

BASE_URL = "http://localhost:9849"
ENABLE_ENV_VAR = "INBOX_ENABLE_LINKEDIN_SCRAPER"


# Exceptions ------------------------------------------------------------------

class LinkedInScannerOff(Exception):
    """The inbox server's LinkedIn scraper is not enabled.

    The scraper is gated behind ``INBOX_ENABLE_LINKEDIN_SCRAPER`` on the
    *server* side. Set it to ``1`` in the server's environment and
    restart the server to enable the ``/linkedin/*`` routes.
    """

    DEFAULT_MESSAGE = (
        "LinkedIn scanner is disabled on the inbox server. "
        f"Set {ENABLE_ENV_VAR}=1 in the inbox server's environment "
        "and restart it to enable /linkedin/* routes."
    )

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.DEFAULT_MESSAGE)


# Internal helpers ------------------------------------------------------------

def _is_enabled() -> bool:
    """Local env-var check — does not touch the network."""
    return os.environ.get(ENABLE_ENV_VAR) == "1"


def _require_enabled() -> None:
    """Raise :class:`LinkedInScannerOff` if the scraper is gated off."""
    if not _is_enabled():
        raise LinkedInScannerOff()


# Public API ------------------------------------------------------------------

def check_enabled() -> bool:
    """Return ``True`` if the LinkedIn scraper is opted in via env var.

    This is a *local* check only — it reads ``INBOX_ENABLE_LINKEDIN_SCRAPER``
    from this process's environment. It does **not** ping the inbox server,
    so a ``True`` return value does not guarantee the server is actually
    reachable.
    """
    return _is_enabled()


def get_dms(limit: int = 10) -> list:
    """Fetch the most recent LinkedIn DMs from the inbox server.

    Args:
        limit: Maximum number of DMs to return (server-side cap).

    Returns:
        A list of DM objects as decoded from the server's JSON response.

    Raises:
        LinkedInScannerOff: If ``INBOX_ENABLE_LINKEDIN_SCRAPER`` is not set.
        InboxError: On transport / HTTP errors from the inbox server.
    """
    _require_enabled()
    return inbox_get(f"{BASE_URL}/linkedin/dms", params={"limit": limit})


def get_connections(limit: int = 20) -> list:
    """Fetch recent LinkedIn connections from the inbox server.

    Args:
        limit: Maximum number of connections to return (server-side cap).

    Returns:
        A list of connection objects as decoded from the server's JSON.

    Raises:
        LinkedInScannerOff: If the scraper is not enabled.
        InboxError: On transport / HTTP errors.
    """
    _require_enabled()
    return inbox_get(f"{BASE_URL}/linkedin/connections", params={"limit": limit})


def get_profile(person: str) -> dict:
    """Fetch LinkedIn profile info for the given person slug/id.

    Args:
        person: The LinkedIn vanity slug, public id, or other identifier
            accepted by the inbox server.

    Returns:
        A profile dict as decoded from the server's JSON response.

    Raises:
        LinkedInScannerOff: If the scraper is not enabled.
        InboxError: On transport / HTTP errors.
    """
    _require_enabled()
    # Note: `person` is interpolated into the path; callers should pass a
    # trusted slug. If untrusted input is ever supported, URL-encode it.
    return inbox_get(f"{BASE_URL}/linkedin/profile/{person}")


def send_dm(connection_id: str, message: str) -> dict:
    """Send a DM to the given LinkedIn connection.

    Args:
        connection_id: The recipient's LinkedIn connection id (as returned
            by :func:`get_connections`).
        message: The DM body to send.

    Returns:
        The server's JSON response describing the sent message (typically
        an id, timestamp, and delivery status).

    Raises:
        LinkedInScannerOff: If the scraper is not enabled.
        InboxError: On transport / HTTP errors.
    """
    _require_enabled()
    return inbox_post(
        f"{BASE_URL}/linkedin/send_dm",
        json={"connection_id": connection_id, "message": message},
    )
