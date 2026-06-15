#!/usr/bin/env python3
"""
odysseus_boot.py — startup health checks for Odysseus.

Runs every check in parallel (ThreadPoolExecutor) with a 3-second
per-check timeout, prints a colored status table to stdout, and
returns a dict describing the result of each check.

Usage:
    python src/odysseus_boot.py
    ODYSSEUS_INBOX_URL=http://...:9849/health python src/odysseus_boot.py
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

# ── ANSI palette ─────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"

TIMEOUT_S = 3
USER_AGENT = "odysseus-boot/1.0"


# ── individual checks ───────────────────────────────────────────────────

def check_inbox() -> bool:
    """GET inbox /health endpoint."""
    url = os.environ.get("ODYSSEUS_INBOX_URL", "http://localhost:9849/health")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def check_tokenrouter() -> bool:
    """Send one tiny M3 completion to TokenRouter."""
    url = os.environ.get(
        "ODYSSEUS_TOKENROUTER_URL",
        "http://localhost:9848/v1/chat/completions",
    )
    body = json.dumps({
        "model": "m3",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def check_pi() -> bool:
    """Run `pi --version` and inspect the exit code."""
    try:
        proc = subprocess.run(
            ["pi", "--version"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
        return proc.returncode == 0
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False


def check_imessage() -> bool:
    """Confirm ~/Library/Messages/chat.db exists and is readable."""
    try:
        db = Path.home() / "Library" / "Messages" / "chat.db"
        return db.is_file() and os.access(db, os.R_OK)
    except OSError:
        return False


def check_whatsapp() -> bool | str:
    """Probe macOS Accessibility API (System Events)."""
    if sys.platform != "darwin":
        return "skip"
    try:
        proc = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to count of processes'],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
        # WhatsApp check never *fails* — OK if we have permission, SKIP otherwise.
        return True if proc.returncode == 0 else "skip"
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return "skip"


# ── registry ────────────────────────────────────────────────────────────

CHECKS: list[tuple[str, str, Callable[[], object]]] = [
    ("inbox",       "GET  localhost:9849/health",               check_inbox),
    ("tokenrouter", "1× M3 chat completion",                    check_tokenrouter),
    ("pi",          "pi --version",                             check_pi),
    ("imessage",    "~/Library/Messages/chat.db readable",      check_imessage),
    ("whatsapp",    "macOS Accessibility API (System Events)",  check_whatsapp),
]


# ── runner ──────────────────────────────────────────────────────────────

def run_all() -> dict:
    """Execute every check concurrently and collect results."""
    results: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CHECKS)) as pool:
        futures = {pool.submit(fn): name for name, _, fn in CHECKS}
        for fut, name in futures.items():
            try:
                value = fut.result(timeout=TIMEOUT_S + 1)
            except Exception:
                value = "skip" if name == "whatsapp" else False
            # WhatsApp is binary OK / SKIP — coerce any False into SKIP.
            if name == "whatsapp" and value is False:
                value = "skip"
            results[name] = value
    # Defensive backfill in case a future disappears.
    for name, _, _ in CHECKS:
        results.setdefault(name, "skip" if name == "whatsapp" else False)
    return results


# ── rendering ───────────────────────────────────────────────────────────

def _format_status(value: object) -> tuple[str, str]:
    """Return (color, label) for a check value."""
    if value is True:
        return GREEN,  "  OK  "
    if value == "skip":
        return YELLOW, " SKIP "
    return RED, " FAIL "


def render(results: dict) -> None:
    """Print a colored, aligned status table to stdout."""
    name_w = max(len(n) for n, _, _ in CHECKS)
    desc_w = max(len(d) for _, d, _ in CHECKS)
    bar    = "─" * (name_w + desc_w + 14)

    print()
    print(f"  {BOLD}{CYAN}⚓ Odysseus Boot{RESET} {DIM}— startup checks{RESET}")
    print(f"  {DIM}{bar}{RESET}")
    print(
        f"  {BOLD}{'check':<{name_w}}{RESET}  "
        f"{DIM}{'what':<{desc_w}}{RESET}  "
        f"{BOLD}{'status':>6}{RESET}"
    )
    print(f"  {DIM}{bar}{RESET}")

    for name, desc, _ in CHECKS:
        value = results.get(name, False)
        color, label = _format_status(value)
        print(
            f"  {name:<{name_w}}  "
            f"{DIM}{desc:<{desc_w}}{RESET}  "
            f"{color}{BOLD}{label}{RESET}"
        )

    print(f"  {DIM}{bar}{RESET}")

    n_ok   = sum(1 for v in results.values() if v is True)
    n_fail = sum(1 for v in results.values() if v is False)
    n_skip = sum(1 for v in results.values() if v == "skip")

    ok_color   = GREEN  if n_ok   else DIM
    fail_color = RED    if n_fail else DIM
    skip_color = YELLOW if n_skip else DIM

    print(
        f"  {ok_color}{n_ok} ok{RESET}  "
        f"{fail_color}{n_fail} fail{RESET}  "
        f"{skip_color}{n_skip} skip{RESET}"
    )
    print()


# ── entry point ─────────────────────────────────────────────────────────

def main() -> int:
    results = run_all()
    render(results)
    # Non-zero exit only if a *required* check failed (skip is fine).
    return 1 if any(v is False for v in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
