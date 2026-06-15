#!/usr/bin/env python3
"""
M3 parallel grind — runs multiple M3 improvement loops simultaneously.
Squeezes max value from free TokenRouter tier before expiry.

Usage: nohup python3 scripts/m3_grind.py >> /tmp/m3_grind.log 2>&1 &
       tail -f /tmp/m3_grind.log
"""
import json
import os
import re
import ssl
import subprocess
import sys
import threading
import urllib.request
import time
from datetime import datetime
from pathlib import Path

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()

TOKENROUTER_KEY = os.environ.get(
    "TOKENROUTER_API_KEY",
    "sk-umkgY44a1AeYkZa2ZCZFpPwnGY4ZeedbFByHfm8eZcfRKXZJ",
)
REPO_ROOT = Path(__file__).parent.parent
LOCK = threading.Lock()

# ── Grind goals ────────────────────────────────────────────────────────────────
# Each entry: (name, goal, target_files, max_rounds)
GRIND_JOBS = [
    (
        "workflow-engine",
        """Write src/workflow_engine.py — a deterministic workflow engine for Odysseus.
Workflows are predefined sequences of inbox actions. No LLM in the engine itself.

Required workflows:
  reply_flow(platform, contact, thread_id, reply_text) -> calls inbox_tool.send_*
  inbox_summary_flow(platforms=['imessage','gmail'], limit=10) -> returns dict of unread counts + snippets
  calendar_add_flow(title, start_iso, end_iso, description='') -> calls inbox_tool POST /calendar/events

Each step in a flow:
  1. Call inbox_tool function
  2. If needs_approval=True, raise ApprovalRequired(action, payload) exception
  3. Return structured result

Also write: approval gate middleware that catches ApprovalRequired and asks the agent loop for confirmation.

Use:
  from src.inbox_tool import inbox_get, inbox_post, send_imessage, send_whatsapp, send_email, get_calendar_upcoming

Output as: ```python:src/workflow_engine.py```""",
        ["src/inbox_tool.py"],
        4,
    ),
    (
        "harness-router",
        """Write src/harness.py — the deterministic routing layer between the chat UI and tools.

This replaces keyword-based route_task(). It uses src/intent_router.classify() to get intent,
then dispatches to the right workflow or tool without any LLM involvement.

```python
# src/harness.py
from src.intent_router import classify, IntentResult
from src.workflow_engine import reply_flow, inbox_summary_flow, calendar_add_flow
from src.inbox_tool import get_imessage_contacts, get_imessage_thread, get_gmail_unread, get_calendar_upcoming
from src.pi_call import pi_call

class HarnessResult:
    content: str
    action_taken: str
    needs_approval: bool
    approval_payload: dict | None

def route(user_text: str, context: dict = None) -> HarnessResult:
    \"\"\"Single entry point. Classifies intent, runs deterministic handler, returns result.\"\"\"
    ...

# Handlers — pure Python, no LLM:
def _handle_read(intent: IntentResult) -> HarnessResult: ...
def _handle_send(intent: IntentResult, text: str) -> HarnessResult: ...
def _handle_calendar(intent: IntentResult, text: str) -> HarnessResult: ...
def _handle_code(intent: IntentResult, text: str) -> HarnessResult: ...
```

For code intents, call pi_call() with the appropriate model.
For read intents, call the right inbox_tool helper.
For send/reply intents, call the right workflow and gate on approval.

Output as: ```python:src/harness.py```""",
        ["src/intent_router.py", "src/workflow_engine.py", "src/inbox_tool.py", "src/pi_call.py"],
        4,
    ),
    (
        "imessage-bridge",
        """Improve src/inbox_tool.py — add comprehensive iMessage support.

Current inbox server routes for iMessage (all confirmed live at localhost:9849):
  GET /imessage/contacts -> list of {handle_id, chat_identifier, display_name, last_message, unread_count}
  GET /imessage/messages/{chat_id}?limit=N -> list of messages
  GET /imessage/search?q=term -> search messages
  POST /messages/send {source: "imessage", to: str, body: str}
  GET /imessage/unread -> unread counts

Add to inbox_tool.py:
  search_imessage(query: str) -> list
  get_imessage_unread() -> list
  get_recent_threads(limit=5) -> list[dict]  # sorted by most recent activity
  format_thread_summary(thread: list[dict]) -> str  # human-readable summary

Also fix: contact extraction in get_imessage_thread — handle both int and str chat_id.
Also add: retry logic (3 attempts, 2s backoff) in _request() for connection failures.

Output the complete updated file as: ```python:src/inbox_tool.py```""",
        ["src/inbox_tool.py"],
        3,
    ),
    (
        "intent-improve",
        """Improve src/intent_router.py — fix contact extraction and add time parsing.

Current bugs:
1. "send email to John about proposal" → contact="John about" (grabs too much)
   Fix: stop at preposition words (about, for, re, regarding, re:)
2. "reply to mom's text" → contact="mom iMessage" (includes platform name)
   Fix: strip platform keywords from contact name

New feature — add time_info extraction:
  "add meeting Tuesday 3pm" → time_info={"day": "Tuesday", "time": "15:00", "relative": True}
  "meeting at 2026-06-17 14:00" → time_info={"datetime_iso": "2026-06-17T14:00:00"}
  "tomorrow morning" → time_info={"day": "tomorrow", "time": "09:00", "relative": True}

Update IntentResult dataclass to include time_info: dict | None

Also improve confidence scoring: if both platform AND action have high-confidence matches,
confidence = 0.95, not just the average.

Output the complete updated file as: ```python:src/intent_router.py```""",
        ["src/intent_router.py"],
        3,
    ),
    (
        "agent-loop-wire",
        """Update src/tool_implementations.py and src/tool_schemas.py to wire harness.py into the agent loop.

Add these tools:
1. "route" tool — calls harness.route(user_text) and returns HarnessResult
   Schema: {user_text: string, context: object (optional)}

2. "inbox_read" tool — reads from inbox using inbox_tool directly
   Schema: {platform: "imessage"|"gmail"|"whatsapp"|"calendar"|"linkedin",
             action: "contacts"|"thread"|"unread"|"upcoming",
             contact: string (optional), limit: int (optional)}

3. "inbox_send" tool — sends via inbox_tool with mandatory approval gate
   Schema: {platform: "imessage"|"whatsapp"|"gmail", to: string, body: string, subject: string (gmail only)}
   Implementation: ALWAYS sets needs_approval=True, returns {pending: true, payload: {...}}
   for the agent loop to confirm before calling /messages/send

Read existing tool_implementations.py and tool_schemas.py and add to them.
Output both complete files as:
```python:src/tool_implementations.py```
```python:src/tool_schemas.py```""",
        ["src/tool_implementations.py", "src/tool_schemas.py", "src/inbox_tool.py"],
        3,
    ),
    (
        "fusion-improve",
        """Improve src/fusion.py — add streaming, better error handling, and a fast single-model path.

Current issues:
1. No timeout per panel member — one slow model blocks the whole synthesis
2. No streaming — waits for full response before returning
3. If synthesizer (Claude) is unavailable, returns raw judge output (ugly)

Improvements:
1. Add per-model timeout: each panel member gets 45s, stragglers are dropped, synthesis continues with available responses
2. Add fast_fuse(prompt, model="tokenrouter/MiniMax-M3") -> str: single model call, no panel, for latency-sensitive paths
3. Improve fallback synthesizer: if Claude unavailable, use M3 as synthesizer (already in budget panel, call separately)
4. Add fuse_streaming() generator that yields partial synthesis as it comes back (server-sent events compatible)

Read the existing src/fusion.py and output the improved complete file as:
```python:src/fusion.py```""",
        ["src/fusion.py"],
        3,
    ),
]


def log(name: str, msg: str) -> None:
    with LOCK:
        print(f"[{datetime.now().strftime('%H:%M:%S')}][{name}] {msg}", flush=True)


def m3_call(prompt: str, max_tokens: int = 8000) -> str:
    msgs = [{"role": "user", "content": prompt}]
    req = urllib.request.Request(
        "https://api.tokenrouter.com/v1/chat/completions",
        data=json.dumps({"model": "MiniMax-M3", "messages": msgs, "max_tokens": max_tokens}).encode(),
        headers={"Authorization": f"Bearer {TOKENROUTER_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300, context=SSL_CTX) as r:
        body = json.load(r)
    out = body["choices"][0]["message"]["content"]
    if "</think>" in out:
        out = out.split("</think>", 1)[1].strip()
    return out


def read_files(rel_paths: list[str]) -> str:
    parts = []
    for p in rel_paths:
        path = REPO_ROOT / p
        if path.exists():
            content = path.read_text()
            parts.append(f"=== {p} ===\n{content}")
        else:
            parts.append(f"=== {p} === (does not exist yet)")
    return "\n\n".join(parts)


def parse_edits(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    # Match ```lang:path\n...\n```
    for m in re.finditer(r"```\w*:(\S+)\n(.*?)```", text, re.DOTALL):
        result[m.group(1)] = m.group(2).strip()
    return result


def apply_edits(edits: dict[str, str], name: str) -> list[str]:
    applied = []
    for rel_path, content in edits.items():
        path = REPO_ROOT / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n")
        applied.append(rel_path)
        log(name, f"wrote {rel_path} ({len(content)} chars)")
    return applied


def run_job(name: str, goal: str, context_files: list[str], max_rounds: int) -> None:
    log(name, f"START — {goal[:60]}...")

    for rnd in range(1, max_rounds + 1):
        log(name, f"round {rnd}/{max_rounds}")
        context = read_files(context_files)
        prompt = f"{goal}\n\nCURRENT FILE CONTEXT:\n{context}"
        try:
            response = m3_call(prompt)
        except Exception as e:
            log(name, f"M3 error: {e}")
            time.sleep(10)
            continue

        log(name, f"got {len(response)} chars from M3")
        edits = parse_edits(response)
        if not edits:
            log(name, "no edits produced — done")
            log(name, f"M3 said: {response[:200]}")
            break

        applied = apply_edits(edits, name)

        # Commit each file written
        if applied:
            with LOCK:
                subprocess.run(["git", "add"] + applied, cwd=REPO_ROOT, capture_output=True)
                subprocess.run(
                    ["git", "commit", "-m", f"m3-grind {name} round {rnd}"],
                    cwd=REPO_ROOT, capture_output=True
                )
            log(name, f"committed: {applied}")
        break  # One round per job (parallel jobs cover all goals simultaneously)

    log(name, "DONE")


def main() -> None:
    log("grind", f"Starting {len(GRIND_JOBS)} parallel M3 jobs")
    log("grind", "TokenRouter free tier — grinding before June 17 expiry")

    threads = []
    for name, goal, files, rounds in GRIND_JOBS:
        t = threading.Thread(target=run_job, args=(name, goal, files, rounds), daemon=True)
        threads.append(t)
        t.start()
        time.sleep(0.5)  # Stagger starts slightly

    for t in threads:
        t.join()

    log("grind", "All jobs complete")


if __name__ == "__main__":
    main()
