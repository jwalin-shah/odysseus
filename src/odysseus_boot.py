#!/usr/bin/env python3
"""Odysseus boot checker — verifies all required services are reachable.

Usage:
    python -m src.odysseus_boot          # prints a colored status table
    from src.odysseus_boot import check  # programmatic: returns the dict

Returned dict shape:
    {
        "inbox":       bool,   # inbox server /health
        "tokenrouter": bool,   # one tiny M3 chat-completion call
        "pi":          bool,   # `pi --version` exits 0
        "imessage":    bool,   # ~/Library/Messages/chat.db exists & readable
        "whatsapp":    True | False | "skip",
    }
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Union

CheckResult = Union[bool, str]


# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"


# ---------------------------------------------------------------------------
# Individual checks — each self-contained with a 3-second budget
# ---------------------------------------------------------------------------

def check_inbox_server() -> bool:
    """GET http://localhost:9849/health within 3s."""
    try:
        req = urllib.request.Request(
            "http://localhost:9849/health", method="GET"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return False


def check_tokenrouter() -> bool:
    """One tiny M3 chat-completion call to TokenRouter (3s budget)."""
    api_key = os.environ.get("TOKENROUTER_API_KEY") or os.environ.get(
        "OPENAI_API_KEY"
    )
    if not api_key:
        return False
    base = (
        os.environ.get("TOKENROUTER_BASE", "https://api.tokenrouter.ai/v1")
        .rstrip("/")
    )
    body = json.dumps(
        {
            "model": "m3-tiny",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return False


def check_pi_cli() -> bool:
    """`pi --version` must exit 0 within 3s."""
    try:
        proc = subprocess.run(
            ["pi", "--version"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return proc.returncode == 0


def check_imessage_db() -> bool:
    """Confirm ~/Library/Messages/chat.db exists and is readable."""
    db = Path.home() / "Library" / "Messages" / "chat.db"
    if not db.is_file():
        return False
    try:
        with open(db, "rb") as fh:
            fh.read(16)  # touch the file to confirm access
        return True
    except OSError:
        return False


def check_whatsapp_accessibility() -> CheckResult:
    """Best-effort check of macOS Accessibility permission for WhatsApp.

    Returns True/False on macOS, "skip" on any other platform or when
    the probe itself fails (e.g. osascript unavailable).
    """
    if sys.platform != "darwin":
        return "skip"
    # Ask System Events about the WhatsApp process.  If TCC has not granted
    # accessibility, osascript exits non-zero with "not authorized".
    script = (
        'tell application "System Events" to '
        'count of (every process whose name is "WhatsApp")'
    )
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "skip"
    if proc.returncode == 0:
        return True
    err = (proc.stderr or "").lower()
    if "not authorized" in err or "not permitted" in err:
        return False
    return "skip"


# ---------------------------------------------------------------------------
# Registry + parallel runner
# ---------------------------------------------------------------------------

CHECKS: dict[str, tuple[str, Callable[[], CheckResult]]] = {
    "inbox":       ("Inbox server",    check_inbox_server),
    "tokenrouter": ("TokenRouter API", check_tokenrouter),
    "pi":          ("pi CLI",          check_pi_cli),
    "imessage":    ("iMessage DB",     check_imessage_db),
    "whatsapp":    ("WhatsApp a11y",   check_whatsapp_accessibility),
}


def check() -> dict[str, CheckResult]:
    """Run every check in parallel and return the results dict."""
    results: dict[str, CheckResult] = {}
    with ThreadPoolExecutor(max_workers=len(CHECKS)) as ex:
        futures = {ex.submit(fn): key for key, (_, fn) in CHECKS.items()}
        for fut, key in futures.items():
            try:
                results[key] = fut.result(timeout=4)
            except Exception:
                results[key] = "skip" if key == "whatsapp" else False
    # Make sure every key is present even on pathological failures.
    for key, (_, _fn) in CHECKS.items():
        results.setdefault(key, "skip" if key == "whatsapp" else False)
    return results


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def _status_cell(value: CheckResult) -> str:
    if value is True:
        return f"{C.GREEN}OK  {C.RESET}"
    if value is False:
        return f"{C.RED}FAIL{C.RESET}"
    if isinstance(value, str) and value.lower() == "skip":
        return f"{C.YELLOW}SKIP{C.RESET}"
    return f"{C.RED}FAIL{C.RESET}"


def render_table(results: dict[str, CheckResult]) -> str:
    label_w = max(len(label) for label, _ in CHECKS.values())
    key_w = max(len(k) for k in CHECKS)

    lines: list[str] = [
        f" {C.BOLD}{'SERVICE'.ljust(label_w)}  "
        f"{'KEY'.ljust(key_w)}  STATUS{C.RESET}",
        f" {C.DIM}{'-' * (label_w + key_w + 14)}{C.RESET}",
    ]
    for key, (label, _) in CHECKS.items():
        lines.append(
            f" {label.ljust(label_w)}  "
            f"{C.CYAN}{key.ljust(key_w)}{C.RESET}  "
            f"{_status_cell(results.get(key))}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    # Disable color when output is piped/redirected.
    if not sys.stdout.isatty():
        for attr in ("RESET", "BOLD", "DIM", "RED", "GREEN", "YELLOW", "CYAN"):
            setattr(C, attr, "")

    print(f"{C.BOLD}Odysseus boot check{C.RESET}")
    results = check()
    print(render_table(results))

    fails = [k for k, v in results.items() if v is False]
    if fails:
        print(
            f"\n{C.RED}✗ {len(fails)} check(s) failed: "
            f"{', '.join(fails)}{C.RESET}"
        )
        return 1
    print(f"\n{C.GREEN}✓ all required services reachable{C.RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
