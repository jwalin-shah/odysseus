"""Deterministic workflow engine for Odysseus.

Workflows are predefined, side-effect-aware sequences of inbox actions.
The engine itself contains **no LLM logic** — it is a thin orchestrator
over :mod:`src.inbox_tool`. Decisions about *which* workflow to run and
*what arguments* to pass are made by the agent loop elsewhere; this
module only knows how to execute the steps.

A :class:`Step` declares:
  1. The inbox_tool call to make
  2. Whether that call needs human sign-off (``:code:`needs_approval` ``)
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
        result = self.run()
        log.info("workflow step ok:   %s", self.name)
        return result


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


def reply_flow(
    platform: str,
    contact: str,
    thread_id: str,
    reply_text: str,
) -> dict:
    """Reply to an existing conversation on the given platform.

    The ``platform`` parameter selects the inbox_tool ``send_*`` function:

    ===========  =================================================
    platform     call
    ===========  =================================================
    ``imessage``  ``send_imessage(contact, reply_text)``
    ``whatsapp``  ``send_whatsapp(contact, reply_text)``
    ``email`` /   ``send_email(to=contact, subject=thread_id,
    ``gmail``       body=reply_text)``
    ===========  =================================================

    Sending has external side-effects, so the step is approval-gated.
    """
    platform = platform.lower().strip()

    payload = {
        "platform": platform,
        "contact": contact,
        "thread_id": thread_id,
        "reply_text": reply_text,
    }

    if platform == "imessage":
        step = Step(
            name="send_imessage",
            needs_approval=True,
            run=lambda: send_imessage(contact, reply_text),
        )
    elif platform == "whatsapp":
        step = Step(
            name="send_whatsapp",
            needs_approval=True,
            run=lambda: send_whatsapp(contact, reply_text),
        )
    elif platform in ("email", "gmail"):
        # ``thread_id`` carries the subject (or a message id the caller resolved).
        subject = thread_id or "(no subject)"
        step = Step(
            name="send_email",
            needs_approval=True,
            run=lambda: send_email(to=contact, subject=subject, body=reply_text),
        )
    else:
        raise ValueError(f"reply_flow: unknown platform {platform!r}")

    if step.needs_approval:
        raise ApprovalRequired(action=step.name, payload=payload, step=step)

    return {"platform": platform, "contact": contact, "result": step.execute()}


def inbox_summary_flow(
    platforms: Iterable[str] = ("imessage", "gmail"),
    limit: int = 10,
) -> dict:
    """Return a per-platform summary of unread messages.

    Result shape::

        {
            "imessage": {"unread": int, "snippets": [str, ...]},
            "gmail":    {"unread": int, "snippets": [str, ...]},
            ...
        }

    Read-only — no approval required.
    """
    summary: dict[str, dict] = {}

    for raw in platforms:
        platform = raw.lower().strip()

        if platform == "gmail":
            threads = get_gmail_unread(limit=limit)
            summary["gmail"] = _summarise_threads(threads, limit)

        elif platform == "imessage":
            # No dedicated unread helper in inbox_tool; ask the server
            # directly and fall back to contacts if the endpoint is missing.
            try:
                data = inbox_get("/imessage/unread", {"limit": limit})
                messages = data if isinstance(data, list) else data.get("messages", [])
                summary["imessage"] = _summarise_threads(messages, limit)
            except Exception as exc:  # noqa: BLE001 — fall back gracefully
                log.warning("imessage unread endpoint failed (%s); using contacts", exc)
                contacts = get_imessage_contacts(limit=limit)
                summary["imessage"] = {
                    "unread": len(contacts),
                    "snippets": [
                        str(c.get("name") or c.get("handle") or c) for c in contacts
                    ][:limit],
                }

        elif platform == "linkedin":
            data = inbox_get("/linkedin/dms", {"limit": limit})
            items = data if isinstance(data, list) else data.get("dms", [])
            summary["linkedin"] = _summarise_threads(items, limit)

        else:
            raise ValueError(f"inbox_summary_flow: unsupported platform {platform!r}")

    return summary


def calendar_add_flow(
    title: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
) -> dict:
    """Create a calendar event via ``POST /calendar/events``.

    Calendar writes modify shared state, so this step is approval-gated.
    """
    payload = {
        "title": title,
        "start": start_iso,
        "end": end_iso,
        "description": description,
    }

    step = Step(
        name="calendar_add",
        needs_approval=True,
        run=lambda: inbox_post("/calendar/events", payload),
    )

    if step.needs_approval:
        raise ApprovalRequired(action=step.name, payload=payload, step=step)

    return {"event": step.execute(), "title": title}


def calendar_list_flow(days: int = 7) -> dict:
    """Convenience read-only workflow: list upcoming calendar events.

    Uses :func:`get_calendar_upcoming` so the agent loop can quickly
    surface "what's on my calendar?" without re-implementing the call.
    """
    events = get_calendar_upcoming(days=days)
    return {"days": days, "count": len(events), "events": events}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _summarise_threads(items: list, limit: int) -> dict:
    """Reduce a list of thread/message dicts to ``{unread, snippets}``."""
    snippets: list[str] = []
    for it in items[:limit]:
        if not isinstance(it, dict):
            snippets.append(str(it))
            continue
        for key in ("snippet", "preview", "subject", "body", "text"):
            value = it.get(key)
            if value:
                snippets.append(str(value)[:140])
                break
        else:
            snippets.append("")
    return {"unread": len(items), "snippets": snippets}


# ---------------------------------------------------------------------------
# Approval-gate middleware
# ---------------------------------------------------------------------------


ConfirmFn = Callable[[str, dict], bool]
"""Signature: ``(action, payload) -> True`` to approve, ``False`` to deny."""


def with_approval_gate(
    flow_fn: Callable[..., Any],
    confirm: ConfirmFn,
) -> Callable[..., Any]:
    """Wrap a workflow so any :class:`ApprovalRequired` is presented for
    confirmation before the underlying step runs.

    Usage::

        gated_reply = with_approval_gate(reply_flow, my_confirm_callback)
        result = gated_reply(platform="imessage", contact="+1...",
                             thread_id="abc", reply_text="hi")

    The ``confirm`` callable receives ``(action, payload)`` and returns
    ``True`` to proceed or ``False`` to deny. On approval, the step's
    closure is re-invoked and its result returned. On denial,
    :class:`ApprovalDenied` is raised.
    """
    def wrapped(*args, **kwargs):
        try:
            return flow_fn(*args, **kwargs)
        except ApprovalRequired as exc:
            log.info("approval gate: %s payload=%s", exc.action, exc.payload)
            approved = bool(confirm(exc.action, exc.payload))
            if not approved:
                raise ApprovalDenied(f"user denied action: {exc.action}") from exc

            if exc.step is not None:
                result = exc.step.execute()
                return {
                    "approved": True,
                    "action": exc.action,
                    "result": result,
                }

            # Fallback: re-invoke the flow. The caller is responsible for
            # ensuring the flow is idempotent w.r.t. repeated invocation.
            return flow_fn(*args, **kwargs)

    wrapped.__wrapped__ = flow_fn
    wrapped.__name__ = f"gated_{flow_fn.__name__}"
    wrapped.__doc__ = flow_fn.__doc__
    return wrapped


def console_confirm(action: str, payload: dict) -> bool:
    """Reference :data:`ConfirmFn` that prompts on stdin.

    Useful for tests and local development. In production the agent
    loop supplies its own implementation that consults the user via
    chat (or auto-approves for trusted sub-flows).
    """
    print(f"\n[approval required] {action}")
    for key, value in payload.items():
        print(f"  {key}: {value}")
    ans = input("approve? [y/N] ").strip().lower()
    return ans in ("y", "yes")


__all__ = [
    "ApprovalRequired",
    "ApprovalDenied",
    "Step",
    "reply_flow",
    "inbox_summary_flow",
    "calendar_add_flow",
    "calendar_list_flow",
    "with_approval_gate",
    "console_confirm",
]
