#!/usr/bin/env python3
"""Odysseus boot checker — verifies all required services are reachable.

Runs fast, parallel health checks against external dependencies and prints
a colored status table. Each check is bounded by a 3-second timeout, so
the worst-case startup cost is ~3s, not 5×3s.

Usage:
    python src/odysseus_boot.py

    # Programmatic:
    from odysseus_boot import run_checks
    status = run_checks()
    if not status["inbox"]:
        sys.exit(1)

Returns:
    dict with keys: inbox, tokenrouter, pi, imessage, whatsapp
        - first four are bool (True == OK, False == FAIL)
        - whatsapp is the str "ok" or "skip" (Accessibility can't be
          reliably probed from a non-GUI process)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

try:
    import requests
except ImportError:
    sys.stderr.write(
        "odysseus_boot: 'requests' is required. "
        "Install with: pip install requests\n"
    )
    sys.exit(1)


# --------------------------------------------------------------------------- #
# ANSI styling
# --------------------------------------------------------------------------- #

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR") == "1":
        return True
    return sys.stdout.isatty()


_COLOR = _color_enabled()


def c(text: str, color: str) -> str:
    """Wrap text in ANSI color codes (no-op if stdout isn't a TTY)."""
    return f"{color}{text}{RESET}" if _COLOR else text


# --------------------------------------------------------------------------- #
# Configuration (override via env vars)
# --------------------------------------------------------------------------- #

TIMEOUT = float(os.environ.get("ODYSSEUS_BOOT_TIMEOUT", "3.0"))

INBOX_URL = os.environ.get(
    "ODYSSEUS_INBOX_URL", "http://localhost:9849/health"
)
TOKENROUTER_URL = os.environ.get(
    "ODYSSEUS_TOKENROUTER_URL", "http://localhost:9848/v1/chat/completions"
)
TOKENROUTER_MODEL = os.environ.get(
    "ODYSSEUS_TOKENROUTER_MODEL", "MiniMax-M3"
)
TOKENROUTER_API_KEY = os.environ.get(
    "ODYSSEUS_TOKENROUTER_API_KEY", "sk-no-key-required"
)

PI_BIN = os.environ.get("ODYSSEUS_PI_BIN", "pi")
PI_CMD = [PI_BIN, "--version"]

IMESSAGE_DB = Path(
    os.environ.get(
        "ODYSSEUS_IMESSAGE_DB",
        os.path.expanduser("~/Library/Messages/chat.db"),
    )
)


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #

def check_inbox() -> bool:
    """Inbox server health endpoint returns 2xx."""
    try:
        r = requests.get(INBOX_URL, timeout=TIMEOUT)
        return r.ok
    except requests.RequestException:
        return False


def check_tokenrouter() -> bool:
    """One-token M3 completion — confirms the router is up and routed.

    Uses max_tokens=1 to keep the call as cheap as possible.
    """
    try:
        r = requests.post(
            TOKENROUTER_URL,
            headers={
                "Authorization": f"Bearer {TOKENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": TOKENROUTER_MODEL,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "stream": False,
            },
            timeout=TIMEOUT,
        )
        return r.ok
    except requests.RequestException:
        return False


def check_pi() -> bool:
    """`pi --version` exits 0 (binary is on PATH and runs)."""
    if shutil.which(PI_BIN) is None:
        return False
    try:
        result = subprocess.run(
            PI_CMD,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def check_imessage() -> bool:
    """~/Library/Messages/chat.db exists and is readable."""
    if not IMESSAGE_DB.exists():
        return False
    if not os.access(IMESSAGE_DB, os.R_OK):
        return False
    try:
        # Open and read 1 byte to confirm we can actually touch the DB,
        # not just stat it (macOS Full Disk Access is enforced on open()).
        with open(IMESSAGE_DB, "rb") as fh:
            fh.read(1)
        return True
    except OSError:
        return False


def check_whatsapp() -> str:
    """macOS-only: probe Accessibility permission via System Events.

    A non-GUI Python process can't directly call the macOS Accessibility
    API — the user must grant permission to the *parent* app (Terminal,
    IDE, etc.) in System Settings → Privacy & Security → Accessibility.
    We make a best-effort AppleScript probe and otherwise return "skip".
    """
    if sys.platform != "darwin":
        return "skip"
    if shutil.which("osascript") is None:
        return "skip"
    script = (
        'tell application "System Events" to count of '
        '(every process whose name is "WhatsApp")'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "skip"
    # osascript returns non-zero with "not authorized" in stderr when the
    # parent process hasn't been granted Accessibility.
    if result.returncode != 0:
        return "skip"
    return "ok"


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def run_checks() -> dict[str, bool | str]:
    """Run all checks in parallel and return the status dict.

    All checks execute concurrently via a thread pool; the whole call
    completes in at most ~TIMEOUT seconds regardless of how many checks
    there are.
    """
    checks: list[tuple[str, Callable[[], bool | str]]] = [
        ("inbox", check_inbox),
        ("tokenrouter", check_tokenrouter),
        ("pi", check_pi),
        ("imessage", check_imessage),
        ("whatsapp", check_whatsapp),
    ]

    # Pre-seed with safe defaults so a raising check still produces a
    # well-formed dict.
    results: dict[str, bool | str] = {
        name: (False if name != "whatsapp" else "skip") for name, _ in checks
    }

    with ThreadPoolExecutor(max_workers=len(checks)) as ex:
        futures = {ex.submit(fn): name for name, fn in checks}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception:  # noqa: BLE001 — defensive: any crash → FAIL/skip
                results[name] = False if name != "whatsapp" else "skip"

    return results


def print_table(results: dict[str, bool | str]) -> None:
    """Pretty-print a colored status table to stdout."""
    order = ["inbox", "tokenrouter", "pi", "imessage", "whatsapp"]
    rows = [(name, results.get(name)) for name in order]

    name_w = max(len(n) for n, _ in rows)
    rule_w = name_w + 16

    print()
    print(c("  ⚓ Odysseus Boot", BOLD + CYAN))
    print(c("  " + "─" * rule_w, DIM))
    for name, status in rows:
        if status is True:
            badge = c("  OK  ", BOLD + GREEN)
        elif status is False:
            badge = c(" FAIL ", BOLD + RED)
        else:  # "ok" or "skip" (any string)
            badge = c(" SKIP ", BOLD + YELLOW)
        print(f"  {name:<{name_w}}    {badge}")
    print(c("  " + "─" * rule_w, DIM))
    print()


def main() -> int:
    """Entry point: run checks, print table, return process exit code."""
    try:
        results = run_checks()
    except Exception as exc:  # noqa: BLE001
        print(c(f"odysseus_boot: fatal: {exc}", BOLD + RED), file=sys.stderr)
        return 2

    print_table(results)

    # Non-zero exit if any *required* check failed. "skip" is not a failure.
    required_failed = any(
        v is False for k, v in results.items() if k != "whatsapp"
    )
    return 1 if required_failed else 0


if __name__ == "__main__":
    sys.exit(main())
