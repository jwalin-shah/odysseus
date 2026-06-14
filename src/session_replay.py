"""
session_replay.py

Reads logs/tool_use.jsonl and reconstructs what happened in a session:
sequence of tool calls, what succeeded/failed, total tokens used, duration,
and generates a human-readable session summary.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_LOG_PATH = "logs/tool_use.jsonl"

_SUCCESS_STATUSES = {"success", "ok", "succeeded", "completed"}
_FAILURE_STATUSES = {"error", "failed", "failure", "timeout"}


class SessionReplay:
    """Replay and summarize a session from the tool-use JSONL log."""

    def __init__(self, log_path: Optional[str] = None) -> None:
        self.log_path = log_path or DEFAULT_LOG_PATH
        self.entries: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []
        self.successful: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, Any]] = []
        self.total_tokens: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.duration_seconds: float = 0.0
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.session_id: Optional[str] = None

    # ------------------------------------------------------------------ loading

    def load(self, log_path: Optional[str] = None) -> None:
        """Load raw JSONL entries from the log file."""
        if log_path:
            self.log_path = log_path
        path = Path(self.log_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {self.log_path}")

        self.entries = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.entries.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines rather than abort the whole replay.
                    continue

    # ------------------------------------------------------------------- parsing

    def _coerce_dt(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except (OverflowError, OSError, ValueError):
                return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _extract_tokens(self, entry: Dict[str, Any]) -> None:
        # Accept several common shapes: {tokens: N}, {total_tokens: N},
        # {usage: {total_tokens/prompt_tokens/completion_tokens}}.
        if "tokens" in entry and isinstance(entry["tokens"], (int, float)):
            self.total_tokens += int(entry["tokens"])
        if "total_tokens" in entry and isinstance(entry["total_tokens"], (int, float)):
            self.total_tokens += int(entry["total_tokens"])
        usage = entry.get("usage") or {}
        if isinstance(usage, dict):
            for key, attr in (
                ("total_tokens", "total_tokens"),
                ("prompt_tokens", "prompt_tokens"),
                ("completion_tokens", "completion_tokens"),
            ):
                v = usage.get(key)
                if isinstance(v, (int, float)):
                    setattr(self, attr, getattr(self, attr) + int(v))

    def parse(self) -> None:
        """Parse loaded entries into tool calls, token totals, and timing."""
        self.tool_calls = []
        self.successful = []
        self.failed = []
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.duration_seconds = 0.0
        self.start_time = None
        self.end_time = None

        for entry in self.entries:
            if self.session_id is None:
                self.session_id = entry.get("session_id") or entry.get("sessionId")

            tool_name = (
                entry.get("tool")
                or entry.get("tool_name")
                or entry.get("name")
                or entry.get("function")
            )
            if tool_name:
                status = str(entry.get("status", "unknown")).lower()
                call: Dict[str, Any] = {
                    "tool": tool_name,
                    "args": entry.get("args")
                    or entry.get("arguments")
                    or entry.get("input")
                    or {},
                    "status": entry.get("status", "unknown"),
                    "timestamp": entry.get("timestamp") or entry.get("time"),
                    "duration_ms": entry.get("duration_ms") or entry.get("elapsed_ms"),
                    "result": entry.get("result") or entry.get("output"),
                    "error": entry.get("error") or entry.get("error_message"),
                }
                self.tool_calls.append(call)
                if status in _SUCCESS_STATUSES:
                    self.successful.append(call)
                elif status in _FAILURE_STATUSES:
                    self.failed.append(call)

            self._extract_tokens(entry)

            dt = self._coerce_dt(entry.get("timestamp") or entry.get("time"))
            if dt is not None:
                if self.start_time is None or dt < self.start_time:
                    self.start_time = dt
                if self.end_time is None or dt > self.end_time:
                    self.end_time = dt

        if self.start_time and self.end_time:
            delta = (self.end_time - self.start_time).total_seconds()
            if delta >= 0:
                self.duration_seconds = delta

    # ------------------------------------------------------------------ summary

    def summarize(self) -> str:
        """Return a human-readable session summary."""
        lines: List[str] = []
        lines.append("=== Session Summary ===")
        if self.session_id:
            lines.append(f"Session ID : {self.session_id}")
        if self.start_time and self.end_time:
            lines.append(f"Start      : {self.start_time.isoformat()}")
            lines.append(f"End        : {self.end_time.isoformat()}")
        if self.duration_seconds:
            mins, secs = divmod(self.duration_seconds, 60)
            lines.append(f"Duration   : {int(mins)}m {secs:.2f}s "
                         f"({self.duration_seconds:.2f}s)")
        lines.append("")
        lines.append("Tool calls : "
                     f"{len(self.tool_calls)} total, "
                     f"{len(self.successful)} succeeded, "
                     f"{len(self.failed)} failed")
        lines.append("Tokens     : "
                     f"{self.total_tokens} total "
                     f"(prompt={self.prompt_tokens}, "
                     f"completion={self.completion_tokens})")
        lines.append("")
        lines.append("--- Tool call sequence ---")
        if not self.tool_calls:
            lines.append("(no tool calls recorded)")
        for i, call in enumerate(self.tool_calls, 1):
            if call in self.successful:
                marker = "OK "
            elif call in self.failed:
                marker = "ERR"
            else:
                marker = "---"
            ts = call.get("timestamp") or "-"
            lines.append(f"{i:>3}. [{marker}] {call['tool']:<24} @ {ts}")
            err = call.get("error")
            if err:
                lines.append(f"      error: {err}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict of the parsed session."""
        return {
            "session_id": self.session_id,
            "log_path": self.log_path,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "totals": {
                "tool_calls": len(self.tool_calls),
                "succeeded": len(self.successful),
                "failed": len(self.failed),
                "tokens": self.total_tokens,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
            },
            "tool_calls": self.tool_calls,
        }


def replay(log_path: Optional[str] = None) -> SessionReplay:
    """Convenience helper: load, parse, and return a SessionReplay."""
    sr = SessionReplay(log_path=log_path)
    sr.load()
    sr.parse()
    return sr


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Replay a tool-use log.")
    parser.add_argument(
        "log_path",
        nargs="?",
        default=DEFAULT_LOG_PATH,
        help="Path to tool_use.jsonl (default: logs/tool_use.jsonl)",
    )
    args = parser.parse_args()

    session = replay(args.log_path)
    print(session.summarize())