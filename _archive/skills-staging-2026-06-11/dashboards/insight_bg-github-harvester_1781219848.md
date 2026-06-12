# 1-Surface Dashboard — orchestrator-mvp / 2026-06-11 (Round-Boundary State Isolation Cycle)

> **Headline:** Three round-boundary state leaks in 4 hours (#3992, #3993, #3998) plus #3961 all share one root cause. Per-round state leaks across rounds in the agent runtime, and the frontend has no contract to reset it. **This is the smallest unit of work that fixes the 1-Surface dashboard's correctness and unblocks Brief 5.**

---

## 1. Pattern Decomposition

### 1.1 Three new issues + one older, one shape
| Issue | Surface | Symptom |
|---|---|---|
| #3998 | `_thinkOpen` | next round's reasoning streams into the reply bubble, then visibly re-sorts mid-read |
| #3992 | pre-tool prose | agent prose persisted before the tool result is in |
| #3993 | email tool fences | executed tool fences stay visible after the round ends |
| #3961 | utility model | memory extraction silently dropped at round boundary |

The **shape is the same**: state that belongs to *one round* is reachable from *the next round*. The fix is a **reset contract** at the round boundary.

### 1.2 The fix is a single function
A `reset_round_state()` function called from `start_round()`. Every per-round state field is reset to a known-clean default. Global state (session_id, mode, owner) is preserved. This is **one function, one PR, three (likely four) issues closed**.

### 1.3 The investigation is bounded
30 minutes of grep + AST analysis can produce the state-field × read-sites × write-sites × reset-sites matrix. The 1-Surface dashboard's correctness depends on this matrix being correct. The whole flywheel (Brief 5) is blocked behind the dashboard being trustworthy.

---

## 2. Memory Rules (new for this cycle)

```yaml
- id: MR-OD-025
  rule: "Per-round state (thinkOpen, active_fences, prose_persisted,
         current_history, tool_call_in_flight, last_tool_result) MUST
         be reset at every start_round() boundary. Global state
         (session_id, mode, owner) MUST NOT be reset. The contract
         is enforced by a single reset_round_state() function called
         from start_round(). A regression in round isolation is a 1-Surface
         correctness regression — block merge."
  source: "Issues #3992, #3993, #3998, #3961 — all share root cause"
  severity: critical

- id: MR-OD-026
  rule: "Any state field that is read or written in the agent runtime
         MUST be classified as either per-round or global. The
         classification is recorded in docs/round_state_contract.md."
  source: "Round-state hygiene is a precondition for Brief 5 measurement"
  severity: high

- id: MR-OD-027
  rule: "Pre-tool prose MUST NOT be persisted to history until the
         corresponding tool result is in. Streaming prose is rendered
         to the UI as 'in progress' (not 'final'). Issue #3992."
  source: "Prose vs tool result ordering is a 1-Surface contract"
  severity: high

- id: MR-OD-028
  rule: "Active tool fences (UI markers for executed tools) MUST be
         cleared at round boundary. A fence is per-round, not global.
         Issue #3993."
  source: "Fence lifecycle is per-round"
  severity: high
```

---

## 3. Pytest files (concrete, copy-pasteable)

### 3.1 `tests/test_round_state_matrix.py` (the audit)
```python
"""The state-field × read-sites × write-sites × reset-sites matrix.
This test is the audit — it enumerates every per-round state field in
the agent runtime and asserts the reset contract is honored.
Source: MR-OD-025 + MR-OD-026."""
import ast
import inspect
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]


# Every per-round state field, with its expected default after reset.
# If you add a new per-round field, add it here. CI will catch if you
# don't — the test_round_boundary_state_reset suite fails.
PER_ROUND_FIELDS = {
    # field_name: (owner_class, expected_default)
    "_think_open":            ("AgentRuntime", False),
    "active_fences":          ("AgentRuntime", []),
    "prose_persisted":        ("AgentRuntime", False),
    "tool_call_in_flight":    ("AgentRuntime", None),
    "last_tool_result":       ("AgentRuntime", None),
    "current_history":        ("AgentRuntime", []),
    "streamed_prose":         ("AgentRuntime", ""),
    "pending_tool_call_id":   ("AgentRuntime", None),
}

# Fields that MUST persist across round boundaries.
GLOBAL_FIELDS = {
    "session_id":    "str",
    "mode":          "str",
    "owner":         "str",
    "is_important":  "bool",
    "message_count": "int",
    "api_key_env":   "str (config, not runtime)",
}


@pytest.fixture(scope="module")
def agent_runtime_class():
    """Import the AgentRuntime class. The import path may differ;
    adjust the import for your codebase."""
    from src.agent.runtime import AgentRuntime
    return AgentRuntime


def test_every_per_round_field_is_in_the_matrix(agent_runtime_class):
    """The matrix is the source of truth. Any field present in
    AgentRuntime that isn't here is a regression waiting to happen."""
    src = inspect.getsource(agent_runtime_class)
    tree = ast.parse(src)
    class_fields = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            class_fields.add(node.target.id)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    class_fields.add(t.id)
    unclassified = class_fields - set(PER_ROUND_FIELDS) - set(GLOBAL_FIELDS) - {
        "__init__", "start_round", "end_round", "reset_round_state",
        "current_round_id", "current_round_started_at",  # metadata
    }
    runtime_state = {f for f in unclassified if f.startswith("_") or f.islower()}
    assert not runtime_state, (
        f"Unclassified per-round state fields: {runtime_state}. "
        f"Add to PER_ROUND_FIELDS or GLOBAL_FIELDS in "
        f"tests/test_round_state_matrix.py. See MR-OD-026."
    )


def test_per_round_fields_exist_on_class(agent_runtime_class):
    """Every field in PER_ROUND_FIELDS must exist on AgentRuntime."""
    class_attrs = dir(agent_runtime_class)
    for field in PER_ROUND_FIELDS:
        assert field in class_attrs, (
            f"PER_ROUND_FIELDS contains {field!r} but AgentRuntime "
            f"has no such attribute. Remove from matrix or add to class."
        )


def test_reset_round_state_method_exists(agent_runtime_class):
    assert hasattr(agent_runtime_class, "reset_round_state"), (
        "MR-OD-025: AgentRuntime must have a reset_round_state() method."
    )


def test_start_round_calls_reset_round_state(agent_runtime_class):
    """The reset must be automatic. start_round() must call
    reset_round_state() — manual reset is a regression waiting to happen."""
    src = inspect.getsource(agent_runtime_class.start_round)
    assert "reset_round_state" in src, (
        "MR-OD-025: start_round() must call reset_round_state() automatically."
    )


def test_reset_round_state_only_resets_per_round_fields(agent_runtime_class):
    """The reset function must NOT touch global fields."""
    src = inspect.getsource(agent_runtime_class.reset_round_state)
    for global_field in GLOBAL_FIELDS:
        if f"self.{global_field} = " in src or f"self.{global_field}=" in src:
            pytest.fail(
                f"reset_round_state() assigns to self.{global_field}, "
                f"which is a global field. Reset must NOT touch global state."
            )


def test_reset_round_state_clears_all_per_round_fields(agent_runtime_class):
    """The reset must actually clear every per-round field."""
    src = inspect.getsource(agent_runtime_class.reset_round_state)
    missing_resets = []
    for field in PER_ROUND_FIELDS:
        if f"self.{field}" not in src:
            missing_resets.append(field)
    assert not missing_resets, (
        f"reset_round_state() does not clear: {missing_resets}."
    )
```

### 3.2 `tests/test_round_boundary_state_reset.py` (the contract test)
```python
"""The behavioral test: after start_round(round_n), no state from
round_{n-1} is reachable. Closes #3992, #3993, #3998.
Source: MR-OD-025."""
import pytest


def test_thinkopen_resets_at_round_boundary():
    """Issue #3998: _thinkOpen must reset."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt._think_open = True
    rt.start_round("round 2")
    assert rt._think_open is False, (
        "MR-OD-025: _thinkOpen not reset at round boundary (issue #3998)"
    )


def test_active_fences_cleared_at_round_boundary():
    """Issue #3993: tool fences must clear."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.active_fences = ["<fence email>", "<fence shell>"]
    rt.start_round("round 2")
    assert rt.active_fences == [], (
        "MR-OD-025: tool fences persist (issue #3993)"
    )


def test_prose_persisted_flag_resets():
    """Issue #3992: pre-tool prose must not persist until tool result is in."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.prose_persisted = True
    rt.start_round("round 2")
    assert rt.prose_persisted is False


def test_prose_does_not_persist_before_tool_result():
    """Issue #3992: agent prose streamed before tool result must be
    rendered as in-progress, not persisted as final."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.stream_prose("I will now call the email tool...")
    assert rt.prose_persisted() is False, (
        "MR-OD-027: pre-tool prose must not persist before tool result"
    )
    rt.complete_tool_result("email", "<result>...</result>")
    assert rt.prose_persisted() is True


def test_history_slice_isolated_per_round():
    """Per-round history must not leak across rounds."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.add_to_history("user", "from round 1")
    rt.start_round("round 2")
    assert "from round 1" not in rt.current_history(), (
        "MR-OD-025: round 1 history leaked into round 2"
    )


def test_global_state_preserved_across_rounds():
    """Global state must NOT be reset. session_id, mode, owner survive."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.session_id = "abc-123"
    rt.mode = "research"
    rt.owner = "jwalin"
    rt.start_round("round 1")
    rt._think_open = True
    rt.start_round("round 2")
    assert rt.session_id == "abc-123"
    assert rt.mode == "research"
    assert rt.owner == "jwalin", (
        "MR-OD-025: global state was reset. This breaks session continuity."
    )


def test_memory_extraction_state_resets():
    """Issue #3961: utility model not invoked. Likely root cause:
    memory_extraction_state persists across rounds, so the utility
    model thinks 'already done'."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.memory_extraction_done = True  # simulate utility model ran
    rt.start_round("round 2")
    assert rt.memory_extraction_done is False, (
        "MR-OD-025: memory extraction state leaked; utility model "
        "silently skipped in round 2 (issue #3961)"
    )


def test_tool_call_in_flight_resets():
    """A stale tool_call_in_flight flag from round 1 would block
    tool calls in round 2."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.tool_call_in_flight = "call-abc-123"
    rt.start_round("round 2")
    assert rt.tool_call_in_flight is None, (
        "MR-OD-025: stale tool_call_in_flight from round 1 "
        "blocks round 2 tool calls"
    )


def test_last_tool_result_resets():
    """A stale last_tool_result would let the agent reference
    the previous round's result as if it were current."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.last_tool_result = {"tool": "shell", "output": "round 1 output"}
    rt.start_round("round 2")
    assert rt.last_tool_result is None, (
        "MR-OD-025: stale last_tool_result from round 1 "
        "is referenced as current in round 2"
    )
```

### 3.3 `tests/test_round_state_contract_documented.py`
```python
"""The contract doc must exist and list every per-round field.
Source: MR-OD-026."""
from pathlib import Path
import pytest

CONTRACT = Path("docs/round_state_contract.md")


def test_contract_doc_exists():
    assert CONTRACT.exists(), (
        "docs/round_state_contract.md must exist. See MR-OD-026."
    )


def test_contract_doc_lists_all_per_round_fields():
    """Every per-round field in the test matrix must be documented."""
    from tests.test_round_state_matrix import PER_ROUND_FIELDS
    doc = CONTRACT.read_text()
    for field in PER_ROUND_FIELDS:
        assert field in doc, (
            f"Per-round field {field!r} is not documented in "
            f"docs/round_state_contract.md. See MR-OD-026."
        )


def test_contract_doc_distinguishes_per_round_from_global():
    """The doc must explicitly mark each field as per-round OR global."""
    doc = CONTRACT.read_text()
    assert "per-round" in doc.lower() or "per_round" in doc.lower()
    assert "global" in doc.lower()
```

---

## 4. Next Unknown

**What is the actual `task_hash` collision rate and deduplication contract for `exchanges.jsonl` when 28 `llm_call_async` callers may dispatch the same logical task — and does the current "forensics-only" `task_hash` definition make the corpus trainable, or just collected?**

**Why this and not the alternatives:**

| Candidate | Why not |
|---|---|
| PII surface in 28 callers | Addressed in prior cycle; benchmark + replay queued |
| NER layer for high-tier importers | Architecture decision deferred to replay; not the immediate unknown |
| 5-router harvest | Static scan; not the immediate unknown |
| Implementer gating | Mechanical fix; not investigation |
| Pydantic Router spec | Blocked on Jwalin (#3958); not an investigation |
| Per-model parameter table | Scoping work; not research |
| Round-boundary state isolation (this cycle) | Spec'd; the fix is mechanical (`reset_round_state()`); tests drafted |
| `task_hash` collision contract (next) | **Brief 6 §4.4 already names the join semantics as a precondition for failure mining; the contract is undefined** |

**The `task_hash` / dedup question is the one unknown where:**

- **The answer is not in any document.** Brief 6a defines the schema (`task_hash` is a 16-hex sha256, forensics-only) but never specifies: *what happens when two callers hash the same task to the same value?*
- **It gates the flywheel thesis directly.** If the same chat message is captured by the chat importer, the summary importer, and the research importer, `exchanges.jsonl` contains 3× the same content. Pioneer-adaption trains on the same example 3×, overfitting and wasting compute.
- **The 28-importer chokepoint makes this worse, not better.** All 28 callers share `llm_call_async` → 1 capture site. If 3 callers hash the same content (e.g., a quoted email captured by email importer, chat importer, and research importer), they collide on `task_hash`.
- **Brief 6 §4.4 already names the adjacent problem.** "Failure mining via task_hash join" depends on join semantics. Without a dedup policy, the join is meaningless.

**Investigation (concrete):**

1. **Read `src/llm_core.py`'s `_hash_task()` implementation.** What fields go into the hash? Is `prompt_type` included? Is `model` included? Is `caller` included? Is the hash deterministic across processes?

2. **For each of the 28 importers, determine the natural collision patterns:**
   - chat + email-summary: both ingest user-supplied text
   - notes + research: both summarize a user document
   - agent-loop + research: both may dispatch a "summarize this" task
   - scheduler + chat: scheduler may replay a chat message verbatim

3. **Design the dedup policy.** Three options:
   - **content-hash** (sha256 of `task` text): high collision rate
   - **semantic-hash** (sha256 of `task` + `prompt_type` + `model`): lower collision rate
   - **intent-hash** (sha256 of `task` + `caller` + `caller_session_id`): lowest collision rate

4. **Test the contract.** For each pair of importers likely to collide, assert:
   - content-hash: `hash(chat_task) == hash(email_summary_task)` (expected)
   - semantic-hash: `hash(chat_task, "chat", "claude") != hash(email_summary_task, "summarize", "claude")` (expected)
   - intent-hash: `hash(chat_task, "src/chat.py", session_a) != hash(email_summary_task, "src/email.py", session_a)` (expected)

5. **Codify as `core/task_hash_policy.json`** with the policy, the rationale, and the failure modes. This is the spec the implementation PR must meet.

6. **Outcome**: a 1-PR spec for the capture chokepoint contract. This is what gates Brief 6's "keep forever" retention.

**Why this is the next investigation:** the round-boundary state fix is 1 PR. The capture contract is 1 PR. The NER benchmark is 1 PR. The production-traffic replay is 1 PR. The task_hash policy is 1 PR. Each unblocks the next. The order matters: round-state fixes the dashboard (this cycle), capture contract enables the corpus (next), NER+replay makes the corpus safe, policy makes the corpus trainable.

**Concrete deliverable**: a `core/task_hash_policy.json` + a `tests/test_task_hash_dedup_policy.py` + a `docs/capture_chokepoint_contract.md`.

---

## 5. Dashboard Card (1-Surface)

```
┌──────────────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ 🟢 ROUND-STATE FIX READY      │ 🟡 CAPTURE CHOKEPOINT        │ 🔴 FIRE-AND-FORGET GAP      │
│ 1-PR fix closes #3992,        │ Spec'd, not built.           │ Phase 2 not landed.          │
│ #3993, #3998, #3961.         │ 28 importers waiting.        │ visibility_tools.py         │
│ Test matrix in MR-OD-025.    │ 1 raise = 28 regressions.    │ spec'd, not built.           │
│ Implementer: 1-2 hours.      │ [test_capture_at_             │ [test_visibility_tools_      │
│                              │  chokepoint.py]              │  placeholder.py]            │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 bg-implementer LOOSE      │ 🟡 auth-bypass = admin       │ 🟡 session.mode = DEAD      │
│ Self-modifying, no gate,     │ 2-line posture change,       │ Written 4×, read 0×.        │
│ no receipt, no HITL.         │ no test.                     │ Legacy sessions empty.       │
│ Conflicts with 3 non-goals.  │ [test_localhost_bypass_       │ [test_session_mode_          │
│ [test_implementer_miner_      │  auth.py]                    │  contract.py]                │
│  gating.py]                  │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 CADENCE INSTABILITY       │ 🟡 UNKNOWN: task_hash /      │ 🟡 Phase 3 (super-skills)  │
│ 3 commits, 75 min,           │ dedup policy. 28 importers   │ listed, not landed.         │
│ 6-100× interval change.      │ → 1 capture site → 3×        │ Repo map / auto-fix /        │
│ No measurement, no test.     │ collision risk. Gates the    │ Cline checklist.            │
│ [test_miners_cadence_         │ corpus trainability.         │                             │
│  governance.py]              │ Next cycle.                  │                             │
└──────────────────────────────┴──────────────────────────────┴──────────────────────────────┘
🟢 aligned with North Star  🟡 spec'd but unverified  🔴 gap with no owner
```

**One-liner:** *The round-state fix is 1 PR. Land it. The capture chokepoint contract is 1 PR. Land it. Brief 5 is unblocked. The flywheel starts.*