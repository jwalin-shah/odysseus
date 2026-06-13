#!/usr/bin/env python3
"""
ody_supervisor.py — top-level task supervisor for odysseus.

Receives incoming tasks, assembles a context-augmented system prompt
(via microagent_router), and dispatches the task to the appropriate
handler.
"""
from __future__ import annotations

import logging
from typing import Optional

import microagent_router

logger = logging.getLogger(__name__)

BASE_SYSTEM_PROMPT = """You are odysseus, an AI engineering assistant with access to \
tools, code execution, and a persistent workspace. Think step by step, be precise, and \
prefer the smallest change that solves the problem."""


def build_system_prompt(task: str, base: Optional[str] = None) -> str:
    """Assemble the supervisor's system prompt for ``task``.

    Pulls keyword-matched microagent context via
    :func:`microagent_router.get_context` and prepends it to the base
    system prompt so downstream models receive relevant domain knowledge
    before processing the task.
    """
    base_prompt = base if base is not None else BASE_SYSTEM_PROMPT
    extra_context = microagent_router.get_context(task)
    if extra_context:
        logger.debug(
            "Injected microagent context (%d chars) for task: %s",
            len(extra_context),
            task[:80],
        )
        return f"{extra_context}\n\n{base_prompt}"
    return base_prompt


def handle_task(task: str, base_prompt: Optional[str] = None) -> dict:
    """Handle an incoming task.

    Returns a payload containing the context-augmented system prompt
    and the original task, ready to be dispatched to a model or agent.
    """
    system_prompt = build_system_prompt(task, base=base_prompt)
    return {"system": system_prompt, "task": task}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        result = handle_task(task)
        print(result["system"])
        print("---")
        print(result["task"])
    else:
        print("Usage: ody_supervisor.py <task>")