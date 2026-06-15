#!/usr/bin/env python3
"""Odysseus boot checker — verifies all required services are reachable.

Run as a script to print a colored status table, or import
``run_boot_check()`` to get the results dict programmatically.
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

# ---------------------------------------------------------------------------
# Color helpers — ANSI escapes, no external dependency
# ---------------------------------------------------------------------------
_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_GRAY = "\033[90m"

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(text: str, code: str) -> str:
    if not USE_COLOR:
        return text
    return f"{code}{text}{_RESET}"


# ---------------------------------------------------------------------------
# Individual checks (each ≤ 3 s; whatsapp may return the string "skip")
# ---------------------------------------------------------------------------
def check_inbox() -> bool:
    """GET http://localhost:9849/health — True on 2xx."""
    url = os.environ.get("ODYSSEUS_INBOX_URL", "http://localhost:9849/health")
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, Exception):
        return False


def check_tokenrouter() -> bool:
    """Single 1-token M3 chat completion — confirms the proxy answers."""
    base = os.environ.get(
        "ODYSSEUS_TOKENROUTER_URL", "http://localhost:9848/v1"
    ).rstrip("/")
    model = os.environ.get("ODYSSEUS_TOKENROUTER_MODEL", "m3-tiny")
    key = os.environ.get("ODYSSEUS_TOKENROUTER_KEY", "sk-no-key-required")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "."}],
        "max_tokens": 1,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, Exception):
        return False


def check_pi() -> bool:
    """`pi --version` exits 0."""
    try:
        result = subprocess.run(
            ["pi", "--version"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, Exception):
        return False


def check_imessage() -> bool:
    """~/Library/Messages/chat.db exists and is readable."""
    path = Path.home() / "Library" / "Messages" / "chat.db"
    if not path.exists():
        return False
    try:
        return os.access(path, os.R_OK)
    except OSError:
        return False


def check_whatsapp() -> Any:
    """Probe macOS Accessibility API; "skip" when PyObjC is unavailable."""
    try:
        from ApplicationServices import AXIsProcessTrusted  # type: ignore
    except ImportError:
        return "skip"

    try:
        return bool(AXIsProcessTrusted())
    except Exception:
        return "skip"


# ---------------------------------------------------------------------------
# Parallel runner + colored table printer
# ---------------------------------------------------------------------------
_CHECKS: list[tuple[str, Callable[[], Any]]] = [
    ("inbox", check_inbox),
    ("tokenrouter", check_tokenrouter),
    ("pi", check_pi),
    ("imessage", check_imessage),
    ("whatsapp", check_whatsapp),
]


def run_boot_check(timeout: float = 3.0) -> dict[str, Any]:
    """Run all checks concurrently, each capped at ``timeout`` seconds.

    Returns a dict like::

        {"inbox": True, "tokenrouter": True, "pi": True,
         "imessage": True, "whatsapp": "skip"}

    The value is ``True`` / ``False`` for hard checks, and the string
    ``"skip"`` when a check could not be performed (e.g. PyObjC missing).
    """
    results: dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(_CHECKS)) as ex:
        futures = {ex.submit(fn): name for name, fn in _CHECKS}
        for fut, name in futures.items():
            try:
                results[name] = fut.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                results[name] = "skip" if name == "whatsapp" else False
            except Exception:
                results[name] = "skip" if name == "whatsapp" else False

    _print_table(results)
    return results


def _format_status(value: Any) -> tuple[str, str]:
    """Map a check value to (display_label, ansi_color_code)."""
    if value is True:
        return "OK", _GREEN
    if value == "skip":
        return "SKIP", _YELLOW
    return "FAIL", _RED


def _print_table(results: dict[str, Any]) -> None:
    width = max(len(name) for name in results)
    print()
    print(_c("⚓  Odysseus Boot Check", _BOLD + _CYAN))
    print(_c("─" * (width + 14), _GRAY))

    for name, value in results.items():
        status, color = _format_status(value)
        if status == "OK":
            glyph, glyph_color = "✓", _GREEN
        elif status == "SKIP":
            glyph, glyph_color = "⊘", _YELLOW
        else:
            glyph, glyph_color = "✗", _RED
        print(
            f"  {_c(glyph, glyph_color)}  "
            f"{_c(name.ljust(width), _BOLD)}  "
            f"{_c(status, color)}"
        )
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    results = run_boot_check()
    # "skip" is informational; only hard False values are treated as failures.
    hard_fail = any(v is False for v in results.values())
    sys.exit(1 if hard_fail else 0)
