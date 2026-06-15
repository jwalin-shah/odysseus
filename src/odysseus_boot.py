#!/usr/bin/env python3
"""
Odysseus Boot Checker
=====================

Fast, parallel startup probe that verifies Odysseus can reach all of its
required services before the main runtime takes over.

Checks (each with a 3s timeout, executed concurrently):

    1. inbox server      GET http://localhost:9849/health            → OK / FAIL
    2. TokenRouter API   1 tiny M3 call                              → OK / FAIL
    3. pi CLI available  `pi --version`                              → OK / FAIL
    4. iMessage DB       ~/Library/Messages/chat.db readable         → OK / FAIL
    5. WhatsApp access   macOS Accessibility API window list         → OK / SKIP

Returns a dict shaped like::

    {"inbox": True, "tokenrouter": True, "pi": True,
     "imessage": True, "whatsapp": "skip"}

…and prints a colored status table to stdout.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List


# ──────────────────────────────────────────────────────────────────────────────
# ANSI colors (no-op when stdout isn't a TTY)
# ──────────────────────────────────────────────────────────────────────────────
class C:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def _paint(s: str, code: str) -> str:
    return f"{code}{s}{C.RESET}" if sys.stdout.isatty() else s


# ──────────────────────────────────────────────────────────────────────────────
# Result model
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class CheckResult:
    name: str
    status: str  # "OK" | "FAIL" | "SKIP"
    detail: str = ""

    def to_value(self) -> Any:
        """Map status to the dict value expected by callers."""
        if self.status == "SKIP":
            return "skip"
        return self.status == "OK"


# ──────────────────────────────────────────────────────────────────────────────
# Individual checks
# ──────────────────────────────────────────────────────────────────────────────
def check_inbox(timeout: float = 3.0) -> CheckResult:
    url = "http://localhost:9849/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(64).decode("utf-8", errors="replace").strip()
            if 200 <= resp.status < 300:
                return CheckResult("inbox", "OK", f"HTTP {resp.status} {body[:24]}")
            return CheckResult("inbox", "FAIL", f"HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        return CheckResult("inbox", "FAIL", f"HTTP {e.code}")
    except urllib.error.URLError as e:
        return CheckResult("inbox", "FAIL", f"unreachable: {e.reason}"[:40])
    except Exception as e:  # noqa: BLE001
        return CheckResult("inbox", "FAIL", str(e)[:40])


def check_tokenrouter(timeout: float = 3.0) -> CheckResult:
    api_key = os.environ.get("TOKENROUTER_API_KEY")
    endpoint = os.environ.get(
        "TOKENROUTER_ENDPOINT",
        "https://api.tokenrouter.io/v1/chat/completions",
    )
    model = os.environ.get("TOKENROUTER_MODEL", "M3")

    if not api_key:
        return CheckResult("tokenrouter", "FAIL", "TOKENROUTER_API_KEY unset")

    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if 200 <= resp.status < 300:
                return CheckResult("tokenrouter", "OK", f"HTTP {resp.status}")
            return CheckResult("tokenrouter", "FAIL", f"HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        return CheckResult("tokenrouter", "FAIL", f"HTTP {e.code}")
    except Exception as e:  # noqa: BLE001
        return CheckResult("tokenrouter", "FAIL", str(e)[:40])


def check_pi(timeout: float = 3.0) -> CheckResult:
    if shutil.which("pi") is None:
        return CheckResult("pi", "FAIL", "not found in PATH")
    try:
        proc = subprocess.run(
            ["pi", "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CheckResult("pi", "FAIL", "timeout")
    except Exception as e:  # noqa: BLE001
        return CheckResult("pi", "FAIL", str(e)[:40])

    if proc.returncode == 0:
        out = (proc.stdout or proc.stderr).strip().splitlines()
        return CheckResult("pi", "OK", out[0][:40] if out else "")
    return CheckResult("pi", "FAIL", f"exit {proc.returncode}")


def check_imessage() -> CheckResult:
    if platform.system() != "Darwin":
        return CheckResult("imessage", "FAIL", "macOS only")

    db = Path.home() / "Library" / "Messages" / "chat.db"
    if not db.exists():
        return CheckResult("imessage", "FAIL", "chat.db missing")
    if not os.access(str(db), os.R_OK):
        return CheckResult("imessage", "FAIL", "no read access (Full Disk Access?)")
    try:
        size = db.stat().st_size
        return CheckResult("imessage", "OK", f"{size:,} bytes")
    except Exception as e:  # noqa: BLE001
        return CheckResult("imessage", "FAIL", str(e)[:40])


def check_whatsapp() -> CheckResult:
    """Try macOS Accessibility API. Anything that prevents a real probe → SKIP."""
    if platform.system() != "Darwin":
        return CheckResult("whatsapp", "SKIP", "non-macOS")

    # Preferred path: PyObjC Quartz (full accessibility enumeration)
    try:
        import Quartz  # type: ignore

        wins = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID
        )
        if wins:
            return CheckResult("whatsapp", "OK", f"{len(wins)} windows listed")
        return CheckResult("whatsapp", "OK", "Quartz reachable")
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        return CheckResult("whatsapp", "SKIP", str(e)[:40])

    # Fallback: System Events via osascript
    try:
        proc = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of every process',
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return CheckResult("whatsapp", "OK", "System Events granted")
        return CheckResult("whatsapp", "SKIP", "System Events denied")
    except subprocess.TimeoutExpired:
        return CheckResult("whatsapp", "SKIP", "osascript timeout")
    except FileNotFoundError:
        return CheckResult("whatsapp", "SKIP", "osascript missing")
    except Exception as e:  # noqa: BLE001
        return CheckResult("whatsapp", "SKIP", str(e)[:40])


# ──────────────────────────────────────────────────────────────────────────────
# Orchestration
# ──────────────────────────────────────────────────────────────────────────────
# Canonical order is preserved in the printed table and returned dict.
CHECKS: List[tuple] = [
    ("inbox", check_inbox),
    ("tokenrouter", check_tokenrouter),
    ("pi", check_pi),
    ("imessage", check_imessage),
    ("whatsapp", check_whatsapp),
]


def _status_glyph(status: str) -> str:
    if status == "OK":
        return _paint("✓ OK  ", C.GREEN)
    if status == "FAIL":
        return _paint("✗ FAIL ", C.RED)
    if status == "SKIP":
        return _paint("→ SKIP ", C.YELLOW)
    return status


def print_table(results: List[CheckResult]) -> None:
    name_w = max(len(r.name) for r in results)
    bar = _paint("─" * 60, C.DIM)
    print()
    print(_paint("  Odysseus Boot Check", C.BOLD))
    print(bar)
    for r in results:
        glyph = _status_glyph(r.status)
        detail = _paint(f"  {r.detail}", C.BLUE) if r.detail else ""
        print(f"  {r.name:<{name_w}}  {glyph}{detail}")
    print(bar)


def run_checks(timeout: float = 3.0) -> Dict[str, Any]:
    """Run every check in parallel and return the canonical result dict."""
    results: Dict[str, CheckResult] = {}

    with ThreadPoolExecutor(max_workers=len(CHECKS)) as pool:
        future_to_name = {
            pool.submit(fn, timeout): name for name, fn in CHECKS
        }
        for fut in as_completed(future_to_name):
            name = future_to_name[fut]
            try:
                results[name] = fut.result()
            except Exception as e:  # noqa: BLE001
                results[name] = CheckResult(name, "FAIL", str(e)[:40])

    ordered = [results[name] for name, _ in CHECKS if name in results]
    print_table(ordered)
    return {r.name: r.to_value() for r in ordered}


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    result = run_checks()
    print(json.dumps(result, indent=2))
    failed = [k for k, v in result.items() if v is False]
    if failed:
        print(_paint(f"\n✗ Boot check failed: {', '.join(failed)}", C.RED))
        return 1
    print(_paint("\n✓ All required services reachable.", C.GREEN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
