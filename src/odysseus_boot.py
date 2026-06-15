#!/usr/bin/env python3
"""
Odysseus boot checker — verifies all services are reachable.

Runs each check in parallel with a 3s timeout, prints a colored status table
to stdout, and returns a dict mapping service name → True / False / "skip".

Usage:
    python -m odysseus_boot
    python src/odysseus_boot.py

Environment overrides:
    ODYSSEUS_INBOX_URL         default: http://localhost:9849/health
    ODYSSEUS_TOKENROUTER_URL   default: http://localhost:9848/v1/chat/completions
    ODYSSEUS_MODEL             default: MiniMax-M3
    ODYSSEUS_TOKENROUTER_KEY   optional Bearer token
    NO_COLOR=1                 disable ANSI colors
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import concurrent.futures
from pathlib import Path
from typing import Callable, Dict, List, Tuple, Union

# Prefer `requests`; gracefully fall back to urllib stdlib.
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover
    requests = None  # type: ignore
    import urllib.request
    import urllib.error
    _HAS_REQUESTS = False


TIMEOUT = 3.0  # seconds per check


# --- ANSI colors -------------------------------------------------------------

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    BLUE   = "\033[34m"
    MAGENTA= "\033[35m"
    CYAN   = "\033[36m"
    GRAY   = "\033[90m"


def _color_enabled() -> bool:
    return (
        sys.stdout.isatty()
        and os.environ.get("TERM") != "dumb"
        and os.environ.get("NO_COLOR") is None
    )


def colorize(text: str, code: str) -> str:
    if not _color_enabled():
        return text
    return f"{code}{text}{C.RESET}"


# --- HTTP helper -------------------------------------------------------------

def _http_get(url: str) -> bool:
    try:
        if _HAS_REQUESTS:
            resp = requests.get(url, timeout=TIMEOUT)
            return 200 <= resp.status_code < 300
        with urllib.request.urlopen(url, timeout=TIMEOUT):  # noqa: S310
            return True
    except Exception:
        return False


def _http_post(url: str, payload: dict, headers: dict) -> bool:
    try:
        if _HAS_REQUESTS:
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            return 200 <= resp.status_code < 300
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT):  # noqa: S310
            return True
    except Exception:
        return False


# --- Individual checks --------------------------------------------------------

def check_inbox() -> bool:
    """Inbox server health endpoint."""
    url = os.environ.get(
        "ODYSSEUS_INBOX_URL", "http://localhost:9849/health"
    )
    return _http_get(url)


def check_tokenrouter() -> bool:
    """TokenRouter API — one tiny M3 chat-completion call."""
    url = os.environ.get(
        "ODYSSEUS_TOKENROUTER_URL",
        "http://localhost:9848/v1/chat/completions",
    )
    model = os.environ.get("ODYSSEUS_MODEL", "MiniMax-M3")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("ODYSSEUS_TOKENROUTER_KEY") or os.environ.get(
        "OPENAI_API_KEY"
    )
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return _http_post(url, payload, headers)


def check_pi() -> bool:
    """`pi` CLI on PATH and executable."""
    try:
        result = subprocess.run(
            ["pi", "--version"],
            capture_output=True,
            timeout=TIMEOUT,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_imessage() -> bool:
    """~/Library/Messages/chat.db exists and is readable."""
    db = Path.home() / "Library" / "Messages" / "chat.db"
    try:
        return db.is_file() and os.access(db, os.R_OK)
    except Exception:
        return False


def check_whatsapp() -> str:
    """
    macOS Accessibility API probe. Returns:
        "ok"   — System Events responded (a11y granted)
        "skip" — non-macOS, permission denied, or error
    """
    if sys.platform != "darwin":
        return "skip"

    script = (
        'tell application "System Events"\n'
        '  set procs to name of every process\n'
        '  return procs\n'
        'end tell'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=TIMEOUT,
            text=True,
        )
        return "ok" if result.returncode == 0 else "skip"
    except Exception:
        return "skip"


# --- Runner -------------------------------------------------------------------

CheckResult = Union[bool, str]  # True / False / "skip" / "ok"
CheckFn = Callable[[], CheckResult]

# Canonical check order — also the order keys appear in the returned dict.
CHECKS: List[Tuple[str, CheckFn]] = [
    ("inbox",       check_inbox),
    ("tokenrouter", check_tokenrouter),
    ("pi",          check_pi),
    ("imessage",    check_imessage),
    ("whatsapp",    check_whatsapp),
]

LABELS = {
    "inbox":       "Inbox server",
    "tokenrouter": "TokenRouter API",
    "pi":          "pi CLI",
    "imessage":    "iMessage DB",
    "whatsapp":    "WhatsApp a11y",
}


def run_checks() -> Dict[str, CheckResult]:
    """Execute all checks in parallel; return an ordered result dict."""
    results: Dict[str, CheckResult] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CHECKS)) as ex:
        future_to_name = {ex.submit(fn): name for name, fn in CHECKS}
        for fut in concurrent.futures.as_completed(future_to_name):
            name = future_to_name[fut]
            try:
                results[name] = fut.result()
            except Exception:
                results[name] = "skip" if name == "whatsapp" else False

    # Preserve canonical order; fill any missing entries with safe defaults.
    for name, _ in CHECKS:
        results.setdefault(name, "skip" if name == "whatsapp" else False)
    return results


def render_table(results: Dict[str, CheckResult]) -> None:
    """Print a colored status table to stdout."""
    width = max(len(label) for label in LABELS.values())
    rule   = "─" * (width + 24)

    print()
    print(colorize("⚓ Odysseus Boot Check", C.BOLD + C.CYAN))
    print(colorize(rule, C.GRAY))

    for name, _ in CHECKS:
        result = results[name]

        if result is True or result == "ok":
            tag, code = "OK  ", C.GREEN + C.BOLD
        elif result is False:
            tag, code = "FAIL", C.RED + C.BOLD
        elif result == "skip":
            tag, code = "SKIP", C.YELLOW + C.BOLD
        else:
            tag, code = str(result).ljust(4), C.GRAY

        label = LABELS[name].ljust(width)
        bullet = colorize("●", C.GRAY)
        print(
            f"  {bullet} "
            f"{colorize(label, C.BOLD)}  "
            f"{colorize(tag, code)}"
        )

    print(colorize(rule, C.GRAY))
    print()


def main() -> Dict[str, CheckResult]:
    results = run_checks()
    render_table(results)
    return results


if __name__ == "__main__":
    main()
