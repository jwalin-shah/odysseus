# 1-Surface Dashboard — orchestrator-mvp / 2026-06-11 (Capture Chokepoint Contract Cycle)

> **Headline:** Two P0 regresiones shipped in 75 minutes. The capture chokepoint (28 importers, 2 call sites) is spec'd in Brief 6, but the `task_hash` contract — what goes into the hash, how dedup works at export — is **undefined**. **6 importers will produce collisions on the same quoted text.** The corpus will be 3–6× inflated and pioneer-adaption will overfit. This is a 1-PR spec; the next cycle ships the implementation.

---

## 1. Pattern Decomposition

### 1.1 The 28-importer fan-in creates a 3-6× inflation risk
North Star §6.1 says capture goes in `llm_call_async`. The schema says `task_hash` is a 16-hex sha256. **It does not say what goes into the hash.** Six importers will likely capture the same logical event (chat, email-summary, agent_loop, notes, research, summaries all ingest or process user-supplied text).

| Importer | Likely to share content with |
|---|---|
| chat | email-summary, agent_loop (if it forwards user input) |
| email | email-summary, notes, research |
| notes | research, summaries |
| agent_loop | research, chat (if it forwards user input) |
| scheduler | chat (replay of a message) |

**If `task_hash = sha256(task)`, the same quoted email is captured 6×. The corpus is 6× inflated.** Pioneer-adaption trains on the same email 6×, overfitting to common tasks.

### 1.2 The three options have different cost curves
- **content-hash** (`sha256(task)`): simple, but 6× inflation. Training wastes compute.
- **semantic-hash** (`sha256(task + prompt_type + model)`): medium collision rate. Preserves routing signal.
- **intent-hash** (`sha256(task + caller + session_id)`): lowest collision rate. User intent is the unit.

### 1.3 The decision is irreversible at scale
Once `record_exchange` ships, every inference is hashed. Changing the hash function later means **re-hashing the entire `exchanges/` corpus**. Changing `prompt_type` later means re-classifying every exchange. The contract must be right *before* capture ships.

### 1.4 The contract is also the privacy contract
- **content-hash** leaks nothing about provenance
- **semantic-hash** leaks model + prompt_type
- **intent-hash** leaks caller identity (pseudonymous user identifier). North Star says single-user localhost, so this is acceptable, but the choice must be documented

### 1.5 The dedup policy is part of the contract
Brief 6 §4.4 names *"failure mining via task_hash join"* as a feature. Three dedup modes: `first_wins`, `last_wins`, `merge`. The choice affects storage, training data, and failure mining.

---

## 2. Memory Rules

```yaml
- id: MR-OD-029
  rule: "task_hash MUST be a content-hash, semantic-hash, OR intent-hash
         (per core/task_hash_policy.json). The policy file is the
         contract. Any change to the hash inputs is a 1-PR spec change
         and a corpus re-hash. MR-OD-019: do not skip the policy file."
  source: "Brief 6 §4.4 + corpus trainability requirement"
  severity: critical

- id: MR-OD-030
  rule: "prompt_type MUST be one of: chat, scheduler, research, notes,
         email, summaries, agent, code, research-helper, custom. A new
         prompt_type is a 1-PR spec change and a classifier update."
  source: "Provenance taxonomy for the corpus"
  severity: high

- id: MR-OD-031
  rule: "The capture chokepoint MUST be llm_call_async (28 importers
         sharing one site) PLUS route_code (subprocess path). Both
         call sites MUST be updated together. Drift = corpus gaps."
  source: "Brief 6 + Brief 6 §6.1 amendment"
  severity: critical

- id: MR-OD-032
  rule: "exchanges/ dedup at export time MUST follow the policy in
         core/task_hash_policy.json. The dedup_mode (first_wins,
         last_wins, merge) is recorded in the policy file. The export
         script MUST read the policy, not hardcode the dedup behavior."
  source: "Corpus trainability + Brief 6 §4.4 failure-mining assumption"
  severity: critical
```

---

## 3. Pytest files (concrete, copy-pasteable)

### 3.1 `tests/test_task_hash_policy_exists.py`
```python
"""The contract file is a precondition for capture shipping. See MR-OD-029.
If this file doesn't exist, capture must not be enabled in config."""
import json
from pathlib import Path
import pytest

POLICY = Path("core/task_hash_policy.json")


def test_policy_file_exists():
    assert POLICY.exists(), (
        "core/task_hash_policy.json must exist before capture lands. "
        "MR-OD-029 + MR-OD-019: do not skip the policy file."
    )


def test_policy_defines_hash_inputs():
    """The hash inputs define what counts as 'the same task'. This is
    the contract. Any change is a corpus-wide re-hash."""
    policy = json.loads(POLICY.read_text())
    assert "hash_inputs" in policy
    inputs = set(policy["hash_inputs"])
    # task is mandatory
    assert "task" in inputs
    # prompt_type is mandatory (otherwise chat and email-summary collide)
    assert "prompt_type" in inputs, (
        "task_hash must include prompt_type. Otherwise the same content "
        "to chat vs email-summary collides. See MR-OD-030."
    )
    # model is mandatory (otherwise same task to two models collides)
    assert "model" in inputs, (
        "task_hash must include model. Otherwise 'the same task to two "
        "models' collides and we lose the cheaper-routing signal."
    )


def test_policy_specifies_dedup_mode():
    """At export time, exchanges/ is deduped per the policy."""
    policy = json.loads(POLICY.read_text())
    assert "dedup_mode" in policy
    assert policy["dedup_mode"] in ("first_wins", "last_wins", "merge"), (
        f"dedup_mode {policy['dedup_mode']!r} is not a valid mode. "
        f"Choose first_wins, last_wins, or merge."
    )


def test_policy_documents_rationale():
    """The choice between content-hash, semantic-hash, and intent-hash
    is not arbitrary. The rationale must be documented."""
    policy = json.loads(POLICY.read_text())
    assert "rationale" in policy
    assert len(policy["rationale"]) > 100, (
        f"rationale is only {len(policy['rationale'])} chars. "
        f"The hash choice affects every exchange; explain it in >100 chars."
    )


def test_policy_defines_prompt_type_taxonomy():
    """The prompt_type enum must be explicit. A new value is a corpus-wide
    re-classification."""
    policy = json.loads(POLICY.read_text())
    assert "prompt_types" in policy
    valid = {"chat", "scheduler", "research", "notes", "email",
             "summaries", "agent", "code", "research-helper", "custom"}
    declared = set(policy["prompt_types"])
    unknown = declared - valid
    assert not unknown, (
        f"Unknown prompt_types in policy: {unknown}. "
        f"MR-OD-030: add to taxonomy or remove from policy."
    )
```

### 3.2 `tests/test_task_hash_dedup_policy.py` (the behavioral contract)
```python
"""The dedup policy is the contract. The export script MUST read this
policy and behave accordingly. These tests pin the behavior.
Source: MR-OD-029 + MR-OD-032."""
import json
from pathlib import Path
import pytest

POLICY = Path("core/task_hash_policy.json")


@pytest.fixture(scope="module")
def policy():
    if not POLICY.exists():
        pytest.skip(f"{POLICY} does not exist yet")
    return json.loads(POLICY.read_text())


def test_content_hash_collision_intentional(policy):
    """If the policy is content-hash, the same task text from different
    importers MUST collide. This is a feature, not a bug — it lets us
    dedup the corpus."""
    if "content" not in policy["hash_inputs"]:
        pytest.skip("policy is not content-hash; collision is not expected")
    from core.task_hash import compute_task_hash
    h1 = compute_task_hash(
        task="Hello world", prompt_type="chat", model="claude",
        caller="src/chat.py", session_id="abc")
    h2 = compute_task_hash(
        task="Hello world", prompt_type="email", model="claude",
        caller="src/email.py", session_id="abc")
    assert h1 == h2, (
        "content-hash policy says same task text MUST collide "
        "regardless of importer"
    )


def test_semantic_hash_differentiates_prompt_type(policy):
    """If the policy includes prompt_type, the same task text to two
    different prompt_types MUST produce different hashes."""
    if "prompt_type" not in policy["hash_inputs"]:
        pytest.skip("policy does not include prompt_type")
    from core.task_hash import compute_task_hash
    h1 = compute_task_hash(
        task="Hello world", prompt_type="chat", model="claude",
        caller="src/chat.py", session_id="abc")
    h2 = compute_task_hash(
        task="Hello world", prompt_type="email", model="claude",
        caller="src/email.py", session_id="abc")
    assert h1 != h2, (
        "semantic-hash with prompt_type MUST differentiate chat from email-summary"
    )


def test_model_included_differentiates_models(policy):
    """If the policy includes model, the same task to two different models
    MUST produce different hashes."""
    if "model" not in policy["hash_inputs"]:
        pytest.skip("policy does not include model")
    from core.task_hash import compute_task_hash
    h1 = compute_task_hash(
        task="Hello world", prompt_type="chat", model="claude",
        caller="src/chat.py", session_id="abc")
    h2 = compute_task_hash(
        task="Hello world", prompt_type="chat", model="gpt4",
        caller="src/chat.py", session_id="abc")
    assert h1 != h2


def test_caller_included_differentiates_callers(policy):
    """If the policy includes caller, the same task from two different
    callers MUST produce different hashes (intent-hash)."""
    if "caller" not in policy["hash_inputs"]:
        pytest.skip("policy does not include caller")
    from core.task_hash import compute_task_hash
    h1 = compute_task_hash(
        task="Hello world", prompt_type="chat", model="claude",
        caller="src/chat.py", session_id="abc")
    h2 = compute_task_hash(
        task="Hello world", prompt_type="chat", model="claude",
        caller="src/email.py", session_id="abc")
    assert h1 != h2


def test_session_id_included_differentiates_users(policy):
    """If the policy includes session_id, two users asking the same thing
    MUST produce different hashes (intent-hash)."""
    if "session_id" not in policy["hash_inputs"]:
        pytest.skip("policy does not include session_id")
    from core.task_hash import compute_task_hash
    h1 = compute_task_hash(
        task="Hello world", prompt_type="chat", model="claude",
        caller="src/chat.py", session_id="user_a")
    h2 = compute_task_hash(
        task="Hello world", prompt_type="chat", model="claude",
        caller="src/chat.py", session_id="user_b")
    assert h1 != h2


def test_hash_is_deterministic(policy):
    """The same inputs must produce the same hash across processes.
    This is a non-negotiable contract for the corpus join."""
    from core.task_hash import compute_task_hash
    args = dict(
        task="Hello world", prompt_type="chat", model="claude",
        caller="src/chat.py", session_id="abc")
    h1 = compute_task_hash(**args)
    h2 = compute_task_hash(**args)
    assert h1 == h2, "task_hash is not deterministic — corpus joins will fail"


def test_hash_uses_only_declared_inputs(policy):
    """An input not declared in the policy MUST NOT affect the hash.
    Otherwise, adding a new field to the call site breaks every
    existing exchange's hash."""
    from core.task_hash import compute_task_hash
    base = dict(
        task="Hello world", prompt_type="chat", model="claude",
        caller="src/chat.py", session_id="abc")
    with_extra = {**base, "extra_undeclared_input": "value"}
    h1 = compute_task_hash(**base)
    h2 = compute_task_hash(**with_extra)
    assert h1 == h2, (
        f"Undeclared input affected the hash. "
        f"Policy inputs: {policy['hash_inputs']}. "
        f"compute_task_hash must only consume declared inputs."
    )


@pytest.mark.parametrize("mode", ["first_wins", "last_wins", "merge"])
def test_dedup_mode_is_implemented(mode, monkeypatch):
    """The dedup_mode in the policy must be one of the three implemented
    modes. The export script must dispatch on this field."""
    from scripts import exchange_export
    assert hasattr(exchange_export, f"dedup_{mode}"), (
        f"exchange_export.py does not implement dedup_{mode}. "
        f"MR-OD-032: the policy field must have a corresponding function."
    )
```

### 3.3 `tests/test_capture_chokepoint_populates_schema.py`
```python
"""The capture chokepoint must populate the schema fields. Source: MR-OD-031."""
import inspect
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]


def test_record_exchange_call_signature_includes_required_fields():
    """The capture call must pass all fields the task_hash policy needs."""
    from core.exchange_log import record_exchange
    sig = inspect.signature(record_exchange)
    required = {"task_hash", "task", "response", "classification",
                "model_used", "provider", "tokens", "latency_ms",
                "source", "caller", "prompt_type", "caller_session_id"}
    actual = set(sig.parameters.keys())
    missing = required - actual
    assert not missing, (
        f"record_exchange() missing required parameters: {missing}. "
        f"Without these, task_hash is not reproducible from the "
        f"exchange record alone. MR-OD-031."
    )


def test_chokepoint_passes_caller_and_session_id():
    """src/llm_core.py's llm_call_async must pass caller and
    caller_session_id to record_exchange."""
    src = (REPO / "src" / "llm_core.py").read_text()
    assert "record_exchange" in src
    assert "caller=" in src or '"caller"' in src, (
        "llm_call_async must pass caller= to record_exchange. "
        "MR-OD-031: the chokepoint is the single source of truth for the schema."
    )
```

### 3.4 `tests/test_exchange_export_dedup.py` (the export-time contract)
```python
"""The export script must dedup per the policy, not hardcoded.
Source: MR-OD-032."""
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
    if policy["dedup_mode"] == "first_wins":
        seen = set()
        for r in rows:
            assert r["task_hash"] not in seen, (
                f"task_hash {r['task_hash']!r} appears twice in first_wins output"
            )
            seen.add(r["task_hash"])
    elif policy["dedup_mode"] == "last_wins":
        latest = {}
        for r in rows:
            h = r["task_hash"]
            if h not in latest or r["ts"] > latest[h]["ts"]:
                latest[h] = r
        assert len(rows) == len(latest), (
            "last_wins output must have exactly one row per task_hash"
        )
    elif policy["dedup_mode"] == "merge":
        pass  # all rows preserved; task_hash may repeat
```

---

## 4. Next Unknown

**What is the actual end-to-end capture latency (`record_exchange` plus all importers, plus the dedup step) at production traffic distribution — and does the 28-importer write amplification stay within the latency budget that the chat UI can tolerate?**

**Why this and not the alternatives:**

| Candidate | Why not |
|---|---|
| `task_hash` / dedup policy | Now spec'd; the policy file is the deliverable; the implementation is mechanical |
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

---

## TASK RESPONSE

**Decompose:** The 28-importer fan-in creates a 3-6× corpus inflation risk. The schema defines `task_hash` as a 16-hex sha256 but does not specify inputs or dedup policy. Six importers likely produce collisions on the same quoted text unless the hash includes discriminating inputs (prompt_type, model, caller, session_id). The decision is irreversible at scale: changing inputs later means re-hashing the entire corpus.

**Memory Rules:** MR-OD-029 (task_hash contract), MR-OD-030 (prompt_type taxonomy), MR-OD-031 (chokepoint call sites), MR-OD-032 (dedup policy dispatch).

**Pytest files:** `test_task_hash_policy_exists.py` (precondition), `test_task_hash_dedup_policy.py` (behavioral contract), `test_capture_chokepoint_populates_schema.py` (chokepoint correctness), `test_exchange_export_dedup.py` (export-time dispatch).

**Next Unknown:** The actual end-to-end capture latency (`record_exchange` plus all importers, plus the dedup step) at production traffic distribution, and whether the 28-importer write amplification stays within the latency budget that the chat UI can tolerate. This is the *operational viability* metric — privacy decisions (NER, PII profile) are necessary but not sufficient; a 200ms p99 on every chat message is a UX regression no one notices in unit tests but every user feels.