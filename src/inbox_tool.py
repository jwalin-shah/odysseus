import json
import subprocess
import time
import urllib.request
import urllib.parse
import urllib.error
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
        if result.returncode == 0:
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
        separator = "&" if "?" in path else "?"
        path = path + separator + urllib.parse.urlencode(params)
    return _request("GET", path)


def inbox_post(path: str, body: dict) -> Any:
    return _request("POST", path, body)


# --- High-level helpers ---

def get_imessage_contacts(limit: int = 20) -> list:
    result = inbox_get("/imessage/contacts", {"limit": limit})
    contacts = result if isinstance(result, list) else result.get("contacts", result.get("data", []))
    return contacts[:limit]


def get_imessage_thread(chat_id: Union[int, str], limit: int = 50) -> list:
    """Fetch messages from an iMessage thread.

    Accepts chat_id as either int (handle_id) or str (chat_identifier);
    the value is coerced to str for the URL path segment.
    """
    chat_id_str = urllib.parse.quote(str(chat_id), safe="")
    result = inbox_get(f"/imessage/messages/{chat_id_str}", {"limit": limit})
    return result if isinstance(result, list) else result.get("messages", [])
