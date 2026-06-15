"""
odysseus_boot.py — startup checker for the Odysseus runtime.

Runs a small set of fast, parallel health checks (3s timeout each) against
every external dependency the agent needs:

    1. inbox HTTP server      (http://localhost:9849/health)
    2. TokenRouter API        (one tiny M3 call)
    3. pi CLI on PATH         (`pi --version`)
    4. iMessage DB readable   (~/Library/Messages/chat.db)
    5. WhatsApp accessibility (macOS AX API, OK/SKIP — never fatal)

Usage:
    python -m odysseus_boot        # prints a colored table, returns a dict
    python -c "from odysseus_boot import run_checks; print(run_checks())"
"""
from __future__ import annotations

import concurrent.futures
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

# `requests` is the only hard third-party dep; degrade gracefully if missing.
try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore


# ---------------------------------------------------------------------------
# Colored output helpers
# ---------------------------------------------------------------------------

_NO_COLOR = os.environ.get("NO_COLOR") is not None
_USE_COLOR = sys.stdout.isatty() and not _NO_COLOR


def _c(code: str, text: str) -> str:
    """Wrap `text` in ANSI color codes (no-op if not a TTY)."""
    if not _USE_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _ok() -> str:    return _c("32", "  ✓ OK   ")
def _fail() -> str:  return _c("31", "  ✗ FAIL ")
def _skip() -> str:  return _c("33", "  ~ SKIP ")


# ---------------------------------------------------------------------------
# Individual checks — each must accept a timeout and return bool | str.
# ---------------------------------------------------------------------------

def check_inbox(timeout: float) -> bool:
    """GET http://localhost:9849/health — 2xx is OK."""
    if requests is None:
        return False
    try:
        r = requests.get("http://localhost:9849/health", timeout=timeout)
        return 200 <= r.status_code < 300
    except Exception:
        return False


def check_tokenrouter(timeout: float) -> bool:
    """One tiny M3 call (max_tokens=1) through the TokenRouter proxy."""
    if requests is None:
        return False
    endpoint = os.environ.get(
        "TOKENROUTER_URL", "http://localhost:9848/v1/messages"
    )
    api_key = (
        os.environ.get("TOKENROUTER_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
    )
    if not api_key:
        return False
    try:
        r = requests.post(
            endpoint,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": os.environ.get("TOKENROUTER_MODEL", "MiniMax-M3"),
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "."}],
            },
            timeout=timeout,
        )
        return r.ok
    except Exception:
        return False


def check_pi(timeout: float) -> bool:
    """`pi --version` exits 0."""
    pi_path = shutil.which("pi")
    if not pi_path:
        return False
    try:
        result = subprocess.run(
            [pi_path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_imessage(timeout: float) -> bool:
    """~/Library/Messages/chat.db exists and is openable."""
    db = Path.home() / "Library" / "Messages" / "chat.db"
    if not db.exists():
        return False
    try:
        # Opening in binary mode is enough to confirm readability on macOS;
        # the SIP-protected full-disk-access case is a separate concern.
        with open(db, "rb"):
            return True
    except OSError:
        return False


def check_whatsapp(timeout: float) -> str:
    """macOS Accessibility API — return 'ok' / 'skip'. Never 'fail'."""
    if sys.platform != "darwin":
        return "skip"
    try:
        # PyObjC path — the canonical macOS way.
        from ApplicationServices import (  # type: ignore
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )
        # Pass False so we *probe* without spawning a system prompt.
        trusted = bool(
            AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: False})
        )
        return "ok" if trusted else "skip"
    except Exception:
        # No PyObjC, or AX API not reachable from this process — treat as skip.
        return "skip"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

# Order is also the display order in the table.
CHECKS: List[Tuple[str, Callable[[float], Any]]] = [
    ("inbox",       check_inbox),
    ("tokenrouter", check_tokenrouter),
    ("pi",          check_pi),
    ("imessage",    check_imessage),
    ("whatsapp",    check_whatsapp),
]

CHECK_TIMEOUT = 3.0


def run_checks(timeout: float = CHECK_TIMEOUT) -> Dict[str, Any]:
    """Run all checks in parallel; return a {name: status} dict."""
    results: Dict[str, Any] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CHECKS)) as ex:
        future_to_name = {
            ex.submit(fn, timeout): name for name, fn in CHECKS
        }
        # Outer ceiling: even if a check somehow ignores its timeout, the
        # whole boot probe still completes within ~timeout+slack seconds.
        try:
            done, _ = concurrent.futures.wait(
                future_to_name.values(),
                timeout=timeout + 1.0,
                return_when=concurrent.futures.ALL_COMPLETED,
            )
        except Exception:
            done = set()

        for fut, name in future_to_name.items():
            if fut not in done or not fut.done():
                # Timed out — whatsapp is the only one allowed to be 'skip'.
                results[name] = "skip" if name == "whatsapp" else False
                continue
            try:
                results[name] = fut.result()
            except Exception:
                results[name] = "skip" if name == "whatsapp" else False

    # Defensive: ensure every declared check is present in the result dict.
    for name, _ in CHECKS:
        results.setdefault(name, "skip" if name == "whatsapp" else False)

    return results


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def _format_status(value: Any) -> str:
    if value is True:
        return _ok()
    if value is False:
        return _fail()
    if isinstance(value, str):
        v = value.lower()
        if v == "ok":   return _ok()
        if v == "skip": return _skip()
    return _c("90", f"  ? {value} ")


def print_table(results: Dict[str, Any]) -> None:
    name_w = max(len(n) for n, _ in CHECKS) + 2
    bar = _c("90", "─" * (name_w + 14))

    print(_c("1;97", "Odysseus boot check"))
    print(bar)
    for name, _ in CHECKS:
        status = _format_status(results.get(name))
        print(f"  {_c('97', name.ljust(name_w))}{status}")
    print(bar)

    # One-line summary — handy for logs / CI.
    summary = "  ".join(
        f"{name}={results.get(name)!r}" for name, _ in CHECKS
    )
    print(_c("90", summary))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> Dict[str, Any]:
    results = run_checks()
    print_table(results)
    return results


if __name__ == "__main__":
    main()
