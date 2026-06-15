"""Deterministic workflow engine for Odysseus.

Workflows are predefined, side-effect-aware sequences of inbox actions.
The engine itself contains **no LLM logic** — it is a thin orchestrator
over :mod:`src.inbox_tool`. Decisions about *which* workflow to run and
*what arguments* to pass are made by the agent loop elsewhere; this
module only knows how to execute the steps.

A :class:`Step` declares:
  1. The inbox_tool call to make
  2. Whether that call needs human sign-off (``needs_approval``)
  3. How to package the result

If a step requires approval it raises :class:`ApprovalRequired`. The
:func:`with_approval_gate` middleware catches that, asks the agent
loop to confirm, and either re-executes the step or aborts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

from src.inbox_tool import (
    inbox_get,
    inbox_post,
    send_imessage,
    send_whatsapp,
    send_email,
    get_calendar_upcoming,
    get_gmail_unread,
    get_imessage_contacts,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Approval machinery
# ---------------------------------------------------------------------------


class ApprovalRequired(Exception):
    """Raised by a workflow step when its action needs human approval.

    Attributes
    ----------
    action:
        Short, machine-readable name of the action (e.g. ``"send_imessage"``).
    payload:
        The arguments that *would* be sent to the inbox tool. The approval
        handler may inspect, log, or modify this dict before approving.
    step:
        The :class:`Step` that raised the exception. The gate re-executes
        this step directly on approval so closures stay intact.
    """

    def __init__(
        self,
        action: str,
        payload: dict,
        step: Optional["Step"] = None,
    ) -> None:
        super().__init__(f"Approval required for {action}")
        self.action = action
        self.payload = payload
        self.step = step


class ApprovalDenied(Exception):
    """Raised by the gate when the operator refuses the action."""


# ---------------------------------------------------------------------------
# Step abstraction
# ---------------------------------------------------------------------------


@dataclass
class Step:
    """A single inbox action.

    Purely deterministic: declares *what* to call and *whether* it
    needs sign-off. The actual LLM-driven planning happens elsewhere.
    """

    name: str
    needs_approval: bool
    run: Callable[[], Any]

    def execute(self) -> Any:
        log.info("workflow step start: %s (approval=%s)", self.name, self.needs_approval)
        if self.needs_approval:
            log.info("workflow step requires approval: %s", self.name)
            raise ApprovalRequired(action=self.name, payload={}, step=self)
        result = self.run()
        log.info("workflow step ok:   %s", self.name)
        return result


# ---------------------------------------------------------------------------
# Workflows
