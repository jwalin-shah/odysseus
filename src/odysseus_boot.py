#!/usr/bin/env python3
"""
odysseus_boot.py — pre-flight reachability check for Odysseus.

Runs five short checks in parallel (each capped at 3s) and prints a
colour-coded status table.  The returned dict is the machine-readable
contract:

    {
        "inbox":       True,    # /health on the local inbox server
        "tokenrouter": True,    # one tiny MiniMax-M3 completion
        "pi":          True,    # `pi --version` succeeds
        "imessage":    True,    # ~/Library/Messages/chat.db is readable
        "whatsapp":    "skip",  # Accessibility probe (OK or "skip")
    }

A `True` value means reachable/usable, `False` means unreachable, and the
string `"skip"` is reserved for the WhatsApp probe on systems where the
check cannot be performed (non-macOS, no permission, etc.).
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
from typing import Any, Callable

# ─── presentation ────────────────────────────────────────────────────────
GREEN, RED, YELLOW = "\033[92m", "\033[91m", "\033[93m"
CYAN, BOLD, DIM, RESET = "\033[96m", "\033[1m", "\033[2m", "\033[0m"

TIMEOUT_S = 3.0
NAME_WIDTH = 14
DETAIL_WIDTH = 48

# ─── individual checks ───────────────────────────────────────────────────
# Each check returns (status, detail).
#   status  is True / False  for hard pass/fail
#   status  is "skip"        for the WhatsApp probe only
#   detail  is a short human-readable string for the table

def _check_inbox() -> tuple[bool, str]:
    url = os.environ.get("ODYSSEUS_INBOX_URL", "http://localhost:9849/health")
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            ok = 200 <= resp.status < 300
            return ok, f"GET {url} → {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"GET {url} → HTTP {e.code}"
    except Exception as e:
        return False, f"GET {url} → {type(e).__name__}"


def _check_tokenrouter() -> tuple[bool, str]:
    """Fire one minimal completion — the cheapest possible M3 round-trip."""
    url = os.environ.get(
        "ODYSSEUS_TOKENROUTER_URL",
        "http://localhost:9848/v1/chat/completions",
    )
    api_key = os.environ.get("ODYSSEUS_TOKENROUTER_KEY", "")
    model = os.environ.get("ODYSSEUS_TOKENROUTER_MODEL", "MiniMax-M3")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = json.loads(resp.read() or b"{}")
            used = body.get("usage", {}).get("total_tokens", "?")
            ok = 200 <= resp.status < 300
            return ok, f"POST {url} → {resp.status} · {used} tok"
    except urllib.error.HTTPError as e:
        return False, f"POST {url} → HTTP {e.code}"
    except Exception as e:
        return False, f"POST {url} → {type(e).__name__}"


def _check_pi() -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["pi", "--version"],
            capture_output=True, text=True, timeout=TIMEOUT_S,
        )
    except FileNotFoundError:
        return False, "`pi` not on PATH"
    except subprocess.TimeoutExpired:
        return False, "timeout"

    if r.returncode == 0:
        first_line = (r.stdout or r.stderr).strip().splitlines()
        return True, first_line[0] if first_line else "ok"
    return False, f"exit {r.returncode}"


def _check_imessage() -> tuple[bool, str]:
    db = Path.home() / "Library" / "Messages" / "chat.db"
    if not db.exists():
        return False, f"missing: {db}"
    if not os.access(db, os.R_OK):
        return False, f"unreadable: {db}"
    size_mb = db.stat().st_size / (1024 * 1024)
    return True, f"{size_mb:.1f} MB"


def _check_whatsapp() -> tuple[Any, str]:
    """
    OK if Accessibility permission is granted AND we can enumerate
    processes via System Events.  SKIP for every other condition:
    non-macOS, osascript missing, permission not yet granted, or
    any other error — the daemon can still run, the user just has
    to grant access in System Settings.
    """
    if sys.platform != "darwin":
        return "skip", "non-darwin"

    script = 'tell application "System Events" to count processes'
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=TIMEOUT_S,
        )
    except FileNotFoundError:
        return "skip", "no osascript"
    except subprocess.TimeoutExpired:
        return "skip", "timeout"

    if r.returncode == 0 and r.stdout.strip().isdigit():
        return True, f"{r.stdout.strip()} processes visible"

    err = (r.stderr or "").lower()
    if any(token in err for token in ("not authorized", "assistive", "accessibility")):
        return "skip", "grant Accessibility in System Settings"
    return "skip", (err.strip() or "unknown")[:40]


# (name, fn) — order here drives the printed table and the returned dict
CHECKS: tuple[tuple[str, Callable[[], tuple[Any, str]]], ...] = (
    ("inbox",       _check_inbox),
    ("tokenrouter", _check_tokenrouter),
    ("pi",          _check_pi),
    ("imessage",    _check_imessage),
    ("whatsapp",    _check_whatsapp),
)


# ─── presentation ────────────────────────────────────────────────────────
def _marker(status: Any) -> str:
    if status == "skip":
        return f"{YELLOW}○ SKIP{RESET}"
    if status is True:
        return f"{GREEN}● OK  {RESET}"
    return f"{RED}✗ FAIL{RESET}"


def _print_table(results: dict[str, Any], details: dict[str, str]) -> None:
    print()
    print(f"  {BOLD}{CYAN}⚓ Odysseus boot check{RESET} "
          f"{DIM}(parallel, {TIMEOUT_S:g}s timeout each){RESET}")
    print(f"  {DIM}{'─' * 64}{RESET}")

    ok = fail = skip = 0
    for name, _ in CHECKS:
        status = results[name]
        detail = details[name]
        if len(detail) > DETAIL_WIDTH:
            detail = detail[: DETAIL_WIDTH - 1] + "…"
        print(f"  {_marker(status)}  {BOLD}{name:<{NAME_WIDTH}}{RESET} "
              f"{DIM}{detail}{RESET}")
        if status is True:    ok += 1
        elif status == "skip": skip += 1
        else:                  fail += 1

    summary = f"{ok} ok"
    if skip:  summary += f", {skip} skip"
    if fail:  summary += f", {RED}{fail} fail{RESET}"
    print(f"  {DIM}{'─' * 64}{RESET}")
    print(f"  {summary}\n")


# ─── public entry point ──────────────────────────────────────────────────
def boot_check() -> dict[str, Any]:
    """
    Run every check in parallel and return the status dict.

    The dict preserves the declared check order, with boolean values
    for the four hard checks and either True or the string "skip"
    for the WhatsApp accessibility probe.
    """
    results: dict[str, Any] = {}
    details: dict[str, str] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CHECKS)) as ex:
        futures = {ex.submit(fn): name for name, fn in CHECKS}
        for fut in concurrent.futures.as_completed(futures):
            name = futures[fut]
            try:
                status, detail = fut.result()
            except Exception as e:                       # pragma: no cover
                status, detail = False, f"{type(e).__name__}: {e}"
            results[name] = status
            details[name]  = detail

    # stable, declared order in the returned dict
    ordered: dict[str, Any] = {name: results[name] for name, _ in CHECKS}
    _print_table(ordered, details)
    return ordered


if __name__ == "__main__":
    out = boot_check()
    # exit non-zero if any hard check failed (skip never counts as failure)
    sys.exit(1 if any(v is False for v in out.values()) else 0)
