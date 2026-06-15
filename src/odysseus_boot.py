#!/usr/bin/env python3
"""Odysseus startup checker — verifies all services are reachable.

Runs every probe in parallel with a 3s budget and renders a colored
status table. Safe to import: ``run_checks()`` returns the raw dict
without printing, while ``main()`` does the full CLI dance.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable

# ── ANSI colors (silenced when stdout isn't a TTY) ────────────────────
def _use_color() -> bool:
    return sys.stdout.isatty() or bool(os.environ.get("ODYSSEUS_FORCE_COLOR"))


_c = _use_color()
GREEN = "\033[92m" if _c else ""
RED = "\033[91m" if _c else ""
YELLOW = "\033[93m" if _c else ""
DIM = "\033[2m" if _c else ""
BOLD = "\033[1m" if _c else ""
RESET = "\033[0m" if _c else ""

# ── Config ────────────────────────────────────────────────────────────
TIMEOUT_S = 3
INBOX_URL = os.environ.get("ODYSSEUS_INBOX_URL", "http://localhost:9849/health")
TOKENROUTER_URL = os.environ.get(
    "TOKENROUTER_URL", "http://localhost:9850/v1/chat/completions"
)
TOKENROUTER_KEY = os.environ.get("TOKENROUTER_API_KEY", "")
IMESSAGE_DB = Path.home() / "Library" / "Messages" / "chat.db"

# Order matters — this drives the table layout.
SERVICES: tuple[str, ...] = ("inbox", "tokenrouter", "pi", "imessage", "whatsapp")


# ── Individual probes ─────────────────────────────────────────────────
def check_inbox() -> bool:
    """GET the inbox server's /health endpoint."""
    try:
        with urllib.request.urlopen(INBOX_URL, timeout=TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def check_tokenrouter() -> bool:
    """POST a single-token M3 completion — the cheapest possible call."""
    try:
        body = json.dumps(
            {
                "model": "m3-tiny",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
                "stream": False,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if TOKENROUTER_KEY:
            headers["Authorization"] = f"Bearer {TOKENROUTER_KEY}"
        req = urllib.request.Request(TOKENROUTER_URL, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def check_pi() -> bool:
    """Confirm the ``pi`` CLI is on PATH and exits 0."""
    try:
        result = subprocess.run(
            ["pi", "--version"],
            capture_output=True,
            timeout=TIMEOUT_S,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_imessage() -> bool:
    """Confirm ~/Library/Messages/chat.db exists and is readable."""
    try:
        return IMESSAGE_DB.exists() and os.access(IMESSAGE_DB, os.R_OK)
    except Exception:
        return False


def check_whatsapp() -> bool | str:
    """Probe macOS accessibility permission via System Events.

    Returns:
        True  – permission granted (osascript listed processes).
        False – permission denied / System Events refused.
        "skip" – check is not runnable here (non-macOS, osascript
                 missing, timeout, etc.).
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
            timeout=TIMEOUT_S,
        )
        return result.returncode == 0
    except Exception:
        return "skip"


CHECKS: dict[str, Callable[[], bool | str]] = {
    "inbox": check_inbox,
    "tokenrouter": check_tokenrouter,
    "pi": check_pi,
    "imessage": check_imessage,
    "whatsapp": check_whatsapp,
}


# ── Orchestrator ──────────────────────────────────────────────────────
def run_checks() -> dict[str, bool | str]:
    """Run every probe in parallel; each is capped at TIMEOUT_S."""
    results: dict[str, bool | str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CHECKS)) as ex:
        futures = {ex.submit(fn): name for name, fn in CHECKS.items()}
        for fut in concurrent.futures.as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result(timeout=TIMEOUT_S)
            except Exception:
                # whatsapp degrades to "skip"; everything else to False.
                results[name] = "skip" if name == "whatsapp" else False
    return results


# ── Display ───────────────────────────────────────────────────────────
def _render(results: dict[str, bool | str]) -> str:
    name_w = max(len("Service"), max(len(n) for n in SERVICES))
    bar = "─" * (name_w + 12)
    lines: list[str] = [
        f"{BOLD}Odysseus Boot Check{RESET}",
        bar,
        f"{'Service':<{name_w}}  {'Status':<6}",
        bar,
    ]
    for name in SERVICES:
        value = results.get(name, False)
        if value is True:
            tag, color = "OK", GREEN
        elif value == "skip":
            tag, color = "SKIP", YELLOW
        else:
            tag, color = "FAIL", RED
        lines.append(f"{name:<{name_w}}  {color}{tag:<6}{RESET}")
    lines.append(bar)
    return "\n".join(lines)


# ── CLI entry point ───────────────────────────────────────────────────
def main() -> int:
    results = run_checks()
    print(_render(results))
    # Exit non-zero if any *checked* probe failed. Skipped probes are OK.
    critical = [v for v in results.values() if v != "skip"]
    return 0 if all(v is True for v in critical) else 1


if __name__ == "__main__":
    sys.exit(main())
