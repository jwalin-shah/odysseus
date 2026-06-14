"""
tool_logger.py — Structured logging wrapper for agent tool calls.

Provides a ToolLogger class that wraps every tool call invoked through
agent_tools.py (or any other caller) with structured JSONL logging.
Each log entry contains:

  - tool_name     : name of the tool invoked
  - args          : the arguments passed to the tool (JSON-serializable view)
  - result_size   : size of the returned result (chars/bytes/items)
  - duration_ms   : wall-clock duration of the call in milliseconds
  - success       : True if the call completed without exception
  - timestamp     : ISO-8601 UTC timestamp of the call
  - error         : (optional) error message for failed calls

Log records are appended to ``logs/tool_use.jsonl`` (one JSON object per
line). The module also exposes ``tool_stats()`` to summarize per-tool
usage statistics — call counts, success/failure counts, total and
average duration, and success rate.

Typical use:

    from src.tool_logger import ToolLogger, get_tool_logger, tool_stats

    log = get_tool_logger()
    result = log.wrap("do_bash", do_bash, command="ls -la")
    print(tool_stats())

The logger is thread-safe: multiple concurrent tool calls each write a
complete JSON line and update the in-memory stats under a single lock.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)

# Default location of the JSONL log file (relative to the working directory).
DEFAULT_LOG_PATH = "logs/tool_use.jsonl"


class ToolLogger:
    """
    Structured logger for agent tool calls.

    Each call to :meth:`wrap` (or :meth:`log_call`) produces a single
    JSONL record appended to the configured log file. The class is safe
    to share across threads.
    """

    def __init__(
        self,
        log_path: Union[str, os.PathLike] = DEFAULT_LOG_PATH,
        enabled: bool = True,
    ) -> None:
        """
        Initialize the logger.

        Args:
            log_path: Path to the JSONL log file. Parent directories are
                created on demand.
            enabled:  If False, all logging becomes a no-op (stats are
                still tracked in memory). Useful for tests and dry runs.
        """
        self.log_path = os.fspath(log_path)
        self.enabled = enabled
        self._lock = threading.Lock()
        self._stats: Dict[str, Dict[str, Any]] = {}
        self._ensure_log_dir()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_log_dir(self) -> None:
        """Create the parent directory for the log file, if needed."""
        if not self.enabled:
            return
        try:
            parent = Path(self.log_path).expanduser().parent
            if str(parent) and not parent.exists():
                parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning(
                "ToolLogger: could not create log directory %s (%s); "
                "disabling file logging.",
                parent,
                exc,
            )
            self.enabled = False

    def _write(self, entry: Dict[str, Any]) -> None:
        """Serialize and append a single JSONL entry."""
        if not self.enabled:
            return
        try:
            line = json.dumps(entry, default=str, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            logger.warning("ToolLogger: failed to serialize entry (%s).", exc)
            return
        with self._lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError as exc:
                logger.warning("ToolLogger: failed to write log entry (%s).", exc)
                return
        self._update_stats(entry)

    def _update_stats(self, entry: Dict[str, Any]) -> None:
        """Update the in-memory per-tool statistics for one call."""
        tool_name = str(entry.get("tool_name") or "<unknown>")
        duration = float(entry.get("duration_ms") or 0.0)
        success = bool(entry.get("success"))
        with self._lock:
            bucket = self._stats.setdefault(
                tool_name,
                {
                    "calls": 0,
                    "successes": 0,
                    "failures": 0,
                    "total_duration_ms": 0.0,
                },
            )
            bucket["calls"] += 1
            if success:
                bucket["successes"] += 1
            else:
                bucket["failures"] += 1
            bucket["total_duration_ms"] += duration

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def log_call(
        self,
        tool_name: str,
        args: Any,
        result: Any,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        Record a single tool call.

        Args:
            tool_name:   Name of the tool invoked.
            args:        Arguments passed to the tool.
            result:      Return value of the tool (only its size is logged).
            duration_ms: Wall-clock duration of the call, in milliseconds.
            success:     True if the call succeeded.
            error:       Optional error message; recorded when supplied.
        """
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": str(tool_name),
            "args": self._safe_args(args),
            "result_size": self._measure(result),
            "duration_ms": round(float(duration_ms), 3),
            "success": bool(success),
        }
        if error is not None:
            entry["error"] = str(error)
        self._write(entry)

    def wrap(
        self,
        tool_name: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Invoke ``func`` with the given arguments, logging the call.

        The call is timed, exceptions are recorded, and the original
        exception is re-raised after the log entry is written.

        Args:
            tool_name: Name of the tool (used for logging and stats).
            func:      Callable to invoke.
            *args, **kwargs: Forwarded to ``func``.

        Returns:
            Whatever ``func(*args, **kwargs)`` returns.
        """
        start = time.perf_counter()
        success = False
        error_msg: Optional[str] = None
        result: Any = None
        try:
            result = func(*args, **kwargs)
            success = True
            return result
        except BaseException as exc:  # noqa: BLE001 — log then re-raise
            error_msg = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            self.log_call(
                tool_name=tool_name,
                args={"args": list(args), "kwargs": kwargs},
                result=result,
                duration_ms=duration_ms,
                success=success,
                error=error_msg,
            )

    def stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Return a snapshot of per-tool usage statistics.

        Returns:
            Mapping of ``tool_name`` -> dict with:
              - ``calls``            : int
              - ``successes``        : int
              - ``failures``         : int
              - ``total_duration_ms``: float
              - ``avg_duration_ms``  : float
              - ``success_rate``     : float in [0.0, 1.0]
        """
        with self._lock:
            snapshot: Dict[str, Dict[str, Any]] = {}
            for tool_name, s in self._stats.items():
                calls = int(s["calls"])
                total = float(s["total_duration_ms"])
                avg = (total / calls) if calls else 0.0
                rate = (float(s["successes"]) / calls) if calls else 0.0
                snapshot[tool_name] = {
                    "calls": calls,
                    "successes": int(s["successes"]),
                    "failures": int(s["failures"]),
                    "total_duration_ms": round(total, 3),
                    "avg_duration_ms": round(avg, 3),
                    "success_rate": round(rate, 4),
                }
            return snapshot

    def reset_stats(self) -> None:
        """Clear in-memory statistics. The on-disk log file is untouched."""
        with self._lock:
            self._stats.clear()

    # ------------------------------------------------------------------
    # Static utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _measure(result: Any) -> int:
        """Best-effort size measurement of a tool result."""
        if result is None:
            return 0
        if isinstance(result, (str, bytes, bytearray)):
            return len(result)
        try:
            return len(result)
        except TypeError:
            try:
                return len(json.dumps(result, default=str))
            except (TypeError, ValueError):
                return len(str(result))

    @staticmethod
    def _safe_args(args: Any) -> Any:
        """Return a JSON-friendly view of arbitrary tool arguments."""
        if args is None or isinstance(args, (str, int, float, bool)):
            return args
        if isinstance(args, dict):
            return {str(k): ToolLogger._safe_args(v) for k, v in args.items()}
        if isinstance(args, (list, tuple, set, frozenset)):
            return [ToolLogger._safe_args(v) for v in args]
        # Last resort: ensure it round-trips through json.
        try:
            json.dumps(args, default=str)
            return args
        except (TypeError, ValueError):
            return repr(args)


# ---------------------------------------------------------------------------
# Module-level singleton + convenience helpers
# ---------------------------------------------------------------------------
_default_logger: Optional[ToolLogger] = None
_default_lock = threading.Lock()


def get_tool_logger(log_path: Union[str, os.PathLike] = DEFAULT_LOG_PATH) -> ToolLogger:
    """
    Return the process-wide default :class:`ToolLogger` instance.

    The singleton is created lazily on first use. Subsequent calls
    return the same instance, so stats accumulate across the process.
    """
    global _default_logger
    with _default_lock:
        if _default_logger is None:
            _default_logger = ToolLogger(log_path=log_path)
        return _default_logger


def configure(log_path: Union[str, os.PathLike]) -> ToolLogger:
    """
    Replace the default singleton with a fresh logger pointed at ``log_path``.

    Returns the new logger. Useful in tests or when bootstrapping a
    custom log destination.
    """
    global _default_logger
    with _default_lock:
        _default_logger = ToolLogger(log_path=log_path)
        return _default_logger


def tool_stats() -> Dict[str, Dict[str, Any]]:
    """
    Summarize tool usage seen so far by the default logger.

    Returns:
        A dict keyed by tool name with the same shape as
        :meth:`ToolLogger.stats`.
    """
    return get_tool_logger().stats()


__all__ = [
    "DEFAULT_LOG_PATH",
    "ToolLogger",
    "configure",
    "get_tool_logger",
    "tool_stats",
]