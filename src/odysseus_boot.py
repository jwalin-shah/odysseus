#!/usr/bin/env python3
"""
Odysseus boot checker.

Verifies that all required services are reachable before Odysseus starts.
Runs each check in parallel with a 3s timeout, prints a colored status table,
and returns a dict mapping service name → bool (or "skip" for optional ones).

Usage:
    python -m src.odysseus_boot
    # or
    python src/odysseus_boot.py

Environment overrides:
    ODYSSEUS_INBOX_URL        default: http://localhost:9849/health
    ODYSSEUS_TOKENROUTER_URL  default: http://localhost:9848/v1/chat/completions
"""

from __future__ import annotations

import concurrent.futures
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

try:
    import requests
except ImportError:  # pragma: no cover
    sys.stderr.write("odysseus_boot: 'requests' is required (pip install requests)\n")
    sys.exit(2)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INBOX_URL = os.environ.get(
    "ODYSSEUS_INBOX_URL", "http://localhost:9849/health"
)
TOKENROUTER_URL = os.environ.get(
    "ODYSSEUS_TOKENROUTER_URL", "http://localhost:9848/v1/chat/completions"
)
TIMEOUT_S = 3.0
MAX_WORKERS = 5

# ANSI escapes (works on macOS/Linux; Windows users can run through WSL/terminal)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Individual checks
#
# Each function returns:
#   True   → service is healthy
#   False  → service is down / unreachable / failed
#   "skip" → check is not applicable in this environment (only for optional)
# ---------------------------------------------------------------------------


def check_inbox() -> bool:
    """Inbox server health endpoint."""
    try:
        r = requests.get(INBOX_URL, timeout=TIMEOUT_S)
        return bool(r.ok)
    except Exception:
        return False


def check_tokenrouter() -> bool:
    """Fire one tiny M3 completion to confirm the router is live."""
    payload = {
        "model": "M3",
        "messages": [{"role": "user", "content": "."}],
        "max_tokens": 1,
        "temperature": 0.0,
    }
    try:
        r = requests.post(TOKENROUTER_URL, json=payload, timeout=TIMEOUT_S)
        return bool(r.ok)
    except Exception:
        return False


def check_pi() -> bool:
    """The `pi` CLI is on PATH and executable."""
    try:
        result = subprocess.run(
            ["pi", "--version"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_imessage() -> bool:
    """iMessage chat.db is present and readable."""
    db_path = Path.home() / "Library" / "Messages" / "chat.db"
    if not db_path.exists():
        return False
    try:
        # Open read-only and run a trivial query to confirm accessibility.
        uri = f"file:{db_path}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=TIMEOUT_S) as conn:
            conn.execute("SELECT 1 FROM message LIMIT 1")
        return True
    except Exception:
        return False


def check_whatsapp() -> Any:
    """WhatsApp is optional. Only meaningful on macOS with pyobjc installed."""
    try:
        import Quartz  # type: ignore  # provided by pyobjc-framework-Quartz
    except Exception:
        return "skip"

    # `AXIsProcessTrusted()` is the canonical macOS Accessibility check.
    # It returns True when the current process is granted Accessibility perms.
    try:
        trusted = bool(Quartz.AXIsProcessTrusted())
        return True if trusted else "skip"
    except Exception:
        return "skip"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

CHECKS: dict[str, Callable[[], Any]] = {
    "inbox": check_inbox,
    "tokenrouter": check_tokenrouter,
    "pi": check_pi,
    "imessage": check_imessage,
    "whatsapp": check_whatsapp,
}


def run_parallel() -> dict[str, Any]:
    """Run every check in parallel, each capped at TIMEOUT_S + 1s slack."""
    results: dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_name = {pool.submit(fn): name for name, fn in CHECKS.items()}
        for fut in concurrent.futures.as_completed(future_to_name, timeout=None):
            name = future_to_name[fut]
            try:
                results[name] = fut.result(timeout=TIMEOUT_S + 1.0)
            except Exception:
                results[name] = "skip" if name == "whatsapp" else False
    return results


def _format_status(value: Any) -> str:
    if value is True:
        return f"{GREEN}{BOLD}  OK  {RESET}"
    if value == "skip":
        return f"{YELLOW} SKIP  {RESET}"
    return f"{RED}{BOLD} FAIL {RESET}"


def print_table(results: dict[str, Any]) -> None:
    width = 49
    bar = "─" * (width - 2)
    print()
    print(f"{CYAN}{BOLD}┌{bar}┐{RESET}")
    print(f"{CYAN}{BOLD}│{RESET}  {'Odysseus Boot':<{width - 4}} {CYAN}{BOLD}│{RESET}")
    print(f"{CYAN}{BOLD}├{bar}┤{RESET}")
    print(
        f"{CYAN}{BOLD}│{RESET}  {BOLD}{'Service':<22}{RESET}"
        f"{DIM}{'Description':<22}{RESET} {CYAN}{BOLD}│{RESET}"
    )
    print(f"{CYAN}{BOLD}├{bar}┤{RESET}")

    descriptions = {
        "inbox": "inbox server /health",
        "tokenrouter": "TokenRouter M3 call",
        "pi": "`pi --version`",
        "imessage": "~/Library/Messages/chat.db",
        "whatsapp": "macOS Accessibility API",
    }
    for name in CHECKS:
        status = _format_status(results.get(name))
        label = descriptions.get(name, "")
        print(
            f"{CYAN}{BOLD}│{RESET}  {name:<22}{DIM}{label:<22}{RESET} {status} {CYAN}{BOLD}│{RESET}"
        )

    print(f"{CYAN}{BOLD}└{bar}┘{RESET}")
    print()

    # Compact summary line — easy to grep from a parent process.
    summary = " ".join(
        f"{name}={'ok' if results.get(name) is True else results.get(name)}"
        for name in CHECKS
    )
    print(f"{DIM}  {summary}{RESET}")
    print()


def main() -> dict[str, Any]:
    results = run_parallel()
    print_table(results)
    return results


if __name__ == "__main__":
    main()
