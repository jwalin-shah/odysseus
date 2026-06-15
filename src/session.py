# src/session.py
from dataclasses import dataclass, field
from typing import Optional, Any
from src.intent_router import IntentResult


@dataclass
class Session:
    history: list[dict] = field(default_factory=list)
    last_intent: Optional[IntentResult] = None
    pending_approval: Optional[dict] = None  # HarnessResult.approval_payload
    platform_ctx: Optional[str] = None  # last platform used, for follow-ups
    max_history: int = 20

    def add(self, role: str, content: str) -> None:
        """Append a message to conversation history and trim if over limit."""
        self.history.append({"role": role, "content": content})
        self.trim()

    def set_pending(self, payload: dict) -> None:
        """Store a pending approval payload (e.g. tool call awaiting consent)."""
        self.pending_approval = payload

    def clear_pending(self) -> None:
        """Clear any pending approval state."""
        self.pending_approval = None

    def to_messages(self) -> list[dict]:
        """Return a copy of history formatted for LLM context (role/content)."""
        return list(self.history)

    def trim(self) -> None:
        """Keep only the last max_history turns (a turn = user + assistant)."""
        max_messages = self.max_history * 2
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]
