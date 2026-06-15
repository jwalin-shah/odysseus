#!/usr/bin/env python3
"""Odysseus startup checker.

Verifies that all services Odysseus depends on are reachable before the
main process starts. Runs five short checks in parallel, each capped at
a 3 second timeout, and prints a colored status table to stdout.

Checks
------
1. Inbox server    : GET  http://localhost:9849/health
2. TokenRouter API : POST a 1-token chat completion
3. pi CLI          : `pi --version` exits 0
4. iMessage DB     : ~/Library/Messages/chat.db exists and is readable
5. WhatsApp a11y   : macOS Accessibility API list (osascript / System Events)

The return value of :func:`run_all` is a dict suitable for programmatic
consumption::

    {"inbox": True, "tokenrouter": True, "pi": True,
     "imessage": True, "whatsapp": "skip"}

Each value is either ``True`` (OK), ``False`` (FAIL), or the string
``"skip"`` for checks that cannot meaningfully run on the current host.

Environment variables
---------------------
``ODYSSEUS_INBOX_URL``         override inbox health URL
``ODYSSEUS_TOKENROUTER_URL``   override TokenRouter chat-completions URL
``ODYSSEUS_TOKENROUTER_MODEL`` model name to send (default: MiniMax-M3)
``ODYSSEUS_PI_BIN``            override the ``pi`` binary path
``ODYSSEUS_IMESSAGE_DB``       override the iMessage chat.db path
``NO_COLOR``                   disable ANSI colors when set
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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INBOX_URL = os.environ.get(
    "ODYSSEUS_INBOX_URL", "http://localhost:9849/health"
)
TOKENROUTER_URL = os.environ.get(
    "ODYSSEUS_TOKENROUTER_URL", "http://localhost:9848/v1/chat/completions"
)
TOKENROUTER_MODEL = os.environ.get(
    "ODYSSEUS_TOKENROUTER_MODEL", "MiniMax-M3"
)
PI_BIN = os.environ.get("ODYSSEUS_PI_BIN", "pi")
IMESSAGE_DB = Path(
    os.environ.get(
        "ODYSSEUS_IMESSAGE_DB",
        str(Path.home() / "Library" / "Messages" / "chat.db"),
    )
)

CHECK_TIMEOUT_S = 3.0

# ---------------------------------------------------------------------------
# ANSI colors (auto-disabled on non-TTY or when NO_COLOR is set)
# ---------------------------------------------------------------------------

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"


def _c(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}" if _USE_COLOR else text


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

# A check returns True (OK), False (FAIL), or "skip" (cannot evaluate).
CheckResult = Union[bool, str]


def check_inbox() -> CheckResult:
    """GET the inbox health endpoint, expect a 2xx response."""
    try:
        req = urllib.request.Request(INBOX_URL, method="GET")
        with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
        return False


def check_tokenrouter() -> CheckResult:
    """Send a 1-token chat completion through TokenRouter."""
    payload = json.dumps(
        {
            "model": TOKENROUTER_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKENROUTER_URL,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError):
        return False


def check_pi() -> CheckResult:
    """Run ``<pi_bin> --version`` and check for a clean exit."""
    try:
        result = subprocess.run(
            [PI_BIN, "--version"],
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT_S,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def check_imessage() -> CheckResult:
    """Return True iff the iMessage chat.db exists and is readable."""
    try:
        return IMESSAGE_DB.exists() and os.access(IMESSAGE_DB, os.R_OK)
    except OSError:
        return False


def check_whatsapp() -> CheckResult:
    """Probe macOS Accessibility via osascript / System Events.

    Non-macOS hosts and any error path return ``"skip"`` because the
    Accessibility permission state cannot be reliably distinguished from
    a missing binary or other failure with a single probe.
    """
    if sys.platform != "darwin":
        return "skip"
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of every process',
            ],
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT_S,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "skip"


# ---------------------------------------------------------------------------
# Runner + printer
# ---------------------------------------------------------------------------

_CHECKS: dict[str, Callable[[], CheckResult]] = {
    "inbox": check_inbox,
    "tokenrouter": check_tokenrouter,
    "pi": check_pi,
    "imessage": check_imessage,
    "whatsapp": check_whatsapp,
}

_LABELS: dict[str, str] = {
    "inbox": "Inbox server",
    "tokenrouter": "TokenRouter API",
    "pi": "pi CLI",
    "imessage": "iMessage DB",
    "whatsapp": "WhatsApp a11y",
}

_DETAILS: dict[str, str] = {
    "inbox": INBOX_URL,
    "tokenrouter": f"{TOKENROUTER_URL}  ({TOKENROUTER_MODEL})",
    "pi": f"{PI_BIN} --version",
    "imessage": str(IMESSAGE_DB),
    "whatsapp": "osascript / System Events",
}

_ORDER: list[str] = ["inbox", "tokenrouter", "pi", "imessage", "whatsapp"]


def run_all() -> dict[str, CheckResult]:
    """Run all checks in parallel and return a name -> result dict."""
    results: dict[str, CheckResult] = {}
    with ThreadPoolExecutor(max_workers=len(_CHECKS)) as ex:
        futures = {ex.submit(fn): name for name, fn in _CHECKS.items()}
        for fut, name in futures.items():
            try:
                results[name] = fut.result()
            except Exception:
                # If a check raises unexpectedly, treat it as a hard fail.
                results[name] = False
    return results


def _format_status(value: CheckResult) -> str:
    if value is True:
        return _c("OK  ", _GREEN + _BOLD)
    if value == "skip":
        return _c("SKIP", _YELLOW + _BOLD)
    return _c("FAIL", _RED + _BOLD)


def print_table(results: dict[str, CheckResult]) -> None:
    """Render a colored, two-column status table to stdout."""
    label_w = max(len(_LABELS[k]) for k in _ORDER)
    detail_w = max(len(_DETAILS[k]) for k in _ORDER)
    rule = _c("─" * (label_w + detail_w + 12), _DIM)

    print(_c("Odysseus boot check", _BOLD))
    print(rule)
    for key in _ORDER:
        label = _LABELS[key].ljust(label_w)
        detail = _DETAILS[key].ljust(detail_w)
        status = _format_status(results.get(key, False))
        print(f"  {label}  {detail}  {status}")
    print(rule)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the boot check, print the table, and return a process exit code."""
    results = run_all()
    print_table(results)

    # Any hard FAIL (a False that isn't "skip") means we shouldn't start.
    hard_fail = any(v is False for v in results.values())
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
