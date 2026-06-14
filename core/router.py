# core/router.py
"""Intelligent task routing — classify, quota-check, dispatch.

Reads live quota data from the platform quota-core system, classifies
incoming tasks as code / research / chat, and dispatches each to the
cheapest suitable backend:

* **code** → CLI subprocess: claude (ca/cb) → codex → gemini (fallback chain)
* **research** → Gemini endpoint via llm_call_async
* **chat** → cheapest available model (MiniMax M3 preferred)

CLI adapter table
-----------------
_CLI_ADAPTERS is the single config point for all CLI backends.  Each entry:
  {
    "name":        str   – logical name used in traces/logs
    "provider_key":str   – key in quota-live.json providers dict
    "binary":      str   – binary name (resolved via shutil.which at runtime)
    "build_argv":  callable(binary, task) -> list[str]
    "build_env":   callable(env) -> dict  (or None to pass env unchanged)
    "is_exhausted":callable(prov_data) -> bool
    "parse_output":callable(stdout, stderr, returncode) -> (response_text, session_id|None)
    "supports_resume": bool  – True only for claude (session_id based resume)
  }

Code tasks walk the adapter table in order (claude-ca, claude-cb, codex, gemini).
The first non-exhausted adapter with an available binary wins.

NOTE: gemini CLI EOL 2026-06-18 — Antigravity migration pending.
      To swap: update the "binary" and "build_argv" entries for the gemini
      adapter row in _CLI_ADAPTERS below; no other code changes needed.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths & tunables
# ---------------------------------------------------------------------------

QUOTA_LIVE_PATH = Path(
    "/Users/jwalinshah/projects/platform/systems/quota-core/data/quota-live.json"
)
_QUOTA_CACHE_TTL = 60          # seconds – re-read file after this
_QUOTA_STALE_THRESHOLD = 600   # seconds – warn if data older than this
_CODE_TIMEOUT = 300            # subprocess timeout for code tasks

# Claude accounts in priority order: cheapest / most-available first.
# `ca`/`cb` are zsh functions and invisible to this server process, so
# dispatch always execs the real `claude` binary and selects the account via
# CLAUDE_CONFIG_DIR — the same mechanism the shell functions use.
# Each entry is (account, provider_key_in_quota_data, config_dir).
_CLI_PRIORITY: List[Tuple[str, str, str]] = [
    ("ca", "ca", "~/.claude-a"),
    ("cb", "cb", "~/.claude-b"),
]

# ---------------------------------------------------------------------------
# CLI adapter helpers
# ---------------------------------------------------------------------------


def _claude_is_exhausted(prov_data: dict) -> bool:
    return prov_data.get("status") in ("exhausted", "rate_limited")


def _codex_is_exhausted(prov_data: dict) -> bool:
    # weekly_pct_remaining is a string like "10" — treat <=5 as exhausted.
    if prov_data.get("status") in ("exhausted", "rate_limited"):
        return True
    try:
        remaining = int(prov_data.get("weekly_pct_remaining", 100))
        return remaining <= 5
    except (TypeError, ValueError):
        return False


def _gemini_is_exhausted(prov_data: dict) -> bool:
    if prov_data.get("status") in ("exhausted", "rate_limited"):
        return True
    # Check models dict: if any model has pct_used >= 100 we treat it as exhausted.
    try:
        models = prov_data.get("quotas", {}).get("models", {})
        for _model_key, mdata in models.items():
            pct_used = int(mdata.get("pct_used", 0))
            if pct_used >= 100:
                return True
    except (TypeError, ValueError, AttributeError):
        pass
    return False


def _claude_build_argv(binary: str, task: str, config_dir: Optional[str] = None) -> List[str]:
    """Build argv for claude: use --output-format json to capture session_id."""
    return [binary, "--print", "--output-format", "json", "-p", task]


def _claude_parse_output(stdout: str, stderr: str, returncode: int) -> Tuple[str, Optional[str]]:
    """Parse claude --output-format json output.

    JSON shape (verified against real run):
      {"type":"result","subtype":"success","result":"<text>","session_id":"<uuid>", ...}

    Returns (response_text, session_id).
    """
    stdout = stdout.strip()
    if stdout:
        try:
            data = json.loads(stdout)
            text = data.get("result") or ""
            session_id = data.get("session_id")
            return text, session_id
        except json.JSONDecodeError:
            pass
    return stdout or stderr.strip(), None


def _codex_build_argv(binary: str, task: str, config_dir: Optional[str] = None) -> List[str]:
    """Build argv for codex exec (non-interactive).

    `codex exec <prompt>` runs non-interactively and writes the last agent
    message to stdout (or use --json for JSONL events).  We use plain exec
    without --json so stdout is the final text response directly.
    """
    return [binary, "exec", task]


def _codex_parse_output(stdout: str, stderr: str, returncode: int) -> Tuple[str, Optional[str]]:
    """Codex output: plain text on stdout.  No session_id concept."""
    return (stdout.strip() or stderr.strip()), None


def _gemini_build_argv(binary: str, task: str, config_dir: Optional[str] = None) -> List[str]:
    """Build argv for gemini non-interactive mode.

    NOTE: gemini CLI EOL 2026-06-18.  Antigravity CLI migration pending.
    Swap: update binary path and this function for the new CLI's flags.
    Uses -p / --prompt flag for headless/non-interactive execution.
    """
    return [binary, "-p", task]


def _gemini_parse_output(stdout: str, stderr: str, returncode: int) -> Tuple[str, Optional[str]]:
    """Gemini output: plain text on stdout.  No session_id concept."""
    return (stdout.strip() or stderr.strip()), None


# ---------------------------------------------------------------------------
# CLI adapter table — code tasks walk this list in order
# ---------------------------------------------------------------------------
# Each entry drives one CLI backend.  Fields:
#   name            – logical name for traces / logs
#   provider_key    – key into quota-live.json "providers" dict
#   binary          – binary name for shutil.which
#   config_dir      – CLAUDE_CONFIG_DIR value (claude only, else None)
#   build_argv      – callable(binary, task, config_dir) -> argv list
#   build_env       – callable(env_dict) -> env_dict  (or None = pass through)
#   is_exhausted    – callable(provider_data_dict) -> bool
#   parse_output    – callable(stdout, stderr, returncode) -> (text, session_id|None)
#   supports_resume – True if the binary supports session resume (claude only)
#
# Code tasks prefer claude ca → cb, then codex, then gemini as last resort.
# DO NOT silently change this order — it is the cost/quality priority.

_CLI_ADAPTERS: List[Dict[str, Any]] = [
    {
        "name": "claude-ca",
        "provider_key": "ca",
        "binary": "claude",
        "config_dir": "~/.claude-a",
        "build_argv": _claude_build_argv,
        "build_env": None,
        "is_exhausted": _claude_is_exhausted,
        "parse_output": _claude_parse_output,
        "supports_resume": True,
    },
    {
        "name": "claude-cb",
        "provider_key": "cb",
        "binary": "claude",
        "config_dir": "~/.claude-b",
        "build_argv": _claude_build_argv,
        "build_env": None,
        "is_exhausted": _claude_is_exhausted,
        "parse_output": _claude_parse_output,
        "supports_resume": True,
    },
    {
        "name": "codex",
        "provider_key": "codex",
        "binary": "codex",
        "config_dir": None,
        "build_argv": _codex_build_argv,
        "build_env": None,
        "is_exhausted": _codex_is_exhausted,
        "parse_output": _codex_parse_output,
        "supports_resume": False,
    },
    {
        # NOTE: gemini CLI EOL 2026-06-18 — Antigravity migration pending.
        # To swap: change "binary" and "build_argv" here only.
        "name": "gemini",
        "provider_key": "gemini",
        "binary": "gemini",
        "config_dir": None,
        "build_argv": _gemini_build_argv,
        "build_env": None,
        "is_exhausted": _gemini_is_exhausted,
        "parse_output": _gemini_parse_output,
        "supports_resume": False,
    },
]

# ---------------------------------------------------------------------------
# Task-classification patterns
# ---------------------------------------------------------------------------

_CODE_PATTERNS = re.compile(
    r"(?i)"
    r"(?:\.py|\.js|\.ts|\.go|\.rs|\.java|\.c|\.h|\.cpp|\.rb|\.sh)\b"   # file extensions
    r"|def\s+\w+|class\s+\w+|function\s+\w+"                           # function/class defs
    r"|```"                                                              # code fences
    r"|\b(?:write|fix|implement|refactor|debug|test|deploy|build"
    r"|compile|lint|commit|push|merge|rebase|import|export)\b"
    r"|(?:/[\w./]+\.\w+)"                                               # file paths
)

_RESEARCH_PATTERNS = re.compile(
    r"(?i)"
    r"\b(?:find|search|compare|benchmark|analyze|evaluate"
    r"|what\s+is|how\s+does|how\s+do|explain|why\s+does|why\s+do"
    r"|summarize|summarise|overview|review|look\s+up|pros\s+and\s+cons"
    r"|difference\s+between|versus|vs\.?)\b"
    r"|https?://"
)

_CHAT_GREETINGS = re.compile(
    r"(?i)^(?:hi|hey|hello|yo|sup|thanks|thank\s+you|ok|okay"
    r"|good\s+(?:morning|afternoon|evening|night)"
    r"|how\s+are\s+you|what'?s?\s+up)\s*[!?.]*$"
)

# ---------------------------------------------------------------------------
# TaskRouter
# ---------------------------------------------------------------------------


class TaskRouter:
    """Quota-aware task classifier and dispatcher."""

    def __init__(self) -> None:
        self._quota_cache: Optional[dict] = None
        self._quota_cache_time: float = 0

    # ------------------------------------------------------------------
    # Quota reading
    # ------------------------------------------------------------------

    def get_quota_status(self) -> dict:
        """Read current quota status from quota-live.json.

        Returns the full JSON dict.  Result is cached for
        ``_QUOTA_CACHE_TTL`` seconds so hot-path calls are cheap.
        If the file is missing or unreadable, returns an empty-but-safe
        fallback and logs a warning.
        """
        now = time.time()
        if self._quota_cache and (now - self._quota_cache_time) < _QUOTA_CACHE_TTL:
            return self._quota_cache

        try:
            raw = QUOTA_LIVE_PATH.read_text(encoding="utf-8")
            data = json.loads(raw)
        except FileNotFoundError:
            logger.warning("Quota file not found at %s — assuming all available", QUOTA_LIVE_PATH)
            data = {"providers": {}, "timestamp": "unknown"}
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read quota file: %s — assuming all available", exc)
            data = {"providers": {}, "timestamp": "unknown"}

        # Staleness check based on unix timestamp in the file.
        unix_ts = data.get("unix", 0)
        if unix_ts and (now - unix_ts) > _QUOTA_STALE_THRESHOLD:
            logger.warning(
                "Quota data is stale (%.0f s old, threshold %d s)",
                now - unix_ts,
                _QUOTA_STALE_THRESHOLD,
            )

        self._quota_cache = data
        self._quota_cache_time = now
        return data

    # ------------------------------------------------------------------
    # Task classification
    # ------------------------------------------------------------------

    def classify_task(self, task: str, hint: str = "auto") -> str:
        """Classify *task* as ``'code'``, ``'research'``, or ``'chat'``.

        If *hint* is not ``'auto'``, it is returned directly (after
        validation).

        This method is synchronous and pure — safe for unit tests.
        When code_score == research_score and both > 0, the tie-break
        deterministically prefers code.  For an optional async LLM
        tie-break, use ``classify_task_async``.
        """
        hint = (hint or "auto").strip().lower()
        if hint in ("code", "research", "chat"):
            return hint

        # Heuristic classification for "auto"
        stripped = task.strip()

        # Short messages or greetings → chat
        if len(stripped) < 50 and _CHAT_GREETINGS.match(stripped):
            return "chat"

        code_score = len(_CODE_PATTERNS.findall(stripped))
        research_score = len(_RESEARCH_PATTERNS.findall(stripped))

        if code_score > research_score:
            return "code"
        if research_score > code_score:
            return "research"
        if code_score == research_score and code_score > 0:
            # Tie — deterministic fallback prefers code (more specific patterns).
            # classify_task_async may override this with an LLM tie-break.
            return "code"

        # Very short, no signal → chat
        if len(stripped) < 50:
            return "chat"

        # Ambiguous, moderate length — default to chat (cheapest)
        return "chat"

    def _is_ambiguous(self, task: str) -> bool:
        """Return True when the regex scores tie and both are > 0."""
        stripped = task.strip()
        if len(stripped) < 50 and _CHAT_GREETINGS.match(stripped):
            return False
        code_score = len(_CODE_PATTERNS.findall(stripped))
        research_score = len(_RESEARCH_PATTERNS.findall(stripped))
        return code_score == research_score and code_score > 0

    async def classify_task_async(self, task: str, hint: str = "auto") -> str:
        """Async classifier: uses classify_task, then applies an LLM tie-break
        for genuinely ambiguous inputs (code_score == research_score > 0).

        On any LLM failure or unparseable response, falls back to the
        deterministic ``classify_task`` result (prefer code).
        """
        hint = (hint or "auto").strip().lower()
        if hint in ("code", "research", "chat"):
            return hint

        sync_result = self.classify_task(task, hint=hint)

        # Only call LLM when the input is genuinely ambiguous
        if not self._is_ambiguous(task):
            return sync_result

        # Attempt cheap LLM tie-break
        try:
            from src.endpoint_resolver import resolve_endpoint
            from src.llm_core import llm_call_async

            url, model, headers = resolve_endpoint(
                "utility",
                fallback_url=None,
                fallback_model=None,
            )
            if not url or not model:
                return sync_result

            prompt = (
                "Classify the following task as exactly one word: code, research, or chat.\n"
                "Reply with ONLY that one word, nothing else.\n\n"
                f"Task: {task[:500]}"
            )
            messages = [{"role": "user", "content": prompt}]
            answer = await llm_call_async(
                url=url,
                model=model,
                messages=messages,
                headers=headers,
                temperature=0,
                max_tokens=5,
                prompt_type="utility",
            )
            word = (answer or "").strip().lower().split()[0] if answer else ""
            if word in ("code", "research", "chat"):
                logger.debug("LLM tie-break resolved '%s' → '%s'", task[:60], word)
                return word
        except Exception as exc:
            logger.debug("LLM tie-break failed (%s) — using deterministic fallback", exc)

        return sync_result

    # ------------------------------------------------------------------
    # CLI binary selection
    # ------------------------------------------------------------------

    def get_best_code_cli(self) -> Tuple[str, str]:
        """Return ``(account, provider_name)`` for the best Claude account.

        Walks ``_CLI_PRIORITY``, skipping accounts whose config dir is
        missing or whose quota provider is exhausted. Falls back to
        ``('default', 'claude')`` — the bare ``claude`` binary with its
        default profile.

        NOTE: for multi-CLI dispatch, prefer ``select_adapter()`` which
        walks the full _CLI_ADAPTERS table (claude → codex → gemini).
        This method is retained for backward compatibility.
        """
        quota = self.get_quota_status()
        providers = quota.get("providers", {})

        for account, provider_key, config_dir in _CLI_PRIORITY:
            if not Path(config_dir).expanduser().is_dir():
                continue

            # Check if the provider is available in quota data
            prov_data = providers.get(provider_key, {})
            status = prov_data.get("status", "success")

            # Skip providers that are explicitly exhausted / errored
            if status in ("exhausted", "rate_limited"):
                logger.debug("Skipping %s — provider %s status: %s", account, provider_key, status)
                continue

            return account, provider_key

        # Absolute fallback
        return "default", "claude"

    def select_adapter(self) -> Optional[Dict[str, Any]]:
        """Walk _CLI_ADAPTERS and return the first usable adapter dict.

        An adapter is usable when:
          1. Its binary is found on PATH.
          2. Its config_dir exists (if specified — claude accounts only).
          3. Its quota data does not indicate exhaustion.

        Returns None only if every adapter fails all three checks (total
        failure — the caller should emit an in-band error).
        """
        quota = self.get_quota_status()
        providers = quota.get("providers", {})

        for adapter in _CLI_ADAPTERS:
            name = adapter["name"]
            binary = shutil.which(adapter["binary"])
            if not binary:
                logger.debug("Skipping adapter %s — binary '%s' not on PATH", name, adapter["binary"])
                continue

            # config_dir check (claude accounts have one; others don't)
            config_dir = adapter.get("config_dir")
            if config_dir and not Path(config_dir).expanduser().is_dir():
                logger.debug("Skipping adapter %s — config dir missing: %s", name, config_dir)
                continue

            prov_data = providers.get(adapter["provider_key"], {})
            if adapter["is_exhausted"](prov_data):
                logger.debug("Skipping adapter %s — quota exhausted", name)
                continue

            logger.debug("Selected adapter %s", name)
            return adapter

        logger.warning("No usable CLI adapter found in _CLI_ADAPTERS")
        return None

    def build_code_command(self, account: str, task: str) -> Tuple[List[str], Dict[str, str]]:
        """Build ``(argv, env)`` to run a code task as the given account.

        This method is retained for backward compatibility.  New code should
        use ``build_adapter_command()`` with a full adapter dict.
        """
        claude_bin = shutil.which("claude") or "claude"
        argv = [claude_bin, "--print", "--output-format", "json", "-p", task]
        env = {**os.environ, "CLAUDE_MODEL": os.environ.get("CLAUDE_MODEL", "sonnet")}
        config_dir = next(
            (cfg for acct, _, cfg in _CLI_PRIORITY if acct == account), None
        )
        if config_dir:
            env["CLAUDE_CONFIG_DIR"] = str(Path(config_dir).expanduser())
        else:
            # default profile: don't let an inherited CLAUDE_CONFIG_DIR pin
            # the subprocess to whatever account launched this server
            env.pop("CLAUDE_CONFIG_DIR", None)
        return argv, env

    def build_adapter_command(
        self, adapter: Dict[str, Any], task: str
    ) -> Tuple[List[str], Dict[str, str]]:
        """Build ``(argv, env)`` for the given adapter and task."""
        binary = shutil.which(adapter["binary"]) or adapter["binary"]
        config_dir = adapter.get("config_dir")
        argv = adapter["build_argv"](binary, task, config_dir)
        env = dict(os.environ)
        if adapter.get("build_env"):
            env = adapter["build_env"](env)
        if config_dir:
            env["CLAUDE_CONFIG_DIR"] = str(Path(config_dir).expanduser())
        elif "CLAUDE_CONFIG_DIR" in env and adapter["binary"] != "claude":
            # Don't leak a claude config dir into non-claude binaries
            env.pop("CLAUDE_CONFIG_DIR", None)
        env["CLAUDE_MODEL"] = env.get("CLAUDE_MODEL", "sonnet")
        return argv, env

    # ------------------------------------------------------------------
    # Dispatch: code via subprocess (multi-CLI adapter table)
    # ------------------------------------------------------------------

    async def route_code(self, task: str) -> dict:
        """Run a code task via the best available CLI adapter.

        Walks _CLI_ADAPTERS (claude-ca → claude-cb → codex → gemini),
        selects the first non-exhausted adapter, runs it as a subprocess,
        and returns ``{response, model_used, tokens, provider, session_id?}``.

        session_id is populated for claude adapters only (--output-format json).
        """
        adapter = self.select_adapter()
        model = os.environ.get("CLAUDE_MODEL", "sonnet")

        if adapter is None:
            return await self.route_http_fallback(task)

        argv, env = self.build_adapter_command(adapter, task)
        cli_path = argv[0]
        provider_name = adapter["name"]

        logger.info(
            "Routing code task via adapter=%s binary=%s",
            provider_name, cli_path,
        )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                argv,
                capture_output=True,
                text=True,
                timeout=_CODE_TIMEOUT,
                env=env,
            )
        except subprocess.TimeoutExpired:
            logger.error("Code task timed out after %d s via %s", _CODE_TIMEOUT, cli_path)
            return {
                "response": f"Task timed out after {_CODE_TIMEOUT}s",
                "model_used": model,
                "tokens": 0,
                "provider": provider_name,
                "error": True,
            }
        except FileNotFoundError:
            logger.error("CLI binary not found: %s", cli_path)
            return {
                "response": f"CLI binary '{cli_path}' not found on PATH",
                "model_used": model,
                "tokens": 0,
                "provider": provider_name,
                "error": True,
            }

        if result.returncode != 0 and result.stderr:
            logger.warning(
                "CLI %s exited %d: %s", cli_path, result.returncode, result.stderr[:200]
            )

        # Non-zero exit with empty stdout: return stderr as error response
        if result.returncode != 0 and not result.stdout.strip():
            error_text = result.stderr.strip() or f"CLI exited with code {result.returncode}"
            return {
                "response": error_text,
                "model_used": model,
                "tokens": _estimate_tokens(error_text),
                "provider": provider_name,
                "error": True,
            }

        response_text, session_id = adapter["parse_output"](
            result.stdout, result.stderr, result.returncode
        )
        out: Dict[str, Any] = {
            "response": response_text,
            "model_used": model,
            "tokens": _estimate_tokens(response_text),
            "provider": provider_name,
        }
        if session_id:
            out["session_id"] = session_id
        return out

    # ------------------------------------------------------------------
    # HTTP fallback — last-resort free model
    # ------------------------------------------------------------------

    async def route_http_fallback(self, task: str) -> dict:
        """Last-resort HTTP call to a configured free model.

        Used by ``route_code`` when every CLI adapter is exhausted or
        unavailable. Reads ``M3_FALLBACK_URL``, ``M3_FALLBACK_MODEL``, and
        ``M3_FALLBACK_KEY`` from env, with sensible defaults pointing at
        TokenRouter + MiniMax M3 (the same free tier m3_swarm uses).

        Returns the standard ``{response, model_used, tokens, provider,
        error?}`` shape. On any failure, returns an in-band error
        (``error: True``) — never raises.
        """
        import urllib.error
        import urllib.request
        import ssl as _ssl

        url = os.environ.get("M3_FALLBACK_URL", _HTTP_FALLBACK_URL_DEFAULT)
        model = os.environ.get("M3_FALLBACK_MODEL", _HTTP_FALLBACK_MODEL_DEFAULT)
        provider = f"http_fallback:{model}"

        api_key = _resolve_fallback_api_key()
        if not api_key:
            return {
                "response": (
                    "All CLI backends exhausted and M3_FALLBACK_KEY / "
                    "TOKENROUTER_API_KEY is not set; cannot fall back to HTTP"
                ),
                "model_used": model,
                "tokens": 0,
                "provider": "none",
                "error": True,
            }

        messages = [
            {"role": "system", "content": _HTTP_FALLBACK_SYSTEM},
            {"role": "user", "content": task},
        ]
        body = json.dumps(
            {"model": model, "messages": messages, "max_tokens": 4096, "temperature": 0.3}
        ).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        # Match m3_swarm: local TLS-inspecting cert chain breaks Python's
        # default verification. tokenrouter is a trusted first-party endpoint.
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE

        try:
            with await asyncio.to_thread(urllib.request.urlopen, req, timeout=60, context=ctx) as r:
                data = json.loads(r.read())
            response_text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {}) or {}
            total_tokens = int(usage.get("total_tokens", 0) or _estimate_tokens(response_text))
            return {
                "response": response_text,
                "model_used": model,
                "tokens": total_tokens,
                "provider": provider,
            }
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            logger.warning("HTTP fallback to %s failed: %s", url, exc)
            return {
                "response": f"HTTP fallback failed: {exc}",
                "model_used": model,
                "tokens": 0,
                "provider": provider,
                "error": True,
            }
        except Exception as exc:  # never raise from dispatch
            logger.exception("HTTP fallback unexpected error")
            return {
                "response": f"HTTP fallback unexpected error: {exc}",
                "model_used": model,
                "tokens": 0,
                "provider": provider,
                "error": True,
            }

    async def route_code_resume(
        self,
        task: str,
        session_id: str,
        adapter_name: str,
    ) -> dict:
        """Resume a previous claude session via ``--resume <session_id>``.

        Only claude adapters support resume.  The adapter is looked up by
        name so the same account (config_dir) is used as the original run.

        Returns the same shape as ``route_code``.
        """
        model = os.environ.get("CLAUDE_MODEL", "sonnet")

        # Find the adapter by name
        adapter = next(
            (a for a in _CLI_ADAPTERS if a["name"] == adapter_name and a.get("supports_resume")),
            None,
        )
        if adapter is None:
            return {
                "response": f"Adapter '{adapter_name}' does not support resume",
                "model_used": model,
                "tokens": 0,
                "provider": adapter_name,
                "error": True,
            }

        binary = shutil.which(adapter["binary"]) or adapter["binary"]
        config_dir = adapter.get("config_dir")
        argv = [binary, "--resume", session_id, "--print", "--output-format", "json", "-p", task]
        env = dict(os.environ)
        if config_dir:
            env["CLAUDE_CONFIG_DIR"] = str(Path(config_dir).expanduser())
        env["CLAUDE_MODEL"] = env.get("CLAUDE_MODEL", "sonnet")

        logger.info(
            "Resuming session %s via adapter=%s", session_id[:8], adapter_name
        )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                argv,
                capture_output=True,
                text=True,
                timeout=_CODE_TIMEOUT,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return {
                "response": f"Resume timed out after {_CODE_TIMEOUT}s",
                "model_used": model,
                "tokens": 0,
                "provider": adapter_name,
                "error": True,
            }
        except FileNotFoundError:
            return {
                "response": f"CLI binary '{binary}' not found on PATH",
                "model_used": model,
                "tokens": 0,
                "provider": adapter_name,
                "error": True,
            }

        if result.returncode != 0 and not result.stdout.strip():
            error_text = result.stderr.strip() or f"CLI exited with code {result.returncode}"
            return {
                "response": error_text,
                "model_used": model,
                "tokens": _estimate_tokens(error_text),
                "provider": adapter_name,
                "error": True,
            }

        response_text, new_session_id = adapter["parse_output"](
            result.stdout, result.stderr, result.returncode
        )
        out: Dict[str, Any] = {
            "response": response_text,
            "model_used": model,
            "tokens": _estimate_tokens(response_text),
            "provider": adapter_name,
        }
        # The resumed session may return a new (or same) session_id
        if new_session_id:
            out["session_id"] = new_session_id
        return out

    # ------------------------------------------------------------------
    # Dispatch: research via Gemini
    # ------------------------------------------------------------------

    async def route_research(self, task: str) -> dict:
        """Route a research task to Gemini (or fallback).

        Returns ``{response, model_used, tokens, provider}``.
        """
        from src.endpoint_resolver import resolve_endpoint
        from src.llm_core import llm_call_async

        url, model, headers = resolve_endpoint(
            "research",
            fallback_url=None,
            fallback_model=None,
        )

        # If research endpoint not configured, try resolving a Gemini-like endpoint
        if not url:
            url, model, headers = resolve_endpoint(
                "default",
                fallback_url=None,
                fallback_model=None,
            )

        if not url or not model:
            logger.warning("No research/default endpoint configured — cannot route research task")
            return {
                "response": "No research endpoint configured. Set a Research or Default endpoint in Settings.",
                "model_used": "none",
                "tokens": 0,
                "provider": "none",
                "error": True,
            }

        messages = [
            {"role": "system", "content": "You are a thorough research assistant. Provide detailed, well-structured answers with sources when possible."},
            {"role": "user", "content": task},
        ]

        logger.info("Routing research task to %s model=%s", url, model)

        try:
            response_text = await llm_call_async(
                url=url,
                model=model,
                messages=messages,
                headers=headers,
                temperature=0.7,
                max_tokens=8192,
                prompt_type="research",
            )
        except Exception as exc:
            logger.error("Research LLM call failed: %s", exc)
            return {
                "response": f"Research call failed: {exc}",
                "model_used": model,
                "tokens": 0,
                "provider": "unknown",
                "error": True,
            }

        provider = _infer_provider_from_model(model)
        return {
            "response": response_text,
            "model_used": model,
            "tokens": _estimate_tokens(response_text),
            "provider": provider,
        }

    # ------------------------------------------------------------------
    # Dispatch: chat via cheapest model
    # ------------------------------------------------------------------

    async def route_chat(self, task: str) -> dict:
        """Route a chat task to the cheapest available model.

        Prefers MiniMax M3 if configured, otherwise falls back to the
        utility/default chat model from settings.

        MiniMax preference: resolve_endpoint does not expose a way to
        enumerate *all* configured endpoints, only to look up by setting
        key (utility, default, research, ...).  We therefore resolve
        "utility" first and check whether the resolved model name contains
        "minimax" or "m3" (case-insensitive).  If the utility endpoint is
        already set to a MiniMax M3 model, we use it.  Otherwise we fall
        through to utility-first resolution as before.  To actually route
        chat to MiniMax M3, configure the utility endpoint to a MiniMax M3
        model in Settings.

        Returns ``{response, model_used, tokens, provider}``.
        """
        from src.endpoint_resolver import resolve_endpoint
        from src.llm_core import llm_call_async

        # Try utility (cheapest) first, then default.
        # MiniMax M3 preference: if the utility model matches minimax/m3,
        # it is already the preferred cheap model and we use it directly.
        url, model, headers = resolve_endpoint(
            "utility",
            fallback_url=None,
            fallback_model=None,
        )

        if not url:
            url, model, headers = resolve_endpoint(
                "default",
                fallback_url=None,
                fallback_model=None,
            )

        if not url or not model:
            logger.warning("No chat endpoint configured — cannot route chat task")
            return {
                "response": "No chat endpoint configured. Set a Default endpoint in Settings.",
                "model_used": "none",
                "tokens": 0,
                "provider": "none",
                "error": True,
            }

        messages = [
            {"role": "system", "content": "You are a helpful assistant. Be concise and direct."},
            {"role": "user", "content": task},
        ]

        logger.info("Routing chat task to %s model=%s", url, model)

        try:
            response_text = await llm_call_async(
                url=url,
                model=model,
                messages=messages,
                headers=headers,
                temperature=0.9,
                max_tokens=4096,
                prompt_type="chat",
            )
        except Exception as exc:
            logger.error("Chat LLM call failed: %s", exc)
            return {
                "response": f"Chat call failed: {exc}",
                "model_used": model,
                "tokens": 0,
                "provider": "unknown",
                "error": True,
            }

        provider = _infer_provider_from_model(model)
        return {
            "response": response_text,
            "model_used": model,
            "tokens": _estimate_tokens(response_text),
            "provider": provider,
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def route(self, task: str, task_type: str = "auto") -> dict:
        """Classify (if auto) + dispatch a task to the best backend.

        Returns ``{response, model_used, tokens, classification, provider}``.
        """
        if not task or not task.strip():
            return {
                "response": "Empty task",
                "model_used": "none",
                "tokens": 0,
                "classification": "error",
                "provider": "none",
                "error": True,
            }

        classified = await self.classify_task_async(task, hint=task_type)
        logger.info("Task classified as '%s' (hint=%s, length=%d)", classified, task_type, len(task))

        dispatch_map = {
            "code": self.route_code,
            "research": self.route_research,
            "chat": self.route_chat,
        }

        handler = dispatch_map.get(classified, self.route_chat)
        result = await handler(task)
        result["classification"] = classified
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# HTTP fallback — last-resort free-model dispatch (default MiniMax M3)
# ---------------------------------------------------------------------------
# These constants and the key resolver live at module scope so both
# the original TaskRouter class (defined above) and any future caller
# can use the same defaults. route_http_fallback is implemented as a
# method on TaskRouter (inserted between route_code and route_code_resume
# in the class body above).

_HTTP_FALLBACK_URL_DEFAULT = "https://api.tokenrouter.com/v1/chat/completions"
_HTTP_FALLBACK_MODEL_DEFAULT = "MiniMax-M3"
_HTTP_FALLBACK_SYSTEM = (
    "You are a senior Python engineer. Output code only, no prose. "
    "Reply with the complete function or the smallest change that solves the problem."
)


def _resolve_fallback_api_key() -> Optional[str]:
    """Resolve the HTTP-fallback API key. Order: env, opencode config.

    Same lazy lookup as ``m3_swarm.api_key`` so the two systems can share
    credentials without duplicating config.
    """
    k = os.environ.get("M3_FALLBACK_KEY") or os.environ.get("TOKENROUTER_API_KEY")
    if k:
        return k
    try:
        cfg_path = Path(os.path.expanduser("~/.config/opencode/opencode.json"))
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            k = (
                cfg.get("provider", {})
                .get("tokenrouter", {})
                .get("options", {})
                .get("apiKey")
            )
            if k:
                return k
    except Exception:
        pass
    return None


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _infer_provider_from_model(model: str) -> str:
    """Best-effort provider name from model string."""
    m = (model or "").lower()
    if "gemini" in m:
        return "gemini"
    if "claude" in m or "sonnet" in m or "opus" in m or "haiku" in m:
        return "anthropic"
    if "gpt" in m or "o1" in m or "o3" in m or "o4" in m:
        return "openai"
    if "minimax" in m or "m3" in m:
        return "minimax"
    if "llama" in m or "mistral" in m or "qwen" in m or "phi" in m:
        return "local"
    return "unknown"
