import json
import ssl
import subprocess
import time
import urllib.request
import urllib.parse
import os
from typing import Any, Optional, Union

BASE_URL = os.environ.get("INBOX_URL", "http://localhost:9849")


class InboxError(Exception):
    pass


def get_token() -> str:
    token = os.environ.get("INBOX_SERVER_TOKEN", "")
    if token:
        return token
    try:
        result = subprocess.run(
            ["infisical", "secrets", "get", "server_token",
             "--path", "/providers/inbox", "--env", "dev", "--plain"],
            capture_output=True, text=True, timeout=10
        )
        token = result.stdout.strip()
        if token:
            os.environ["INBOX_SERVER_TOKEN"] = token
            return token
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    raise InboxError("INBOX_SERVER_TOKEN not set and Infisical lookup failed")


def _request(method: str, path: str, body: Optional[dict] = None) -> Any:
    """HTTP request with retry logic for transient connection failures.

    Retries up to 3 times on URLError (DNS failure, connection refused,
    network unreachable, etc.) with a 2 second backoff between attempts.
    HTTPError responses are not retried — they indicate a real server reply.
    """
    token = get_token()
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # Server replied with a non-2xx — retrying won't help.
            raise InboxError(f"HTTP {e.code} {e.reason} for {method} {path}")
        except urllib.error.URLError as e:
            last_error = e
            if attempt < 2:  # don't sleep after the final attempt
                time.sleep(2)

    reason = getattr(last_error, "reason", "unknown") if last_error else "unknown"
    raise InboxError(f"Connection failed to {url} after 3 attempts: {reason}")


def inbox_get(path: str, params: Optional[dict] = None) -> Any:
    if params:
        path = path + "?" + urllib.parse.urlencode(params)
    return _request("GET", path)


def inbox_post(path: str, body: dict) -> Any:
    return _request("POST", path, body)


# --- High-level helpers ---

def get_imessage_contacts(limit: int = 20) -> list:
    result = inbox_get("/imessage/contacts")
    contacts = result if isinstance(result, list) else result.get("contacts", result.get("data", []))
    return contacts[:limit]


def get_imessage_thread(chat_id: Union[int, str], limit: int = 50) -> list:
    """Fetch messages from an iMessage thread.

    Accepts chat_id as either int (handle_id) or str (chat_identifier);
    the value is coerced to str for the URL path segment.
    """
    chat_id_str = str(chat_id)
    result = inbox_get(f"/imessage/messages/{chat_id_str}", {"limit": limit})
    return result if isinstance(result, list) else result.get("messages", [])


def search_imessage(query: str) -> list:
    """Full-text search across iMessage messages."""
    result = inbox_get("/imessage/search", {"q": query})
    return result if isinstance(result, list) else result.get("messages", result.get("results", result.get("data", [])))


def get_imessage_unread() -> list:
    """Return per-chat unread counts (or list of unread messages, server-dependent)."""
    result = inbox_get("/imessage/unread")
    return result if isinstance(result, list) else result.get("chats", result.get("unread", result.get("data", [])))


def get_recent_threads(limit: int = 5) -> list[dict]:
    """Return the most recently active iMessage threads.

    Fetches a larger pool of contacts, sorts them by the timestamp of their
    last message, then retrieves a small slice of recent messages for each
    of the top ``limit`` threads. Each returned dict has:

        {
            "contact":       <contact dict from /imessage/contacts>,
            "chat_id":       <str chat_identifier or int handle_id>,
            "display_name":  <str>,
            "unread_count":  <int>,
            "messages":      [<message dict>, ...]   # most recent first
        }
    """
    # Pull a wider set so we can sort by recency before truncating.
    pool_size = max(limit * 4, 20)
    contacts = get_imessage_contacts(limit=pool_size)

    def last_activity(c: dict) -> str:
        """Best-effort timestamp extraction from a contact's last_message field."""
        last = c.get("last_message")
        if isinstance(last, dict):
            return str(
                last.get("timestamp")
                or last.get("date")
                or last.get("created_at")
                or last.get("time")
                or ""
            )
        # last_message might be a plain string (the body) — fall back to 0
        return ""

    sorted_contacts = sorted(contacts, key=last_activity, reverse=True)
    top_contacts = sorted_contacts[:limit]

    threads: list[dict] = []
    for contact in top_contacts:
        chat_id = contact.get("chat_identifier") or contact.get("handle_id")
        if chat_id is None:
            continue
        try:
            messages = get_imessage_thread(chat_id, limit=5)
        except InboxError:
            # One bad thread shouldn't kill the whole result set.
            messages = []

        display = (
            contact.get("display_name")
            or contact.get("chat_identifier")
            or contact.get("handle_id")
            or "Unknown"
        )

        threads.append({
            "contact": contact,
            "chat_id": chat_id,
            "display_name": str(display),
            "unread_count": int(contact.get("unread_count", 0) or 0),
            "messages": messages,
        })

    return threads


def format_thread_summary(thread: list[dict]) -> str:
    """Render a list of iMessage message dicts as a human-readable chat log.

    Tolerates a few common field name variations (body/text, sender/from,
    timestamp/date/created_at) and uses ``is_from_me`` to label outbound
    messages as ``Me`` when present.
    """
    if not thread:
        return "(empty thread)"

    lines: list[str] = []
    for msg in thread:
        sender = (
            msg.get("sender")
            or msg.get("sender_name")
            or msg.get("from")
            or "Unknown"
        )
        text = msg.get("body") or msg.get("text") or ""
        timestamp = (
            msg.get("timestamp")
            or msg.get("date")
            or msg.get("created_at")
            or ""
        )

        if isinstance(msg.get("is_from_me"), bool):
            prefix = "Me" if msg["is_from_me"] else str(sender)
        else:
            prefix = str(sender)

        line = f"[{timestamp}] {prefix}: {text}" if timestamp else f"{prefix}: {text}"
        lines.append(line)

    return "\n".join(lines)


def get_calendar_upcoming(days: int = 7) -> list:
    result = inbox_get("/calendar/upcoming", {"days": days})
    return result if isinstance(result, list) else result.get("events", [])


def get_gmail_unread(limit: int = 10) -> list:
    result = inbox_get("/messages/gmail/", {"limit": limit, "unread": True})
    return result if isinstance(result, list) else result.get("threads", result.get("messages", []))


def send_imessage(contact: str, text: str) -> dict:
    return inbox_post("/messages/send", {"source": "imessage", "to": contact, "body": text})


def send_whatsapp(contact: str, text: str) -> dict:
    return inbox_post("/messages/send", {"source": "whatsapp", "to": contact, "body": text})


def send_email(to: str, subject: str, body: str, account: Optional[str] = None) -> dict:
    payload: dict = {"to": to, "subject": subject, "body": body}
    if account:
        payload["account"] = account
    return inbox_post("/gmail/send", payload)


def get_linkedin_dms(limit: int = 10) -> list:
    result = inbox_get("/linkedin/dms", {"limit": limit})
    return result if isinstance(result, list) else result.get("dms", [])


def search_gmail(query: str, limit: int = 10) -> list:
    result = inbox_get("/messages/gmail/", {"q": query, "limit": limit})
    return result if isinstance(result, list) else result.get("threads", [])
