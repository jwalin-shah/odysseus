#!/usr/bin/env python3
"""
odysseus_boot.py — Startup checker that verifies Odysseus can reach all services.

Runs five fast, parallel health checks (3s timeout each) and prints a
colored status table to stdout. Returns a dict of results so the caller
can branch on success/failure.

    {
        "inbox":       True,    # http://localhost:9849/health
        "tokenrouter": True,    # 1 tiny M3 call to the API
        "pi":          True,    # `pi --version` exits 0
        "imessage":    True,    # ~/Library/Messages/chat.db readable
        "whatsapp":    "skip",  # macOS Accessibility probe — OK/FAIL/skip
    }

Exits with status code 1 if any required check fails (SKIP does not count).
"""

from __future__ import annotations

import concurrent.futures
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict

# ── ANSI colors ──────────────────────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _c(text: str, color: str) -> str:
    """Colorize text — silently pass through if stdout is not a TTY."""
    return f"{color}{text}{RESET}" if sys.stdout.isatty() else text


# ── Individual checks ────────────────────────────────────────────────────────
def check_inbox(timeout: float = 3.0) -> bool:
    """GET http://localhost:9849/health — expect any 2xx."""
    try:
        req = urllib.request.Request(
            "http://localhost:9849/health", method="GET"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError):
        return False
    except Exception:
        return False


def check_tokenrouter(timeout: float = 3.0) -> bool:
    """
    One tiny M3 call to TokenRouter. Reads configuration from env:
        TOKENROUTER_API_KEY   (required for a 200, but a 401 still means
                               the endpoint is reachable — we treat any
                               HTTP response that isn't a connection
                               error as success)
        TOKENROUTER_BASE_URL  (default: https://api.tokenrouter.ai/v1)
        TOKENROUTER_MODEL     (default: m3-tiny)
    """
    base_url = os.environ.get(
        "TOKENROUTER_BASE_URL", "https://api.tokenrouter.ai/v1"
    )
    model = os.environ.get("TOKENROUTER_MODEL", "m3-tiny")
    api_key = os.environ.get("TOKENROUTER_API_KEY", "")

    payload = (
        '{"model":"' + model + '",'
        '"messages":[{"role":"user","content":"ping"}],'
        '"max_tokens":1,"stream":false}'
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 500  # 4xx means the API is up
    except (urllib.error.URLError, OSError, TimeoutError):
        return False
    except Exception:
        return False


def check_pi(timeout: float = 3.0) -> bool:
    """`pi --version` exits 0."""
    pi_path = shutil.which("pi")
    if pi_path is None:
        return False
    try:
        result = subprocess.run(
            [pi_path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False
    except Exception:
        return False


def check_imessage(timeout: float = 3.0) -> bool:  # noqa: ARG001
    """~/Library/Messages/chat.db exists and is readable."""
    db_path = Path.home() / "Library" / "Messages" / "chat.db"
    if not db_path.exists():
        return False
    try:
        with open(db_path, "rb") as fh:
            fh.read(16)  # touch the first page
        return True
    except (OSError, PermissionError):
        return False
    except Exception:
        return False


def check_whatsapp(timeout: float = 3.0) -> Any:
    """
    Probe macOS Accessibility permission for WhatsApp. Returns:
        True   — permission granted
        False  — permission denied
        "skip" — not on macOS, or framework unavailable
    """
    if sys.platform != "darwin":
        return "skip"

    # Method 1: pyobjc bridge (most reliable)
    try:
        import objc  # type: ignore  # noqa: F401
        from ApplicationServices import (  # type: ignore
            AXIsProcessTrusted,
        )
        return bool(AXIsProcessTrusted())
    except ImportError:
        pass
    except Exception:
        pass

    # Method 2: AppleScript probe via System Events
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to count processes'],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        err = (result.stderr or "").lower()
        if "not authorized" in err or "assistive access" in err \
                or "accessibility" in err:
            return False
        if result.returncode == 0 and result.stdout.strip().isdigit():
            return True
        return "skip"
    except subprocess.TimeoutExpired:
        return "skip"
    except Exception:
        return "skip"


# ── Orchestration ────────────────────────────────────────────────────────────
CHECKS: Dict[str, Callable[..., Any]] = {
    "inbox":       check_inbox,
    "tokenrouter": check_tokenrouter,
    "pi":          check_pi,
    "imessage":    check_imessage,
    "whatsapp":    check_whatsapp,
}

DEFAULT_TIMEOUT = 3.0


def run_checks(timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Run every check in parallel. Each is bounded by `timeout` seconds."""
    results: Dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(CHECKS)
    ) as ex:
        futures = {
            name: ex.submit(fn, timeout) for name, fn in CHECKS.items()
        }
        for name, future in futures.items():
            try:
                results[name] = future.result(timeout=timeout + 0.5)
            except Exception:
                # Preserve the "skip" sentinel for whatsapp on hard errors
                results[name] = False if name != "whatsapp" else "skip"
    return results


# ── Pretty printing ─────────────────────────────────────────────────────────
def _format_status(value: Any) -> str:
    if value is True:
        return _c("  OK  ", GREEN)
    if value is False:
        return _c(" FAIL ", RED)
    if value == "skip":
        return _c(" SKIP ", YELLOW)
    return str(value)


def print_table(results: Dict[str, Any]) -> None:
    """Print a compact, colored status table to stdout."""
    label_w = max(len("Service"), max(len(k) for k in results))
    bar = _c("─" * (label_w + 18), DIM)

    print()
    print(_c(f"{' ODYSSEUS BOOT ':─^50}", BOLD + CYAN))
    print(bar)
    print(
        _c("Service".ljust(label_w), BOLD)
        + "  "
        + _c("Status".rjust(8), BOLD)
    )
    print(bar)
    for name, value in results.items():
        label = name.ljust(label_w)
        status = _format_status(value)
        print(f"  {label}  {status}")
    print(bar)

    n_ok = sum(1 for v in results.values() if v is True)
    n_fail = sum(1 for v in results.values() if v is False)
    n_skip = sum(1 for v in results.values() if v == "skip")
    total = len(results)

    parts = [_c(f"{n_ok}/{total} OK", GREEN)]
    if n_fail:
        parts.append(_c(f"{n_fail} FAIL", RED))
    if n_skip:
        parts.append(_c(f"{n_skip} SKIP", YELLOW))
    print("  " + _c("Summary:", BOLD) + "  " + ", ".join(parts))
    print()


# ── Entry point ──────────────────────────────────────────────────────────────
def main() -> Dict[str, Any]:
    """Run all checks, print the table, and return the results dict."""
    results = run_checks()
    print_table(results)
    return results


if __name__ == "__main__":
    result = main()
    # Non-zero exit if any *required* check failed (SKIP is fine)
    failed = any(v is False for v in result.values())
    sys.exit(1 if failed else 0)
