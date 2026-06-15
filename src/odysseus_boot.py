"""
Odysseus boot checker.

Runs a set of fast, parallel health checks (3s timeout each) against the
services Odysseus depends on and prints a colored status table to stdout.

Returns a dict mapping service name -> True / False / "skip".
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GREY = "\033[90m"

    @classmethod
    def disable(cls) -> None:
        """Strip all color codes (no TTY or NO_COLOR set)."""
        for attr in list(vars(cls)):
            if attr.isupper() and isinstance(getattr(cls, attr), str):
                setattr(cls, attr, "")


# Honor NO_COLOR and non-TTY stdout
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    C.disable()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TIMEOUT_S = 3.0

INBOX_URL = os.environ.get(
    "ODYSSEUS_INBOX_URL", "http://localhost:9849/health"
)
TOKENROUTER_URL = os.environ.get(
    "ODYSSEUS_TOKENROUTER_URL", "http://localhost:9848/v1/messages"
)
TOKENROUTER_MODEL = os.environ.get("ODYSSEUS_TOKENROUTER_MODEL", "MiniMax-M3")
TOKENROUTER_TOKEN = os.environ.get("ODYSSEUS_TOKENROUTER_TOKEN", "")

IMESSAGE_DB = Path.home() / "Library" / "Messages" / "chat.db"


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_inbox() -> bool:
    """GET http://localhost:9849/health, expect a 2xx response."""
    try:
        req = Request(INBOX_URL, headers={"Accept": "application/json,*/*"})
        with urlopen(req, timeout=TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except (URLError, HTTPError, TimeoutError, OSError, ValueError):
        return False


def check_tokenrouter() -> bool:
    """Make one tiny completion call (max_tokens=1) to TokenRouter."""
    payload = {
        "model": TOKENROUTER_MODEL,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    headers = {"Content-Type": "application/json"}
    if TOKENROUTER_TOKEN:
        headers["Authorization"] = f"Bearer {TOKENROUTER_TOKEN}"
    try:
        req = Request(
            TOKENROUTER_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(req, timeout=TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except (URLError, HTTPError, TimeoutError, OSError, ValueError):
        return False


def check_pi() -> bool:
    """Is the `pi` CLI on PATH and does `pi --version` exit 0?"""
    if shutil.which("pi") is None:
        return False
    try:
        proc = subprocess.run(
            ["pi", "--version"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def check_imessage() -> bool:
    """Is ~/Library/Messages/chat.db present and readable?"""
    if not IMESSAGE_DB.exists():
        return False
    try:
        with open(IMESSAGE_DB, "rb") as f:
            f.read(1)  # one byte is enough to confirm readability
        return True
    except (PermissionError, OSError):
        return False


def check_whatsapp() -> Any:
    """
    Query macOS Accessibility API to see if System Events can enumerate
    processes (the prerequisite for reading WhatsApp).

    Returns:
        True   -> Accessibility permission granted.
        False  -> Permission denied / not granted.
        "skip" -> Platform is non-macOS or osascript missing.
    """
    if sys.platform != "darwin":
        return "skip"
    if shutil.which("osascript") is None:
        return "skip"

    # Asking System Events for *any* process list is the canonical probe —
    # macOS returns "Not authorized" via osascript exit code 174 if TCC
    # has not blessed the calling app for Accessibility.
    script = (
        'tell application "System Events" to '
        'return name of every process whose name contains "WhatsApp"'
    )
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "skip"

    # Empty list with rc=0 means: permission OK, WhatsApp simply not running.
    # rc=1 with "Not authorized" in stderr means: permission missing.
    if proc.returncode == 0:
        return True
    stderr = (proc.stderr or "").lower()
    if "not authorized" in stderr or "assistive" in stderr:
        return False
    # Anything else — treat as indeterminate / skipped.
    return "skip"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

CHECKS: list[tuple[str, str, Callable[[], Any]]] = [
    ("inbox", "Inbox server (9849)", check_inbox),
    ("tokenrouter", "TokenRouter API", check_tokenrouter),
    ("pi", "pi CLI", check_pi),
    ("imessage", "iMessage DB", check_imessage),
    ("whatsapp", "WhatsApp (Accessibility)", check_whatsapp),
]


def _safe_run(fn: Callable[[], Any]) -> Any:
    """Never let an exception escape a check."""
    try:
        return fn()
    except Exception:
        return False


def boot_check() -> dict[str, Any]:
    """Run all checks in parallel; return {service: True/False/'skip'}."""
    results: dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CHECKS)) as ex:
        futures = {ex.submit(_safe_run, fn): key for key, _, fn in CHECKS}
        for fut in concurrent.futures.as_completed(futures):
            key = futures[fut]
            try:
                results[key] = fut.result()
            except Exception:
                results[key] = False
    # Guarantee every key is present, in declaration order
    for key, _, _ in CHECKS:
        results.setdefault(key, False)
    return results


# ---------------------------------------------------------------------------
# Pretty-printing
# ---------------------------------------------------------------------------

def _format_value(v: Any) -> str:
    """Colored rendering of a single result value."""
    if v is True:
        return f"{C.GREEN}{C.BOLD}OK{C.RESET}"
    if v is False:
        return f"{C.RED}{C.BOLD}FAIL{C.RESET}"
    if isinstance(v, str):
        return f"{C.YELLOW}{C.BOLD}{v.upper()}{C.RESET}"
    return f"{C.DIM}{v}{C.RESET}"


def print_table(results: dict[str, Any]) -> None:
    key_w = max(len(k) for k, _, _ in CHECKS)
    name_w = max(len(n) for _, n, _ in CHECKS)

    bar = f"{C.GREY}{'─' * (key_w + name_w + 14)}{C.RESET}"
    print()
    print(f"{C.BOLD}{C.CYAN}Odysseus boot check{C.RESET}  {C.DIM}(timeout {TIMEOUT_S:.0f}s per probe){C.RESET}")
    print(bar)
    for key, label, _ in CHECKS:
        v = results.get(key, False)
        print(
            f"  {C.DIM}{key:<{key_w}}{C.RESET}  "
            f"{label:<{name_w}}  {_format_value(v)}"
        )
    print(bar)

    ok = sum(1 for v in results.values() if v is True)
    fail = sum(1 for v in results.values() if v is False)
    skip = sum(1 for v in results.values() if v == "skip")
    summary = (
        f"  {C.GREEN}{C.BOLD}{ok} OK{C.RESET}   "
        f"{C.RED}{C.BOLD}{fail} FAIL{C.RESET}   "
        f"{C.YELLOW}{C.BOLD}{skip} SKIP{C.RESET}"
    )
    print(summary)
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    results = boot_check()
    print_table(results)
    # Non-zero exit if any *required* check failed; WhatsApp "skip" is fine.
    critical_failure = any(
        v is False for k, v in results.items() if k != "whatsapp"
    )
    return 1 if critical_failure else 0


if __name__ == "__main__":
    sys.exit(main())
