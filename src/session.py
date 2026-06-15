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
        self.history.append({"role": role, "content": content})
        self.trim()

    def set_pending(self, payload: dict) -> None:
        self.pending_approval = payload

    def clear_pending(self) -> None:
        self.pending_approval = None

    def to_messages(self) -> list[dict]:  # for LLM context
        return list(self.history)

    def trim(self) -> None:  # keep last max_history turns
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
