# core/router.py
"""Intelligent task routing — classify, quota-check, dispatch.

Reads live quota data from the platform quota-core system, classifies
incoming tasks as code / research / chat, and dispatches each to the
cheapest suitable backend:

* **code** → Claude CLI subprocess (ca, cb, cp, or claude binary)
* **research** → Gemini endpoint via llm_call_async
* **chat** → cheapest available model (MiniMax M3 preferred)
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
from typing import Dict, List, Optional, Tuple

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

    def build_code_command(self, account: str, task: str) -> Tuple[List[str], Dict[str, str]]:
        """Build ``(argv, env)`` to run a code task as the given account."""
        claude_bin = shutil.which("claude") or "claude"
        argv = [claude_bin, "--print", "-p", task]
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

    # ------------------------------------------------------------------
    # Dispatch: code via subprocess
    # ------------------------------------------------------------------

    async def route_code(self, task: str) -> dict:
        """Run a code task via Claude CLI subprocess.

        Returns ``{response, model_used, tokens, provider}``.
        """
        account, provider = self.get_best_code_cli()
        model = os.environ.get("CLAUDE_MODEL", "sonnet")
        argv, env = self.build_code_command(account, task)
        cli_path = argv[0]

        logger.info("Routing code task via %s (account=%s, provider=%s, model=%s)",
                    cli_path, account, provider, model)

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
                "provider": provider,
                "error": True,
            }
        except FileNotFoundError:
            logger.error("CLI binary not found: %s", cli_path)
            return {
                "response": f"CLI binary '{cli_path}' not found on PATH",
                "model_used": model,
                "tokens": 0,
                "provider": provider,
                "error": True,
            }

        if result.returncode != 0 and result.stderr:
            logger.warning("CLI %s exited %d: %s", cli_path, result.returncode, result.stderr[:200])

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Non-zero exit with empty stdout: return stderr as error response
        # rather than silently producing an empty success.
        if result.returncode != 0 and not stdout:
            error_text = stderr or f"CLI exited with code {result.returncode}"
            return {
                "response": error_text,
                "model_used": model,
                "tokens": _estimate_tokens(error_text),
                "provider": provider,
                "error": True,
            }

        response_text = stdout or stderr
        return {
            "response": response_text,
            "model_used": model,
            "tokens": _estimate_tokens(response_text),
            "provider": provider,
        }

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
