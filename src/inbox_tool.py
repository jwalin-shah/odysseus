import json
import ssl
import subprocess
import urllib.request
import urllib.parse
import os
from typing import Any, Optional

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
    token = get_token()
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise InboxError(f"HTTP {e.code} {e.reason} for {method} {path}")
    except urllib.error.URLError as e:
        raise InboxError(f"Connection failed to {url}: {e.reason}")


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


def get_imessage_thread(chat_id: str, limit: int = 50) -> list:
    result = inbox_get(f"/imessage/messages/{chat_id}", {"limit": limit})
    return result if isinstance(result, list) else result.get("messages", [])


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
