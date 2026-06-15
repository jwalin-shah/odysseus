#!/usr/bin/env python3
"""Odysseus boot check — verifies all required services are reachable.

Runs every check in parallel with a 3 s per-check timeout and prints a
colored status table. Returns a dict like::

    {
        "inbox":       True,   # /health on localhost:9849
        "tokenrouter": True,   # tiny M3 chat completion
        "pi":          True,   # `pi --version`
        "imessage":    True,   # ~/Library/Messages/chat.db readable
        "whatsapp":    "skip", # macOS Accessibility probe (ok / skip)
    }
"""

from __future__ import annotations

import concurrent.futures
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

try:
    import requests
except ImportError:
    sys.stderr.write(
        "error: the 'requests' library is required "
        "(install with: pip install requests)\n"
    )
    sys.exit(2)


# ─────────────────────────── ANSI colors ────────────────────────────


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


def _color_ok() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.getenv("TERM", "") == "dumb":
        return False
    return True


USE_COLOR = _color_ok()


def col(text: str, code: str) -> str:
    return f"{code}{text}{C.RESET}" if USE_COLOR else text


# ───────────────────────── individual checks ────────────────────────


def check_inbox(timeout: float = 3.0) -> bool:
    """Hit the inbox server's /health endpoint."""
    url = os.getenv("ODYSSEUS_INBOX_URL", "http://localhost:9849/health")
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def check_tokenrouter(timeout: float = 3.0) -> bool:
    """Make a 1-token M3 chat completion against TokenRouter."""
    base = os.getenv("ODYSSEUS_TOKENROUTER_URL", "http://localhost:9848").rstrip("/")
    payload = {
        "model": "m3",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("ODYSSEUS_TOKENROUTER_KEY") or os.getenv("OPENAI_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = requests.post(
            f"{base}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        if resp.status_code == 200:
            return True
    except Exception:
        pass

    # Fall back to a plain health probe
    try:
        resp = requests.get(f"{base}/health", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def check_pi(timeout: float = 3.0) -> bool:
    """Confirm the `pi` CLI exists and responds to --version."""
    try:
        result = subprocess.run(
            ["pi", "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def check_imessage(timeout: float = 3.0) -> bool:
    """Confirm ~/Library/Messages/chat.db exists and is readable."""
    _ = timeout  # accepted for signature parity
    path = Path.home() / "Library" / "Messages" / "chat.db"
    if not path.exists():
        return False
    try:
        with open(path, "rb") as fh:
            fh.read(1)
        return True
    except OSError:
        return False


def check_whatsapp(timeout: float = 3.0) -> str:
    """Probe macOS Accessibility via System Events.

    Returns ``"ok"`` if the probe succeeded, otherwise ``"skip"``.
    """
    if sys.platform != "darwin":
        return "skip"

    script = 'tell application "System Events" to return name of every process'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            return "ok"
        return "skip"
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return "skip"


# ───────────────────────── parallel runner ──────────────────────────


CHECKS: list[tuple[str, Callable[[float], Any]]] = [
    ("inbox", check_inbox),
    ("tokenrouter", check_tokenrouter),
    ("pi", check_pi),
    ("imessage", check_imessage),
    ("whatsapp", check_whatsapp),
]


def run_all(timeout: float = 3.0) -> dict[str, Any]:
    """Run every check in parallel; return a dict of results."""
    results: dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CHECKS)) as pool:
        futures = {pool.submit(fn, timeout): name for name, fn in CHECKS}
        for fut in concurrent.futures.as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception:
                results[name] = "skip" if name == "whatsapp" else False
    return results


# ───────────────────────── pretty printer ───────────────────────────


def _status_label(value: Any) -> str:
    if value is True or value == "ok":
        text, style = "  OK  ", C.BG_GREEN + C.WHITE + C.BOLD
    elif value == "skip":
        text, style = " SKIP ", C.BG_YELLOW + C.WHITE + C.BOLD
    else:
        text, style = " FAIL ", C.BG_RED + C.WHITE + C.BOLD
    return f"{style}{text}{C.RESET}" if USE_COLOR else text


def print_report(results: dict[str, Any]) -> None:
    """Print a colored status table to stdout."""
    print()
    title = " Odysseus Boot Check "
    bar = "═" * len(title)
    print(col(bar, C.CYAN + C.BOLD))
    print(col(f"║{title}║", C.CYAN + C.BOLD))
    print(col(bar, C.CYAN + C.BOLD))
    print()

    for name in ("inbox", "tokenrouter", "pi", "imessage", "whatsapp"):
        if name not in results:
            continue
        label = col(name.ljust(12), C.WHITE + C.BOLD)
        print(f"  {label} {_status_label(results[name])}")

    print()


# ───────────────────────────── main ─────────────────────────────────


def main() -> int:
    started = time.monotonic()
    results = run_all(timeout=3.0)
    elapsed = time.monotonic() - started

    print_report(results)
    print(col(f"  completed in {elapsed:.2f}s", C.DIM))
    print()

    # Exit non-zero if any required check failed (whatsapp 'skip' is fine)
    for name, value in results.items():
        if name == "whatsapp":
            continue
        if value is not True:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
