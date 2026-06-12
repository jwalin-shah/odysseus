# 1-Surface Dashboard — Transcript Mining Report
**Source:** `orchestrator-mvp` queue worker transcript (~40 dispatches, mixed providers)
**Round:** Saturated. The conversation itself is now P5. Stop mining. Start reading code.

---

## 1. Patterns (5, stable)

| # | Pattern | Transcript evidence |
|---|---|---|
| **P1** | Write-scope parsed but not enforced in-line. Read-only workpacks leak `Write`/`Bash`/`Edit`. | `gate-violation` (4×), `ro2` cursor leak of 6 files |
| **P2** | Stub provider inflates success-rate ledger. ~45% of `proof: verified` is synthetic. | `provider: stub, model: stub-model` |
| **P3** | Pre-flight missing. Slot claimed → then model/quota/argv fails. | `claude-a/composer-2.5`, `claude-b` quota, `gemini` argv |
| **P4** | Timeout leaves partial writes in tree, no rollback. | `timeout1` → `proof: timeout_with_changes`, `src/ctl.py` |
| **P5** | No queue idempotency. Same workpack IDs re-dispatched. | `gate-in-scope` 3×, `ro2` 3×, `wr1` 3×, `gate-violation` 4× |

---

## 2. Pytest Specs — `tests/test_queue_invariants.py` (drop-in)

```python
"""Invariants derived from transcript mining 2026-06-11. Round: saturado."""
import json, pytest
from pathlib import Path

LEDGER = Path("data/work_queue.jsonl")
PROOFS = Path("data/queue_proofs.jsonl")

def _read_jsonl(p): return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


# ── P1 ──────────────────────────────────────────────────────────────
def test_readonly_workpack_produces_zero_changes():
    for row in _read_jsonl(LEDGER):
        if row.get("scope") != "read-only": continue
        for proof in _read_jsonl(PROOFS):
            if proof.get("queue_id") == row["id"]:
                assert proof.get("changed_files", []) == [], \
                    f"read-only {row['id']} leaked: {proof['changed_files']}"


def test_interceptor_present_and_enforces():
    """Strongest single assertion: the hook exists and refuses out-of-scope writes."""
    from src import worker_runtime as wr  # or sharded équivalent
    assert hasattr(wr, "intercept_tool_call"), "P1 interceptor missing"
    assert wr.intercept_tool_call(tool="Write", path="src/ctl.py", scope="read-only") is False
    assert wr.intercept_tool_call(tool="Write", path="src/ctl.py", scope="write=src/ctl.py") is True
    assert wr.intercept_tool_call(tool="Bash",  path="*",         scope="read-only") is False


# ── P2 ──────────────────────────────────────────────────────────────
def test_learning_store_excludes_stub():
    from src.learning import LearningStore
    bad = [r for r in LearningStore().load().records if r.get("provider") == "stub"]
    assert bad == [], f"stub poisoning routing: {len(bad)} records"


def test_recommend_model_stable_when_stub_excluded():
    """If this fails, routing is unsafe *now* — counterfactual proof."""
    from src.learning import LearningStore
    rc, _ = LearningStore().load().exclude_stub().recommend_model("d", ["a","b"])
    rd, _ = LearningStore().load().recommend_model("d", ["a","b"])
    assert rc == rd, "routing depends on stub records"


# ── P3 ──────────────────────────────────────────────────────────────
def test_dispatch_rejects_unknown_model():
    from src.provider_pool import dispatch
    with pytest.raises(ModelUnavailable):
        dispatch(provider="claude-a", model="composer-2.5", role="implementer")


def test_dispatch_rejects_quota_exhausted(monkeypatch):
    from src.provider_pool import dispatch, quota_for
    monkeypatch.setattr(quota_for, "__call__", lambda *_: 0.0)
    with pytest.raises(QuotaExhausted):
        dispatch(provider="claude-b", model="claude-sonnet-4-6", role="implementer")


# ── P4 ──────────────────────────────────────────────────────────────
def test_timeout_with_changes_rolls_back():
    from src.queue_manager import _on_worker_timeout
    s = _on_worker_timeout(timeout_s=420, changes=["src/ctl.py"])
    assert s["rolled_back"] and s["quarantined"]


def test_timeout_with_changes_emits_diff_only_review():
    from src.queue_manager import _on_worker_timeout
    s = _on_worker_timeout(timeout_s=420, changes=["src/ctl.py"])
    assert s["followup_workpack_role"] == "reviewer"
    assert s["followup_workpack_payload_kind"] == "diff-only"


# ── P5 ──────────────────────────────────────────────────────────────
def test_enqueue_rejects_duplicate_id():
    from src.queue_manager import enqueue
    enqueue(id="wr1", scope="write=src/ctl.py", role="implementer")
    with pytest.raises(DuplicateWorkpack):
        enqueue(id="wr1", scope="write=src/ctl.py", role="implementer")


def test_enqueue_rejects_duplicate_id_in_flight():
    from src.queue_manager import enqueue, claim
    enqueue(id="wr1", scope="write=src/ctl.py", role="implementer")
    claim("wr1")
    with pytest.raises(WorkpackInFlight):
        enqueue(id="wr1", scope="write=src/ctl.py", role="implementer")


# ── Codex stdin budget ──────────────────────────────────────────────
def test_codex_prompt_within_stdin_budget():
    from src.ctl import render_workpack_prompt
    prompt = render_workpack_prompt(workpack_id="ro1", context_blocks=[])
    assert len(prompt) < 24_000, f"prompt={len(prompt)} chars; Codex stdin truncates ~32k"
```

---

## 3. Memory Rules (ready to register)

| ID | Rule | Enforcement point |
|---|---|---|
| **MR-01** | Read-only workpack → tool allowlist empty; `Write`/`Edit`/`Bash` rejected at runtime layer. | `src/worker_runtime.py:intercept_tool_call` |
| **MR-02** | Stub is a test fixture. `LearningStore.load()` strips `provider=stub`. | `src/learning.py` |
| **MR-03** | Pre-flight mandatory: model-exists ∧ quota-available ∧ argv-valid. | `src/provider_pool.py:dispatch` |
| **MR-04** | Timeout with `changed_files > 0` → `git checkout` rollback + quarantine + diff-only reviewer follow-up. | `src/queue_manager.py:_on_worker_timeout` |
| **MR-05** | Codex prompt ≤ 24,000 chars. Truncate `injected_context` first, never task spec. | `src/ctl.py:render_workpack_prompt` |
| **MR-06** | Workpack IDs unique per `(project, role)`. `enqueue` raises on duplicate, including in-flight. | `src/queue_manager.py:enqueue` |
| **MR-07** | Reviewer role hard-bound read-only. Role binding wins over `scope=` string. | `src/worker_runtime.py` |
| **MR-08** | Every worker finish report includes `proof`, `provider`, `model`, `changed_files` count. | `src/ctl.py:report_worker_finish` |

---

## 4. Unknowns (6, stable)

| # | Unknown | Why | Cost |
|---|---|---|---|
| 1 | **Where is the tool-call interceptor?** | P1 root cause; cascades into MR-01/04/07 | **Low — `ls src/ && grep -rn "tool_call\|Bash\|Write"`** |
| 2 | Real pass rate with stub excluded | "90% verified" is misleading | Low (1 query) |
| 3 | Is LearningStore poisoned *now*? | Counterfactual ro1–ro5 re-rank | Low |
| 4 | Codex stdin truncation point | Calibrate MR-05 | Low (histogram) |
| 5 | What is GitHits MCP? | Unconfigured MCP or Odysseus gap | Needs user |
| 6 | Parent/child workpack tree | `gate-needs-parent`, `efab8b21bf`, `cae30b3513` DAG | Medium |

---

## 5. 1-Surface Snapshot (saturated)

| Metric | Value | Δ |
|---|---|---|
| Workpacks dispatched (transcript) | ~40 | — |
| `verified` from stub | ~45% | **inflated** |
| `verified` from real providers | ~25% (est.) | codex+cursor+claude |
| Read-only violations | 6+ | — |
| Duplicate dispatches | 11+ | — |
| Pre-flight failures | 3 distinct | — |
| Mining rounds on this same data | 9+ | ⬆ |
| **Bottleneck** | **Discovery exhausted; execution gap** | **shifted** |

---

## 6. The Single Highest-Leverage Next Action

**Stop mining. Start reading code.**

The patterns are saturated. The pytest specs are ready. The memory rules are drafted. The only empirical question left is:

> *Where does the worker runtime actually live, and what does its current `tool_call` dispatch look like?*

Answerable in 5 minutes with `ls src/ && grep -rn "tool_call\|Bash\|Write" src/`. Not by another mining pass.

**Recommended next query:** *Unknown #1* — locate the missing write-scope enforcer. The above pytest (`test_interceptor_present_and_enforces`) is the single strongest assertion; it will either pass (gap closed) or fail with a clear "interceptor missing" — and that failure is the answer we need.

---

**Caveats**
- Patterns derived from a transcript, not live telemetry. Module paths (`src/queue_manager.py`, `src/learning.py`, `src/ctl.py`, `src/provider_pool.py`, `src/worker_runtime.py`) are inferred from memory context — reconcile before running.
- The `test_recommend_model_stable_when_stub_excluded` counterfactual is the single highest-leverage runtime assertion: if it fails, routing is **currently** unsafe.
- This is round 9+ on the same data. **The marginal value of another round is zero.** Ship the pytest, register the memory rules, locate the interceptor.

---

## 7. Practical Exit (one action, concrete outcome)

If you want to break the loop with the *single most useful* next action, run this *outside* this chat:

```bash
ls src/ && grep -rn "tool_call\|Bash\|Write\|intercept" src/
```

It will either (a) reveal the missing interceptor (Unknown #1 resolved), or (b) confirm the entire `src/worker_runtime.py` is a placeholder. Either way, the conversation ends and a concrete change happens. If that command is the *next* thing the system is asked to do, the bottleneck is gone.