"""Odysseus startup checker.

Runs a fast, parallel battery of reachability tests against the services
Odysseus depends on at boot. Each check is bounded by a 3s timeout so a
single dead dependency cannot stall the launcher.

Checks:
    1. Inbox HTTP server  — GET http://localhost:9849/health
    2. TokenRouter API    — one minimal M3 chat completion
    3. pi CLI             — `pi --version` exits 0
    4. iMessage DB        — ~/Library/Messages/chat.db exists & is readable
    5. WhatsApp           — macOS Accessibility API trusted (SKIP if unavailable)

Returns a dict like:
    {"inbox": True, "tokenrouter": True, "pi": True,
     "imessage": True, "whatsapp": "skip"}
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# --- Optional deps (resolved lazily so a missing lib doesn't break boot) ---
try:
    import aiohttp  # type: ignore
except ImportError:  # pragma: no cover
    aiohttp = None  # type: ignore

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore


# --- ANSI palette -----------------------------------------------------------
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    BLUE   = "\033[34m"
    CYAN   = "\033[36m"


def _paint(text: str, color: str) -> str:
    return f"{color}{text}{C.RESET}"


def _ok(s: str = "  OK  ")   -> str: return _paint(s, C.GREEN + C.BOLD)
def _fail(s: str = " FAIL ") -> str: return _paint(s, C.RED   + C.BOLD)
def _skip(s: str = " SKIP ") -> str: return _paint(s, C.YELLOW + C.BOLD)


# --- Configuration ----------------------------------------------------------
CHECK_TIMEOUT_S: float = 3.0
INBOX_URL: str         = "http://localhost:9849/health"
TR_BASE_URL: str       = os.environ.get("ODYSSEUS_TR_BASE",   "https://api.tokenrouter.ai/v1")
TR_MODEL: str          = os.environ.get("ODYSSEUS_TR_MODEL",  "m3-tiny")
IMESSAGE_DB: Path      = Path.home() / "Library" / "Messages" / "chat.db"


# --- Individual checks ------------------------------------------------------
async def _check_inbox() -> bool:
    """1) Inbox HTTP health endpoint."""
    if aiohttp is not None:
        try:
            timeout = aiohttp.ClientTimeout(total=CHECK_TIMEOUT_S)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(INBOX_URL) as resp:
                    return 200 <= resp.status < 300
        except Exception:
            return False
    if requests is not None:  # pragma: no cover - fallback path
        def _do() -> bool:
            try:
                r = requests.get(INBOX_URL, timeout=CHECK_TIMEOUT_S)
                return 200 <= r.status_code < 300
            except Exception:
                return False
        return await asyncio.to_thread(_do)
    return False  # no HTTP client available


async def _check_tokenrouter() -> bool:
    """2) Single minimal M3 chat completion via TokenRouter (OpenAI-compatible)."""
    api_key = os.environ.get("ODYSSEUS_TR_KEY") or os.environ.get("OPENAI_API_KEY")
    if OpenAI is None or not api_key:
        return False

    def _do() -> bool:
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=TR_BASE_URL,
                timeout=CHECK_TIMEOUT_S,
            )
            resp = client.chat.completions.create(
                model=TR_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                temperature=0.0,
            )
            return bool(resp and getattr(resp, "choices", None))
        except Exception:
            return False
    return await asyncio.to_thread(_do)


async def _check_pi() -> bool:
    """3) `pi --version` resolves and exits 0."""
    pi_bin = shutil.which("pi")
    if not pi_bin:
        return False

    def _do() -> bool:
        try:
            res = subprocess.run(
                [pi_bin, "--version"],
                capture_output=True,
                text=True,
                timeout=CHECK_TIMEOUT_S,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False
    return await asyncio.to_thread(_do)


async def _check_imessage() -> bool:
    """4) iMessage SQLite is on disk and readable."""
    def _do() -> bool:
        try:
            if not IMESSAGE_DB.is_file():
                return False
            with open(IMESSAGE_DB, "rb") as f:
                f.read(16)  # touch a few bytes — proves we can open it
            return True
        except OSError:
            return False
    return await asyncio.to_thread(_do)


async def _check_whatsapp() -> Any:
    """5) macOS Accessibility permission. SKIP on non-macOS or if PyObjC missing."""
    if sys.platform != "darwin":
        return "skip"

    def _do() -> Any:
        try:
            from ApplicationServices import (  # type: ignore
                AXIsProcessTrustedWithOptions,
                kAXTrustedCheckOptionPrompt,
            )
        except Exception:
            return "skip"  # PyObjC / HIServices unavailable
        try:
            trusted = bool(
                AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: False})
            )
            return True if trusted else "skip"
        except Exception:
            return "skip"
    return await asyncio.to_thread(_do)


# --- Orchestration ----------------------------------------------------------
async def _run_all() -> dict[str, Any]:
    inbox, tr, pi_ok, im, wa = await asyncio.gather(
        _check_inbox(),
        _check_tokenrouter(),
        _check_pi(),
        _check_imessage(),
        _check_whatsapp(),
    )
    return {
        "inbox":       bool(inbox),
        "tokenrouter": bool(tr),
        "pi":          bool(pi_ok),
        "imessage":    bool(im),
        "whatsapp":    wa,           # True when accessible, else "skip"
    }


def _print_table(results: dict[str, Any]) -> None:
    rows: list[tuple[str, str, Any]] = [
        ("Inbox server",    "GET http://localhost:9849/health", results["inbox"]),
        ("TokenRouter API", f"chat.completions {TR_MODEL}/1tok",  results["tokenrouter"]),
        ("pi CLI",          "pi --version",                       results["pi"]),
        ("iMessage DB",     str(IMESSAGE_DB),                     results["imessage"]),
        ("WhatsApp",        "Accessibility (ApplicationServices)", results["whatsapp"]),
    ]
    name_w   = max(len(r[0]) for r in rows)
    target_w = max(len(r[1]) for r in rows)

    def status(v: Any) -> str:
        if v is True:   return _ok()
        if v == "skip": return _skip()
        return _fail()

    print()
    print(_paint("  Odysseus boot check", C.BOLD + C.CYAN))
    rule = "─" * (name_w + target_w + 18)
    print(_paint(rule, C.DIM))
    for name, target, value in rows:
        print(
            f"  {_paint(name, C.BOLD):<{name_w + 9}}  "
            f"{_paint(target, C.DIM):<{target_w + 4}}  {status(value)}"
        )
    print(_paint(rule, C.DIM))

    passed  = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v == "skip")
    failed  = sum(1 for v in results.values() if v is False)
    summary = "  ".join([
        _paint(f"{passed} passed",  C.GREEN),
        _paint(f"{failed} failed",   C.RED   if failed  else C.DIM),
        _paint(f"{skipped} skipped", C.YELLOW if skipped else C.DIM),
    ])
    print(f"  {summary}")
    print()


def check() -> dict[str, Any]:
    """Public entry point — runs all checks in parallel and returns the dict."""
    results = asyncio.run(_run_all())
    _print_table(results)
    return results


if __name__ == "__main__":
    check()
