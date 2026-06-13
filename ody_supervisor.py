#!/usr/bin/env python3
"""
ody_supervisor.py — top-level task supervisor for odysseus.

Receives incoming tasks, assembles a context-augmented system prompt
(via microagent_router), and dispatches the task to the appropriate
handler.
"""
from __future__ import annotations

import logging
import os
import subprocess
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


def get_project_context(hint: Optional[str] = None) -> str:  # hint=None
    """Return a compact project context string (max 400 chars).

    Scans ``~/projects`` and ``~/m3lab`` for git repositories, runs
    ``git log --oneline -3`` in each to capture the last 3 commits,
    and returns the best match.

    If ``hint`` is provided, repos are scored by the number of
    case-insensitive words from ``hint`` that appear in the repo
    name; the highest-scoring repo's name plus its last 3 commits is
    returned. If no hint is given, or no repo scores positively, the
    function falls back to a comma-separated list of all discovered
    repo names.

    All subprocess and filesystem errors are swallowed so a broken
    repo never breaks callers.
    """
    home = os.path.expanduser("~")
    search_dirs = [os.path.join(home, "projects"), os.path.join(home, "m3lab")]

    repos = []
    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        for entry in entries:
            repo_path = os.path.join(directory, entry)
            if not os.path.isdir(repo_path):
                continue
            if not os.path.isdir(os.path.join(repo_path, ".git")):
                continue
            try:
                result = subprocess.run(
                    ["git", "log", "--oneline", "-3"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                commits = result.stdout.strip() if result.returncode == 0 else ""
            except Exception:
                commits = ""
            repos.append((entry, commits))

    if not repos:
        return ""

    if not hint:
        names = ", ".join(name for name, _ in repos)
        return f"Projects: {names}"[:400]

    hint_words = [w.lower() for w in hint.split() if w]
    scored = []
    for name, commits in repos:
        name_lower = name.lower()
        score = sum(1 for w in hint_words if w and w in name_lower)
        scored.append((score, name, commits))
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored or scored[0][0] == 0:
        names = ", ".join(name for name, _ in repos)
        return f"Projects: {names}"[:400]

    best_name, best_commits = scored[0][1], scored[0][2]
    if best_commits:
        context = f"Project: {best_name}\nRecent commits:\n{best_commits}"
    else:
        context = f"Project: {best_name}"
    return context[:400]


def route_task(task: str, project: Optional[str] = None) -> dict:
    """Classify ``task`` and return a routing payload.

    Classification uses simple keyword matching (case-insensitive,
    first-match-wins) to assign the task to one of four worker
    kinds:

    * ``'impl'``      — implement a pure function
    * ``'research'``  — research a topic
    * ``'repo_edit'`` — edit files in a repo
    * ``'question'``  — answer directly

    The returned dict has keys ``worker`` (the classification),
    ``system`` (built via :func:`build_system_prompt` so the
    downstream worker still receives the microagent-augmented
    context), and ``task`` (the original task string).

    The ``project`` parameter is accepted for API symmetry with
    future routing logic but is not currently used.
    """
    task_lower = task.lower()

    impl_keywords = ("implement", "write a function", "def ")
    research_keywords = ("research", "find", "how does", "what is")
    repo_edit_keywords = ("fix", "edit", "update", "wire", "add to")

    if any(kw in task_lower for kw in impl_keywords):
        worker = "impl"
    elif any(kw in task_lower for kw in research_keywords):
        worker = "research"
    elif any(kw in task_lower for kw in repo_edit_keywords):
        worker = "repo_edit"
    else:
        worker = "question"

    system_prompt = build_system_prompt(task)
    return {"worker": worker, "system": system_prompt, "task": task}


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