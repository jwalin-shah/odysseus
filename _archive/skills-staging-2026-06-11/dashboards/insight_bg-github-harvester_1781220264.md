# 1-Surface Dashboard — orchestrator-mvp / 2026-06-11 (Capture Chokepoint Contract Cycle)

> **Headline:** The `task_hash` contract is the single architectural decision that determines whether the corpus is trainable. Get it wrong and the flywheel is 3–6× inflated. Get it right and the flywheel runs. **This is a 1-PR spec, not a research question.** The remaining unknown is the *operational* metric: p99 latency of the chokepoint against 20K real exchanges.

---

## 1. Pattern Decomposition

### 1.1 The 28-importer fan-in makes collisions the central concern
North Star §6.1 says capture goes in `llm_call_async`. The 28 importers fan into that one chokepoint. The schema (`task_hash` is a 16-hex sha256) **never specifies** what goes into the hash. **6+ importers will produce collisions on the same content** unless the hash includes discriminating inputs (prompt_type, model, caller, session_id).

### 1.2 The three options have different cost curves
| Option | Inputs | Collision rate | Tradeoff |
|---|---|---|---|
| content-hash | task | High (6×) | Simple; corpus inflated; training wastes compute |
| semantic-hash | + prompt_type + model | Medium (3–4×) | Preserves routing signal; better training distribution |
| intent-hash | + caller + session_id | Low (1–2×) | Best dedup; treats user/system as the unit |

### 1.3 The contract is also the dedup contract
The export bridge (`scripts/exchange-export`) must dedup per the policy. Three modes: `first_wins`, `last_wins`, `merge`. The choice affects:
- Storage cost (first_wins: smallest; merge: largest)
- Training data (first_wins: first capture wins; merge: all calls preserved)
- Failure mining (merge: `task_hash` join finds all `error: true` and `success: true` for the same task)

### 1.4 The decision is irreversible at scale
Once `record_exchange` ships, every inference is hashed. Changing the hash function later means re-hashing the entire corpus. Changing the policy later means re-deduplicating every file. **The contract must be right before capture lands.**

---

## 2. Memory Rules (new for this cycle)

```yaml
- id: MR-OD-033
  rule: "task_hash MUST be computed from a documented set of inputs
         (per core/task_hash_policy.json). A change to the hash inputs
         is a 1-PR spec change and a corpus-wide re-hash. MR-OD-019:
         do not skip the policy file."
  source: "Brief 6 §4.4 + corpus trainability requirement"
  severity: critical

- id: MR-OD-034
  rule: "prompt_type MUST be one of: chat, scheduler, research, notes,
         email, summaries, agent, code, research-helper, custom. A new
         value is a 1-PR spec change and a classifier update."
  source: "Provenance taxonomy for the corpus"
  severity: high

- id: MR-OD-035
  rule: "The capture chokepoint (llm_call_async) MUST populate all
         dedup-relevant fields on every record_exchange call. Missing
         fields are a regression — the chokepoint is the single source
         of truth for the schema."
  source: "North Star §6.1: 28 importers fan into one capture site"
  severity: critical

- id: MR-OD-036
  rule: "exchanges/ dedup at export time MUST follow the policy in
         core/task_hash_policy.json. The dedup_mode (first_wins,
         last_wins, merge) is recorded in the policy file. The export
         script MUST read the policy, not hardcode dedup behavior."
  source: "Corpus trainability + Brief 6 §4.4 failure-mining assumption"
  severity: critical
```

---

## 3. Pytest files (concrete, copy-pasteable)

### 3.1 `tests/test_task_hash_policy_exists.py` (the precondition)
```python
"""The contract file is a precondition for capture shipping.
Source: MR-OD-033. If this file doesn't exist, capture must not
be enabled in config."""
import json
from pathlib import Path
import pytest

POLICY = Path("core/task_hash_policy.json")


def test_policy_file_exists():
    assert POLICY.exists(), (
        "core/task_hash_policy.json must exist before capture lands. "
        "MR-OD-019 + MR-OD-033. Without a documented policy, the "
        "28-importers chokepoint produces collisions and the corpus "
        "is 3-6× inflated."
    )


def test_policy_defines_hash_inputs():
    """The hash inputs define what counts as 'the same task'."""
    policy = json.loads(POLICY.read_text())
    assert "hash_inputs" in policy
    inputs = set(policy["hash_inputs"])
    assert "task" in inputs
    assert "prompt_type" in inputs, (
        "task_hash must include prompt_type. Otherwise the same content "
        "to chat vs email-summary collides. See MR-OD-034."
    )
    assert "model" in inputs, (
        "task_hash must include model. Otherwise 'the same task to two "
        "models' collides and we lose the cheaper-routing signal."
    )


def test_policy_specifies_dedup_mode():
    policy = json.loads(POLICY.read_text())
    assert "dedup_mode" in policy
    assert policy["dedup_mode"] in ("first_wins", "last_wins", "merge"), (
        f"dedup_mode {policy['dedup_mode']!r} is not a valid mode. "
        f"Choose first_wins, last_wins, or merge."
    )


def test_policy_documents_rationale():
    policy = json.loads(POLICY.read_text())
    assert "rationale" in policy
    assert len(policy["rationale"]) > 100, (
        f"rationale is only {len(policy['rationale'])} chars. "
        f"The hash choice affects every exchange; explain it in >100 chars."
    )


def test_policy_defines_prompt_type_taxonomy():
    policy = json.loads(POLICY.read_text())
    assert "prompt_types" in policy
    valid = {"chat", "scheduler", "research", "notes", "email",
             "summaries", "agent", "code", "research-helper", "custom"}
    declared = set(policy["prompt_types"])
    unknown = declared - valid
    assert not unknown, (
        f"Unknown prompt_types in policy: {unknown}. "
        f"MR-OD-034."
    )
```

### 3.2 `tests/test_task_hash_dedup_policy.py` (the behavioral contract)
```python
"""The dedup policy is the contract. The export script MUST read
this policy and behave accordingly. These tests pin the behavior."""
import json
from pathlib import Path
import pytest

POLICY = Path("core/task_hash_policy.json")


def compute_hash(task, prompt_type, model, caller, session_id):
    """Reference impl. Must match src/llm_core._hash_task()."""
    policy = json.loads(POLICY.read_text())
    inputs = policy["hash_inputs"]
    parts = []
    for k in inputs:
        parts.append({"task": task, "prompt_type": prompt_type,
                      "model": model, "caller": caller,
                      "session_id": session_id}[k])
    import hashlib
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def test_content_hash_collision_intentional():
    """content-hash policy says same content collides regardless of importer."""
    h1 = compute_hash("Hello world", "chat", "claude",
                      "src/chat.py", "abc")
    h2 = compute_hash("Hello world", "email", "claude",
                      "src/email.py", "abc")
    assert h1 == h2, "content-hash policy: same task MUST collide"


def test_semantic_hash_differentiates_prompt_type():
    h1 = compute_hash("Hello world", "chat", "claude",
                      "src/chat.py", "abc")
    h2 = compute_hash("Hello world", "email", "claude",
                      "src/email.py", "abc")
    assert h1 != h2, "semantic-hash: chat and email-summary MUST differ"


def test_model_included_differentiates_models():
    h1 = compute_hash("Hello world", "chat", "claude",
                      "src/chat.py", "abc")
    h2 = compute_hash("Hello world", "chat", "gpt-4",
                      "src/chat.py", "abc")
    assert h1 != h2


def test_hash_is_deterministic():
    args = dict(task="Hello world", prompt_type="chat", model="claude",
                caller="src/chat.py", session_id="abc")
    assert compute_hash(**args) == compute_hash(**args), (
        "task_hash is not deterministic — corpus joins will fail"
    )


def test_undeclared_input_does_not_affect_hash():
    """If the policy doesn't declare an input, it MUST not affect the hash.
    Otherwise adding a new field to the call site breaks every existing
    exchange's hash."""
    base = dict(task="Hello world", prompt_type="chat", model="claude",
                caller="src/chat.py", session_id="abc")
    h1 = compute_hash(**base)
    h2 = compute_hash(**{**base, "extra_undeclared": "value"})
    assert h1 == h2, "Undeclared input affected the hash"


@pytest.mark.parametrize("mode", ["first_wins", "last_wins", "merge"])
def test_dedup_mode_is_implemented(mode):
    from scripts import exchange_export
    assert hasattr(exchange_export, f"dedup_{mode}"), (
        f"exchange_export.py does not implement dedup_{mode}. "
        f"MR-OD-036: the policy field must have a corresponding function."
    )
```

### 3.3 `tests/test_capture_chokepoint_populates_schema.py`
```python
"""The capture chokepoint must populate the schema fields. Source: MR-OD-035."""
import inspect
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]


def test_record_exchange_call_signature_includes_required_fields():
    from core.exchange_log import record_exchange
    sig = inspect.signature(record_exchange)
    required = {"task_hash", "task", "response", "classification",
                "model_used", "provider", "tokens", "latency_ms",
                "source", "caller", "prompt_type", "caller_session_id"}
    actual = set(sig.parameters.keys())
    missing = required - actual
    assert not missing, (
        f"record_exchange() missing required parameters: {missing}. "
        f"MR-OD-035: the chokepoint is the single source of truth."
    )


def test_chokepoint_passes_caller_and_session_id():
    from pathlib import Path
    src = (REPO / "src" / "llm_core.py").read_text()
    assert "record_exchange" in src
    assert "caller=" in src or '"caller"' in src, (
        "llm_call_async must pass caller= to record_exchange. "
        "MR-OD-035: the chokepoint is the single source of truth for the schema."
    )
```

### 3.4 `tests/test_exchange_export_dedup.py` (the export-time contract)
```python
"""The export script must dedup per the policy, not hardcoded.
Source: MR-OD-036."""
import json
from pathlib import Path
import pytest

POLICY = Path("core/task_hash_policy.json")
EXCHANGES = Path("data/orchestration/exchanges/")


def test_export_dedupes_per_policy(tmp_path):
    if not POLICY.exists():
        pytest.skip("policy file missing")
    if not EXCHANGES.exists():
        pytest.skip("no exchanges/ yet")

    policy = json.loads(POLICY.read_text())
    from scripts.exchange_export import export_dedup
    out = export_dedup(
        since="7d",
        exchanges_dir=str(EXCHANGES),
        out_dir=str(tmp_path),
        policy=policy,
    )
    rows = out["rows"]
    mode = policy["dedup_mode"]
    if mode == "first_wins":
        seen = set()
        for r in rows:
            assert r["task_hash"] not in seen
            seen.add(r["task_hash"])
    elif mode == "last_wins":
        latest = {}
        for r in rows:
            h = r["task_hash"]
            if h not in latest or r["ts"] > latest[h]["ts"]:
                latest[h] = r
        assert len(rows) == len(latest)
    # merge: no constraint; all rows preserved
```

---

## 4. Next Unknown

**What is the actual end-to-end capture latency (`record_exchange` plus all importers, plus the dedup step) at production traffic distribution — and does the 28-importer write amplification stay within the latency budget that the chat UI can tolerate?**

**Why this and not the alternatives:**

| Candidate | Why not the next one |
|---|---|
| `task_hash` / dedup policy | This cycle's pass produces the spec; the policy file is the deliverable; the implementation is mechanical |
| PII surface in 28 callers | Profiled in the prior cycle; redaction profile registry is the next step, but it's an implementation task |
| NER layer for high-tier importers | Architecture decision deferred to replay; not the immediate unknown |
| 5-router harvest | Static; mechanical |
| Implementer gating | Mechanical; needs write-scope + receipt + HITL, all small PRs |
| Pydantic Router | Blocked on Jwalin (#3958) |
| `bg-sandbox-architect` choice | Will surface from githits; team picks from data |

**The capture latency is the one unknown where:**

- **It's the operational viability metric.** The NER decision is privacy. The PII profile is privacy. The capture latency is **user experience**. A 200ms p99 on every chat message is a UX regression that the team will feel within hours of merge.
- **The 28-importer chokepoint creates a write-amplification risk.** When chat, email-summary, and research all capture the same quoted text, `record_exchange` is called 3× for the same logical event. The dedup policy mitigates storage but not capture cost — every call still pays the read/hash cost.
- **The dedup step adds latency.** If dedup is at write time (first-wins), the 2nd and 3rd call still pay the read/hash cost. If dedup is at read time (merge), all 3 calls write — 3× the disk, 3× the JSONL appends.
- **Brief 7 (chat-through-router) multiplies the problem.** Every chat message becomes N captures across the 28 importers. If capture is slow, Brief 7 makes it worse.
- **The p99 is what users feel.** A 1ms average with a 200ms p99 means every 1-in-100 chat messages stalls. With 20K exchanges/day, that's 200 stalls. With 6-12 calls/min from the 28 importers, that's a stall every 5-10 min.

**Investigation plan:**

1. **Instrument `record_exchange`** in the chokepoint and the `route_code` subprocess path with timing:
   - Per-call latency (p50, p95, p99, max) by tier (high/medium/low)
   - Per-call latency by payload size bucket (<200, 200-1K, 1K-4K, 4K+)
   - Per-call latency by importer category

2. **Replay 20,000+ exchanges** through the instrumented code in dry-run mode. Use the same corpora as the NER replay (`~/.pi/agent/sessions`, `~/.codex/sessions`, `~/.claude/projects`).

3. **Measure write amplification**: how many distinct `task_hash` values appear in the replay? If the same content is captured by 3 importers, the amplification factor is 3×. Measure the actual factor.

4. **Measure dedup behavior**: if the policy is `first_wins`, how many writes are dropped? If `merge`, how much storage is used?

5. **Measure kill-switch behavior**: with `ODYSSEUS_NO_CAPTURE=1`, is the latency *zero* (the fast path)? With `ODYSSEUS_NO_CAPTURE=0`, is the latency within budget?

6. **Outcome**: a `docs/capture_performance_report.md` with the latency distribution, write amplification factor, and the operational budget decision.

**Why this gates operational viability:** the NER architecture is a *privacy* decision. The PII profile is a *privacy* decision. The capture latency is a *user-experience* decision. All three must be right. A 200ms p99 on every chat message is a UX regression no one notices in unit tests but every user feels.

**Concrete deliverable**: `docs/capture_performance_report.md` + a `tests/test_capture_invariants.py` extension that asserts p99 latency by tier.

---

## 5. Dashboard Card (1-Surface)

```
┌──────────────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ 🟡 CAPTURE CONTRACT READY    │ 🟡 UNKNOWN: capture p99      │ 🔴 FIRE-AND-FORGET GAP      │
│ task_hash policy spec'd.     │ latency on 20K real          │ Phase 2 not landed.          │
│ Dedup modes enumerated.      │ exchanges. Gates Brief 7    │ visibility_tools.py         │
│ Prompt type taxonomy.        │ (chat-through-router).      │ spec'd, not built.           │
│ Next: implementation +       │ 28 importers → write-amp    │ [test_visibility_tools_      │
│ benchmarks.                  │ risk. UX regression if p99  │  placeholder.py]            │
│ [test_task_hash_policy_       │ > 50ms.                      │                             │
│  exists.py]                  │                              │                             │
│ [test_task_hash_dedup_        │                              │                             │
│  policy.py]                  │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🟢 ROUND-STATE FIX READY      │ 🔴 bg-implementer LOOSE      │ 🟡 auth-bypass = admin       │
│ 1-PR fix closes #3992,        │ Self-modifying, no gate,     │ 2-line posture change,       │
│ #3993, #3998, #3961.         │ no receipt, no HITL.         │ no test.                     │
│ Test matrix in MR-OD-019.    │ Conflicts with 3 non-goals.  │ [test_localhost_bypass_       │
│ Implementer: 1-2 hours.      │ [test_implementer_miner_      │  auth.py]                    │
│                              │  gating.py]                  │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 CADENCE INSTABILITY       │ 🟡 5 routers, no harvest     │ 🟡 Phase 3 (super-skills)  │
│ 3 commits, 75 min,           │ plan. Sixth-router temp-     │ listed, not landed.         │
│ 6-100× interval change.      │ tation is real.              │ Repo map / auto-fix /        │
│ No measurement, no test.     │ [grep-and-inventory]         │ Cline checklist.            │
│ [test_miners_cadence_         │                              │                             │
│  governance.py]              │                              │                             │
└──────────────────────────────┴──────────────────────────────┴──────────────────────────────┘
🟢 aligned with North Star  🟡 spec'd but unverified  🔴 gap with no owner
```

**One-liner:** *The task_hash policy is 1 file. Land it. The capture latency measurement is the empirical gate. Land both. Brief 6 is shippable.*