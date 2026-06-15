"""
src/odysseus_boot.py

Startup checker for Odysseus. Verifies that all required services are
reachable before the main agent loop begins. All checks run in parallel
with a 3-second per-check timeout, so the worst-case total time is ~3s.

Checks
------
1. Inbox server    : GET  http://localhost:9849/health
2. TokenRouter API : POST a 1-token M3 completion request
3. pi CLI          : `pi --version` exits 0
4. iMessage DB     : ~/Library/Messages/chat.db exists & is readable
5. WhatsApp a11y   : macOS Accessibility API trust status

Returns
-------
dict with keys: ``inbox``, ``tokenrouter``, ``pi``, ``imessage``, ``whatsapp``
- the first four are True/False
- ``whatsapp`` is one of ``"ok"`` or ``"skip"`` (skip = not macOS or
  unable to determine)

Environment variables
----------------------
ODYSSEUS_INBOX_URL           default: http://localhost:9849/health
ODYSSEUS_TOKENROUTER_URL     default: http://localhost:9848/v1/chat/completions
ODYSSEUS_TOKENROUTER_MODEL   default: m3-tiny
ODYSSEUS_TOKENROUTER_API_KEY optional, sent as ``Authorization: Bearer ...``
NO_COLOR                     disable ANSI color output

Requires Python 3.9+ (for :func:`asyncio.to_thread`).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Union

__all__ = [
    "boot",
    "run_all_checks",
    "print_status_table",
    "PER_CHECK_TIMEOUT",
    "StatusValue",
]

# --- Configuration ----------------------------------------------------------
INBOX_URL: str = os.environ.get(
    "ODYSSEUS_INBOX_URL", "http://localhost:9849/health"
)
TOKENROUTER_URL: str = os.environ.get(
    "ODYSSEUS_TOKENROUTER_URL", "http://localhost:9848/v1/chat/completions"
)
TOKENROUTER_MODEL: str = os.environ.get("ODYSSEUS_TOKENROUTER_MODEL", "m3-tiny")
TOKENROUTER_API_KEY: str = os.environ.get("ODYSSEUS_TOKENROUTER_API_KEY", "")

# Hard cap per individual check (seconds). We give each wrapped coroutine a
# hair more (timeout + 0.5s) so the asyncio.wait_for() cancels cleanly even
# if the underlying thread is mid-syscall.
PER_CHECK_TIMEOUT: float = 3.0
_ASYNCIO_TIMEOUT: float = PER_CHECK_TIMEOUT + 0.5

# --- ANSI colors ------------------------------------------------------------
def _supports_color() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if not sys.stdout.isatty():
        return False
    return True


if _supports_color():
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
else:
    GREEN = RED = YELLOW = CYAN = BOLD = DIM = RESET = ""


# --- Public types -----------------------------------------------------------
StatusValue = Union[bool, str]


# --- Individual checks ------------------------------------------------------
async def check_inbox() -> bool:
    """1. Inbox server health endpoint."""
    def _do() -> bool:
        try:
            req = urllib.request.Request(INBOX_URL, method="GET")
            with urllib.request.urlopen(req, timeout=PER_CHECK_TIMEOUT) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, OSError, TimeoutError):
            return False
        except Exception:
            return False

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_do), timeout=_ASYNCIO_TIMEOUT
        )
    except asyncio.TimeoutError:
        return False
    except Exception:
        return False


async def check_tokenrouter() -> bool:
    """2. TokenRouter API: send a tiny M3 completion request."""
    def _do() -> bool:
        payload = {
            "model": TOKENROUTER_MODEL,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            TOKENROUTER_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        if TOKENROUTER_API_KEY:
            req.add_header("Authorization", f"Bearer {TOKENROUTER_API_KEY}")
        try:
            with urllib.request.urlopen(req, timeout=PER_CHECK_TIMEOUT) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, OSError, TimeoutError):
            return False
        except Exception:
            return False

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_do), timeout=_ASYNCIO_TIMEOUT
        )
    except asyncio.TimeoutError:
        return False
    except Exception:
        return False


async def check_pi() -> bool:
    """3. `pi --version` succeeds."""
    def _do() -> bool:
        # Cheap pre-check: is `pi` even on PATH?
        if shutil.which("pi") is None:
            return False
        try:
            result = subprocess.run(
                ["pi", "--version"],
                capture_output=True,
                timeout=PER_CHECK_TIMEOUT,
                text=True,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
        except Exception:
            return False

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_do), timeout=_ASYNCIO_TIMEOUT
        )
    except asyncio.TimeoutError:
        return False
    except Exception:
        return False


async def check_imessage() -> bool:
    """4. ~/Library/Messages/chat.db exists and is readable."""
    def _do() -> bool:
        try:
            db_path = Path.home() / "Library" / "Messages" / "chat.db"
            if not db_path.exists() or not db_path.is_file():
                return False
            if not os.access(str(db_path), os.R_OK):
                return False
            # Probe by reading the SQLite header to confirm real readability
            # (Full Disk Access may be required on recent macOS).
            with open(db_path, "rb") as f:
                header = f.read(16)
            return header.startswith(b"SQLite format 3\x00")
        except (OSError, PermissionError):
            return False
        except Exception:
            return False

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_do), timeout=_ASYNCIO_TIMEOUT
        )
    except asyncio.TimeoutError:
        return False
    except Exception:
        return False


async def check_whatsapp() -> str:
    """
    5. macOS Accessibility permission for WhatsApp automation.

    Returns:
        "ok"   - we can confirm the process is trusted for accessibility
        "skip" - not on macOS, or we can't determine trust (e.g. PyObjC
                 and osascript both unavailable / failed)
    """
    if sys.platform != "darwin":
        return "skip"

    # Path A: PyObjC (most accurate, no side effects).
    try:
        from ApplicationServices import (  # type: ignore[import-not-found]
            AXIsProcessTrusted,
        )

        return "ok" if bool(AXIsProcessTrusted()) else "skip"
    except ImportError:
        pass
    except Exception:
        pass

    # Path B: osascript probe. Listing processes via System Events will
    # succeed only if the calling process is accessibility-trusted.
    def _do() -> str:
        try:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to count processes',
                ],
                capture_output=True,
                timeout=PER_CHECK_TIMEOUT,
                text=True,
            )
            return "ok" if result.returncode == 0 else "skip"
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return "skip"
        except Exception:
            return "skip"

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_do), timeout=_ASYNCIO_TIMEOUT
        )
    except asyncio.TimeoutError:
        return "skip"
    except Exception:
        return "skip"


# --- Orchestration ----------------------------------------------------------
def _coerce_bool(r: Any) -> bool:
    if isinstance(r, BaseException):
        return False
    if not isinstance(r, bool):
        return False
    return r


def _coerce_whatsapp(r: Any) -> str:
    if isinstance(r, BaseException):
        return "skip"
    if isinstance(r, str) and r in ("ok", "skip"):
        return r
    return "skip"


async def run_all_checks() -> Dict[str, StatusValue]:
    """
    Run all five checks concurrently. Each check is bounded by
    ``PER_CHECK_TIMEOUT``; the whole batch finishes in roughly that
    same wall-clock window since they run in parallel.
    """
    coros = [
        check_inbox(),
        check_tokenrouter(),
        check_pi(),
        check_imessage(),
        check_whatsapp(),
    ]
    results = await asyncio.gather(*coros, return_exceptions=True)

    return {
        "inbox": _coerce_bool(results[0]),
        "tokenrouter": _coerce_bool(results[1]),
        "pi": _coerce_bool(results[2]),
        "imessage": _coerce_bool(results[3]),
        "whatsapp": _coerce_whatsapp(results[4]),
    }


# --- Pretty printing --------------------------------------------------------
_LABEL_ORDER = ("inbox", "tokenrouter", "pi", "imessage", "whatsapp")
_LABEL_TITLE = {
    "inbox": "Inbox server",
    "tokenrouter": "TokenRouter API",
    "pi": "pi CLI",
    "imessage": "iMessage DB",
    "whatsapp": "WhatsApp a11y",
}


def _visible_status(value: StatusValue) -> str:
    if value is True or value == "ok":
        return "OK"
    if value is False or value == "fail":
        return "FAIL"
    if value == "skip":
        return "SKIP"
    return str(value)


def _color_status(value: StatusValue) -> str:
    label = _visible_status(value)
    if label == "OK":
        return f"{GREEN}{label}{RESET}"
    if label == "FAIL":
        return f"{RED}{label}{RESET}"
    if label == "SKIP":
        return f"{YELLOW}{label}{RESET}"
    return f"{DIM}{label}{RESET}"


def print_status_table(results: Dict[str, StatusValue]) -> None:
    """Print a colored status table to stdout."""
    name_w = max(
        len("Service"),
        max(len(_LABEL_TITLE.get(k, k)) for k in _LABEL_ORDER if k in results),
    )
    status_w = 6  # "OK" / "FAIL" / "SKIP"

    bar = f"{DIM}{'─' * (name_w + status_w + 6)}{RESET}"
    title = f"{BOLD}Odysseus Boot Check{RESET} {DIM}(per-check timeout: {PER_CHECK_TIMEOUT:.0f}s){RESET}"

    print()
    print(title)
    print(bar)
    print(
        f"  {BOLD}{'Service'.ljust(name_w)}{RESET}  "
        f"{BOLD}{'Status'.ljust(status_w)}{RESET}"
    )
    print(bar)
    for key in _LABEL_ORDER:
        if key not in results:
            continue
        value = results[key]
        label = _LABEL_TITLE.get(key, key).ljust(name_w)
        colored = _color_status(value)
        visible = _visible_status(value)
        pad = max(0, status_w - len(visible))
        print(f"  {label}  {colored}{' ' * pad}")
    print(bar)
    print()


# --- Public entrypoint ------------------------------------------------------
async def boot() -> Dict[str, StatusValue]:
    """Run all checks, print the colored table, and return the result dict."""
    results = await run_all_checks()
    print_status_table(results)
    return results


def main() -> int:
    try:
        results = asyncio.run(boot())
    except KeyboardInterrupt:
        sys.stdout.write(f"\n{YELLOW}Boot check interrupted.{RESET}\n")
        return 130

    # Skip is non-fatal; only hard failures flip the exit code.
    all_required_ok = all(
        v in (True, "ok", "skip") for k, v in results.items() if k != "whatsapp"
    ) and results.get("whatsapp", "skip") in ("ok", "skip")
    return 0 if all_required_ok else 1


if __name__ == "__main__":
    sys.exit(main())
