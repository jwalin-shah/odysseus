#!/usr/bin/env python3
"""
Odysseus boot — startup service checker.

Runs five fast, parallel health checks (3s timeout each):
  1. inbox server         GET  http://localhost:9849/health
  2. TokenRouter API      one tiny M3 completion
  3. pi CLI               `pi --version`
  4. iMessage DB          ~/Library/Messages/chat.db readable
  5. WhatsApp a11y        best-effort, returns "skip" on failure

Returns a dict like:
  {"inbox": True, "tokenrouter": True, "pi": True,
   "imessage": True, "whatsapp": "skip"}

Exits 0 if all non-skippable checks pass, 1 otherwise.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

# ─────────────────────────── timing ────────────────────────────
TIMEOUT = 3.0  # seconds per check

# ─────────────────────────── colors ────────────────────────────
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def green(t: str) -> str:  return _c("32", t)
def red(t: str) -> str:    return _c("31", t)
def yellow(t: str) -> str: return _c("33", t)
def dim(t: str) -> str:    return _c("2",  t)
def bold(t: str) -> str:  return _c("1",  t)


# ─────────────────────────── checks ────────────────────────────

def check_inbox() -> bool:
    """GET http://localhost:9849/health → 2xx."""
    url = "http://localhost:9849/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, socket.timeout,
            ConnectionRefusedError, OSError):
        return False


def check_tokenrouter() -> bool:
    """One tiny M3 completion via TokenRouter (OpenAI-compatible)."""
    base = os.environ.get("TOKENROUTER_URL", "http://localhost:9800/v1")
    key  = os.environ.get("TOKENROUTER_API_KEY", "sk-noop")
    url  = f"{base.rstrip('/')}/chat/completions"
    body = json.dumps({
        "model": os.environ.get("TOKENROUTER_MODEL", "m3-tiny"),
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1,
        "temperature": 0,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, socket.timeout,
            ConnectionRefusedError, OSError, ValueError):
        return False


def check_pi() -> bool:
    """`pi --version` exits 0."""
    try:
        r = subprocess.run(
            ["pi", "--version"],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def check_imessage() -> bool:
    """~/Library/Messages/chat.db exists and is readable."""
    db = Path.home() / "Library" / "Messages" / "chat.db"
    try:
        return db.is_file() and os.access(db, os.R_OK)
    except OSError:
        return False


def check_whatsapp() -> Any:
    """Best-effort macOS Accessibility probe; never fatal → 'skip' on fail."""
    if sys.platform != "darwin":
        return "skip"
    script = (
        'tell application "System Events" to get name of every process '
        'whose name contains "WhatsApp"'
    )
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        return True if r.returncode == 0 else "skip"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "skip"


# ─────────────────────────── runner ────────────────────────────

CHECKS: list[tuple[str, Callable[[], Any]]] = [
    ("inbox",       check_inbox),
    ("tokenrouter", check_tokenrouter),
    ("pi",          check_pi),
    ("imessage",    check_imessage),
    ("whatsapp",    check_whatsapp),
]


def run() -> dict[str, Any]:
    """Execute all checks in parallel; return result dict."""
    results: dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CHECKS)) as pool:
        futures = {pool.submit(fn): name for name, fn in CHECKS}
        try:
            for fut in concurrent.futures.as_completed(
                futures, timeout=TIMEOUT + 2
            ):
                name = futures[fut]
                try:
                    results[name] = fut.result()
                except Exception:
                    results[name] = "skip" if name == "whatsapp" else False
        except concurrent.futures.TimeoutError:
            # Any future that didn't complete in time counts as failure
            for name, fut in futures.items():
                if name not in results:
                    results[name] = "skip" if name == "whatsapp" else False
    return results


# ─────────────────────────── output ────────────────────────────

def _fmt(value: Any) -> str:
    if value is True:   return green("OK  ")
    if value is False:  return red("FAIL")
    if value == "skip": return yellow("SKIP")
    return dim("?   ")


def print_table(results: dict[str, Any]) -> None:
    print()
    print(bold("⚓ Odysseus boot status"))
    print(dim("─" * 38))
    for name, _ in CHECKS:
        print(f"  {name:<12} {_fmt(results.get(name))}")
    print(dim("─" * 38))

    failed = [n for n, _ in CHECKS if results.get(n) is False]
    if failed:
        print(red(f"  ✗ {len(failed)} failed: {', '.join(failed)}"))
    else:
        print(green("  ✓ all systems go"))
    print()


# ─────────────────────────── main ──────────────────────────────

if __name__ == "__main__":
    results = run()
    print_table(results)
    has_failure = any(results.get(n) is False for n, _ in CHECKS)
    sys.exit(1 if has_failure else 0)
