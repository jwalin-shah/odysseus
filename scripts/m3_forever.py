#!/usr/bin/env python3
"""
M3 forever loop — continuously queues improvement goals, lets M3 do all the coding.
Runs until June 17 (TokenRouter free tier expiry) or killed.

Usage: nohup python3 scripts/m3_forever.py >> /tmp/m3_forever.log 2>&1 &
       tail -f /tmp/m3_forever.log
"""
import json
import os
import re
import ssl
import subprocess
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

KEY = os.environ.get("TOKENROUTER_API_KEY", "sk-umkgY44a1AeYkZa2ZCZFpPwnGY4ZeedbFByHfm8eZcfRKXZJ")
ROOT = Path(__file__).parent.parent
LOCK = threading.Lock()

# Deadline: June 17 2026
DEADLINE = datetime(2026, 6, 17, 23, 59, 0)

# ─── Goal queue ───────────────────────────────────────────────────────────────
# Each goal: (name, prompt, context_files)
# Prompts are kept SHORT — large prompts cause M3 to return 0 chars.
# Max ~3000 chars prompt. Reference files by name, include only critical snippets.

GOALS = [
    # ── iMessage / inbox ──
    (
        "imessage-contact-search",
        """Fix contact extraction in src/intent_router.py for the pattern "what did Sarah say".
Currently _CONTACT_RE only matches after prepositions (to/from/with).
Add a fallback: if no prepositional match, look for a capitalized name anywhere in the text
that isn't a platform word (iMessage/WhatsApp/Gmail/etc).

Add this fallback to _extract_contact():
```python
# Fallback: bare capitalized name not after a preposition
_BARE_NAME_RE = re.compile(r'\\b([A-Z][a-z]{1,15})\\b')
_SKIP_WORDS = {...existing platform words...}

for m in _BARE_NAME_RE.finditer(text):
    w = m.group(1)
    if w.lower() not in _SKIP_WORDS and w not in ('The','A','An','I','My','What','Who','When','Where','How','Did','Does'):
        return w
```

Output the updated _extract_contact function only (not the whole file):
```python:src/intent_router_patch_contact.py```""",
        [],
    ),
    (
        "workflow-test",
        """Write tests/test_workflow_engine.py — unit tests for src/workflow_engine.py.

Test the following (mock inbox_tool calls with unittest.mock):
1. inbox_summary_flow returns dict with platform keys and unread counts
2. reply_flow raises ApprovalRequired before sending
3. calendar_add_flow raises ApprovalRequired before creating event

Use pytest + unittest.mock.patch. Keep it under 80 lines.
Output: ```python:tests/test_workflow_engine.py```""",
        [],
    ),
    (
        "harness-test",
        """Write tests/test_intent_router.py — parametrized pytest tests for src/intent_router.classify().

Test cases:
- "reply to mom's text" → platform=imessage, action=reply, contact=mom
- "send email to John about the deal" → platform=gmail, contact=John
- "add meeting Tuesday 3pm" → platform=calendar, action=create, time_info has day=Tuesday
- "fix bug in auth.py" → platform=code
- "what did Sarah say on WhatsApp" → platform=whatsapp, contact=Sarah (once patch applied)
- "show my LinkedIn DMs" → platform=linkedin, action=read

Output: ```python:tests/test_intent_router.py```""",
        [],
    ),
    (
        "pi-call-test",
        """Write tests/test_pi_call.py — unit tests for src/pi_call.py.

Test:
1. _provider_model("tokenrouter/MiniMax-M3") → ("tokenrouter", "MiniMax-M3")
2. _provider_model("anthropic/claude-sonnet-4-6") → ("anthropic", "claude-sonnet-4-6")
3. pi_call raises RuntimeError when pi not available and provider != tokenrouter
4. BUDGET_MODELS and FRONTIER_MODELS are non-empty lists

Mock subprocess.run to simulate pi not available.
Output: ```python:tests/test_pi_call.py```""",
        [],
    ),
    (
        "inbox-tool-test",
        """Write tests/test_inbox_tool.py — unit tests for src/inbox_tool.py.

Test the retry logic in _request():
1. On URLError, retries 3 times then raises InboxError
2. On HTTPError, raises InboxError immediately (no retry)
3. get_imessage_thread accepts both int and str chat_id

Mock urllib.request.urlopen.
Output: ```python:tests/test_inbox_tool.py```""",
        [],
    ),
    (
        "odysseus-boot",
        """Write src/odysseus_boot.py — startup checker that verifies Odysseus can reach all services.

Checks (fast, parallel, each with 3s timeout):
1. inbox server at http://localhost:9849/health → OK/FAIL
2. TokenRouter API (1 tiny M3 call) → OK/FAIL
3. pi CLI available (pi --version) → OK/FAIL
4. iMessage DB readable (~/Library/Messages/chat.db exists) → OK/FAIL
5. WhatsApp accessibility permission (try Accessibility API list) → OK/SKIP

Returns dict: {"inbox": True, "tokenrouter": True, "pi": True, "imessage": True, "whatsapp": "skip"}
Prints colored status table to stdout.

Output: ```python:src/odysseus_boot.py```""",
        [],
    ),
    (
        "harness-approval-gate",
        """Add approval gate to src/harness.py.

Currently route() returns needs_approval=True for send/create/delete but doesn't actually gate.
Add:

```python
def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    \"\"\"If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result.\"\"\"
    ...
```

The approval payload should contain enough info to re-execute:
{"platform": "imessage", "action": "send", "to": "mom", "body": "...", "fn": "send_imessage"}

When confirmed, look up the function in inbox_tool by name and call it.

Read the current src/harness.py (shown below) and output an updated version:
Current harness.py top-level structure:
  - HarnessResult dataclass
  - route(user_text, context) -> HarnessResult
  - _handle_read, _handle_send, _handle_calendar, _handle_code
Add confirm_and_execute at the bottom.
Output: ```python:src/harness_patch.py``` (just the new function, not full rewrite)""",
        ["src/harness.py"],
    ),
    (
        "whatsapp-wire",
        """Write src/whatsapp_bridge.py — thin wrapper around inbox server WhatsApp routes.

The inbox server (http://localhost:9849) has these WhatsApp routes:
  GET /whatsapp/contacts -> list of contacts
  GET /whatsapp/messages/{contact_id} -> messages in thread
  POST /messages/send {source: "whatsapp", to: str, body: str}

WhatsApp requires WhatsApp.app open + Accessibility permission on macOS.
Add a check: if contacts returns 403 or empty, raise WhatsAppNotReady with instructions.

```python
# src/whatsapp_bridge.py
from src.inbox_tool import inbox_get, inbox_post, InboxError

class WhatsAppNotReady(Exception): ...

def check_ready() -> bool: ...
def get_contacts() -> list: ...
def get_thread(contact_id: str, limit: int = 20) -> list: ...
def send(to: str, body: str) -> dict: ...  # requires explicit call, not gated here
```

Output: ```python:src/whatsapp_bridge.py```""",
        [],
    ),
    (
        "session-manager",
        """Write src/session.py — simple in-memory session manager for the Odysseus chat loop.

Tracks:
- conversation history (list of {role, content} dicts)
- last intent result
- pending approval (if any)
- active platform context

```python
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

    def add(self, role: str, content: str) -> None: ...
    def set_pending(self, payload: dict) -> None: ...
    def clear_pending(self) -> None: ...
    def to_messages(self) -> list[dict]: ...  # for LLM context
    def trim(self) -> None: ...  # keep last max_history turns
```

Output: ```python:src/session.py```""",
        [],
    ),
    (
        "linkedin-wire",
        """Write src/linkedin_bridge.py — wrapper for LinkedIn data via inbox server.

LinkedIn data comes from CDP scanner (INBOX_ENABLE_LINKEDIN_SCRAPER=1 env var needed).
Routes at localhost:9849:
  GET /linkedin/dms -> recent DMs
  GET /linkedin/connections -> recent connections
  GET /linkedin/profile/{person} -> profile info

If LinkedIn scanner not enabled, raise LinkedInScannerOff with instructions to set env var.

```python
# src/linkedin_bridge.py
from src.inbox_tool import inbox_get, InboxError

class LinkedInScannerOff(Exception): ...

def check_enabled() -> bool: ...
def get_dms(limit: int = 10) -> list: ...
def get_connections(limit: int = 20) -> list: ...
def send_dm(connection_id: str, message: str) -> dict: ...
```

Output: ```python:src/linkedin_bridge.py```""",
        [],
    ),
    (
        "fusion-judge-prompt",
        """Improve the judge prompt in src/fusion.py.

Current judge prompt asks for JSON with: consensus/contradictions/partial_coverage/unique_insights/blind_spots/quality_ranking

Problems:
1. "quality_ranking" causes models to self-rank which creates bias
2. "blind_spots" is vague — models can't know what they don't know
3. Missing: "actionable_next_steps" — the most useful output for an agent

New judge JSON schema:
{
  "consensus": "what all models agreed on",
  "best_answer": "the most complete/accurate answer (verbatim from one model or synthesized)",
  "contradictions": ["list of specific disagreements"],
  "gaps": ["things no model covered that would help"],
  "confidence": "high|medium|low based on consensus level",
  "actionable": ["1-3 concrete next steps or answers"]
}

Find the judge prompt string in src/fusion.py and output the replacement.
Output just the new judge prompt as a Python string:
```python:src/fusion_judge_patch.py```
(a file with just: JUDGE_PROMPT = \"\"\"...\"\"\")""",
        [],
    ),
    (
        "routing-readme",
        """Write docs/HARNESS_ROUTING.md — one-page doc explaining how Odysseus routes requests.

Explain (with examples):
1. User text → intent_router.classify() → IntentResult
2. IntentResult → harness.route() → HarnessResult
3. If needs_approval: show to user, get confirm, call confirm_and_execute()
4. If platform=code: routed to pi_call() → M3 or Claude
5. inbox_tool is the data layer, workflow_engine handles multi-step flows

Include a flow diagram using ASCII art.
Keep under 80 lines.

Output: ```markdown:docs/HARNESS_ROUTING.md```""",
        [],
    ),
]


def log(name: str, msg: str) -> None:
    with LOCK:
        print(f"[{datetime.now().strftime('%H:%M:%S')}][{name}] {msg}", flush=True)


def m3_call(prompt: str, max_tokens: int = 64000, retries: int = 3) -> str:
    for attempt in range(retries):
        msgs = [{"role": "user", "content": prompt}]
        req = urllib.request.Request(
            "https://api.tokenrouter.com/v1/chat/completions",
            data=json.dumps({"model": "MiniMax-M3", "messages": msgs, "max_tokens": max_tokens}).encode(),
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=600, context=CTX) as r:
                body = json.load(r)
            raw = body["choices"][0]["message"]["content"]
            finish = body["choices"][0].get("finish_reason", "?")
            usage = body.get("usage", {})
            # Strip think block
            if "</think>" in raw:
                out = raw.split("</think>", 1)[1].strip()
            else:
                out = raw.strip()
            log("m3", f"finish={finish} tokens={usage.get('total_tokens','?')} output={len(out)} chars")
            if out:
                return out
            log("m3", f"empty output (finish={finish}) attempt {attempt+1}")
        except Exception as e:
            log("m3", f"error attempt {attempt+1}: {e}")
            time.sleep(5)
    return ""


def read_snippet(rel_path: str, max_lines: int = 30) -> str:
    p = ROOT / rel_path
    if not p.exists():
        return ""
    lines = p.read_text().splitlines()[:max_lines]
    return "\n".join(lines)


def parse_edits(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for m in re.finditer(r"```(?:\w+)?:(\S+)\n(.*?)```", text, re.DOTALL):
        result[m.group(1)] = m.group(2).strip()
    return result


def run_goal(name: str, prompt: str, context_files: list[str]) -> bool:
    log(name, "start")

    # Append brief context snippets if requested
    full_prompt = prompt
    if context_files:
        snippets = []
        for f in context_files:
            s = read_snippet(f, max_lines=25)
            if s:
                snippets.append(f"=== {f} (first 25 lines) ===\n{s}")
        if snippets:
            full_prompt += "\n\nCONTEXT:\n" + "\n\n".join(snippets)

    response = m3_call(full_prompt)
    if not response:
        log(name, "got empty response after retries — skip")
        return False

    log(name, f"got {len(response)} chars")
    edits = parse_edits(response)
    if not edits:
        log(name, f"no file blocks found. sample: {response[:150]}")
        return False

    applied = []
    for rel_path, content in edits.items():
        p = ROOT / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content + "\n")
        applied.append(rel_path)
        log(name, f"wrote {rel_path} ({len(content)} chars)")

    if applied:
        with LOCK:
            subprocess.run(["git", "add"] + applied, cwd=ROOT, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", f"m3-forever {name}"],
                cwd=ROOT, capture_output=True, text=True
            )
            if result.returncode == 0:
                log(name, f"committed {applied}")
            else:
                log(name, f"commit failed: {result.stderr.strip()}")

    return True


def main() -> None:
    log("forever", f"Starting M3 forever loop — {len(GOALS)} goals queued")
    log("forever", f"Deadline: {DEADLINE} (TokenRouter free tier)")

    # Run goals in parallel batches of 8 — tested no rate limiting up to 4, 8 is safe
    batch_size = 8
    goal_queue = list(GOALS)
    batch_num = 0

    while goal_queue and datetime.now() < DEADLINE:
        batch = goal_queue[:batch_size]
        goal_queue = goal_queue[batch_size:]
        batch_num += 1
        log("forever", f"Batch {batch_num}: {[g[0] for g in batch]}")

        threads = []
        for name, prompt, ctx_files in batch:
            t = threading.Thread(target=run_goal, args=(name, prompt, ctx_files), daemon=True)
            threads.append(t)

        for t in threads:
            t.start()
            time.sleep(0.3)
        for t in threads:
            t.join(timeout=300)

        log("forever", f"Batch {batch_num} done. {len(goal_queue)} goals remaining.")

        if goal_queue:
            time.sleep(2)  # Brief pause between batches

    if datetime.now() >= DEADLINE:
        log("forever", "Deadline reached — stopping")
    else:
        log("forever", "All goals processed")


if __name__ == "__main__":
    main()
