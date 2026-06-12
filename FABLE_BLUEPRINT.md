# Fable Blueprint — V2 Implementation Plan (grounded against real code, 2026-06-11)

Label: **Fable**. Successor to `V2_MASTERPLAN.md`; this version replaces the miners'
inferred module paths with verified facts from `~/projects/orchestrator-mvp/src/`.
A background sweep of all ~140 substantive staging reports is in flight; merge its
findings here before closing out the build order.

---

## 0. Code-grounding results (verified today, not inferred from transcripts)

| Pattern | Miner's claim | Verified reality |
|---|---|---|
| P1 scope leak | interceptor missing | **Confirmed.** No `worker_runtime.py`, no `intercept_tool_call` anywhere in `src/`. `queue_manager.py:100,657` only *labels* `read_only_scope_violation` after the fact — nothing blocks the write. |
| P2 stub poisoning | ledger needs stub exclusion | **Confirmed gap.** Zero mentions of `stub` in `src/learning.py` — no exclusion exists. |
| P3 no pre-flight | dispatch lacks model/quota/argv checks | **Confirmed gap.** No `dispatch`/`quota`/`preflight` symbols in `src/provider_pool.py`. |
| P4 timeout partial writes | no rollback/quarantine | **Confirmed gap.** `queue_manager.py:423-436` fails rows on elapsed timeout (with adaptive classification) but no rollback or quarantine path exists. |
| P5 duplicate dispatch | enqueue lacks idempotency | **Confirmed gap.** No `enqueue` dedup; only asyncio `in_flight` task bookkeeping (`queue_manager.py:1807-1859`), which does not check workpack IDs. |

Module map correction: `src/ctl.py`, `src/learning.py`, `src/provider_pool.py`,
`src/queue_manager.py` exist; **`src/worker_runtime.py` does not** — the interceptor
must be created, and the drop-in test's import (`from src import worker_runtime`)
will be valid only after item 1 ships.

## 1. Build items (target repo: orchestrator-mvp unless noted)

### F1 — Write-scope interceptor (P1, MR-01/07) — *first PR*
Create `src/worker_runtime.py` with `intercept_tool_call(tool, path, scope) -> bool`:
- `scope="read-only"` → reject `Write`/`Edit`/`Bash` unconditionally.
- `scope="write=<paths>"` → allow writes only to listed paths.
- Reviewer role hard-bound read-only regardless of scope string (MR-07).
Wire it into the worker dispatch path so violations are *blocked*, not just labeled
at `queue_manager.py:100`. Ship `tests/test_queue_invariants.py` (full spec in
`data/skills_staging/insight_bg-transcript-architect_1781221523.md` §2) in the same PR;
`test_interceptor_present_and_enforces` is the acceptance gate.

### F2 — Ledger hygiene (P2, MR-02)
`LearningStore.load()` strips `provider == "stub"` records. Then run the counterfactual:
if `recommend_model` output changes with stub excluded, routing is unsafe today —
report that result before any further routing work.

### F3 — Pre-flight + idempotency (P3/P5, MR-03/06)
In `provider_pool.py`: model-exists ∧ quota-available ∧ argv-valid *before* slot claim;
raise typed `ModelUnavailable` / `QuotaExhausted`. In `queue_manager.py`: `enqueue`
raises `DuplicateWorkpack` / `WorkpackInFlight` on duplicate IDs per `(project, role)`,
checked against the ledger, not just the asyncio task set.

### F4 — Timeout rollback (P4, MR-04)
Extend the existing timeout-elapse path (`queue_manager.py:423`) with: if
`changed_files > 0` → `git checkout` rollback + quarantine the workpack + emit a
diff-only reviewer follow-up workpack.

### F5 — Dispatcher gate for the factory (odysseus repo)
The fix for the degenerate loops this run produced (masterplan §3):
- Research dispatch gated on a signed `topic_pivot` row in `data/work_queue.jsonl`;
  empty queue → typed `Quota` by construction.
- Semantic-content validation: reject missions that fingerprint-match prior
  halt/refusal/report output (the loop re-fed the synthesis architect its own halt
  message as a mission — "Bypass Attempt #28").
- Treat 0-byte insight writes as failures to retry-or-alert (this run silently lost
  ~65% of outputs).

### F6 — task_hash policy file (odysseus repo, decide-before-capture)
`core/task_hash_policy.json` fixing hash inputs (content vs semantic vs intent) and
`dedup_mode` before `record_exchange` ships; capture lands at both `llm_call_async`
and `route_code` together. Rules MR-OD-029…032 and the policy-exists test are in
`insight_bg-github-harvester_1781220443.md`.

## 1b. Items added by the full-staging sweep (all ~140 substantive reports read)

Sweep verdict: ~79% of substantive files were loop noise; the net-new signal came almost
entirely from **github-harvester** (rules MR-OD-011…028, 11 pytest spec files) and
**synthesis-architect** (test refinements). Source files:
`insight_bg-github-harvester_1781219654.md` and `_1781219848.md`.

### F7 — Round-boundary state reset (MR-OD-025/026/027/028) — *new critpath, odysseus*
Per-round state (`thinkOpen`, active tool fences, `prose_persisted`, …) must reset at
round boundaries per a documented state-field classification matrix
(`docs/round_state_contract.md`). One PR closes #3992, #3993, #3998, #3961, with
`test_round_boundary_state_reset.py` (8 tests) + `test_round_state_matrix.py` (6) +
`test_round_state_contract_documented.py` (3). **This is the prerequisite for Brief 5
measurement** — the flywheel is blocked until the dashboard's per-round state is
trustworthy. Lands before F9.

### F8 — bg-implementer gating (MR-OD-011) — *odysseus, safety*
The self-modifying miner stays disabled by default until write-scope enforcement,
per-change receipts, and an approval token exist. `test_implementer_miner_gating.py`
(4 tests). Depends conceptually on F1's interceptor pattern.

### F9 — Cadence governance (MR-OD-012) — *odysseus*
Miner-interval changes >2× require a "Measured:" citation in the commit body;
`test_miners_cadence_governance.py` (4 tests). Lands **after** F7, else Brief 5
rollups measure corrupted state.

### F10 — Hardening bundle (MR-OD-013/015/016/018) — *odysseus*
- LOCALHOST_BYPASS paired with non-loopback rejection tests (`test_localhost_bypass_auth.py`)
- Dispatch surfaces never 5xx — in-band error contract (`test_router_never_500.py`)
- Subprocess process-group reaping: `os.setsid` + kill -PGID on timeout (`test_subprocess_lifecycle.py`)
- `api_key_env` precedence env > db > None (`test_api_key_env_precedence.py`)

### Refinements to existing items
- **F1/F3:** add `test_no_workpack_redispatched` (P5 idempotency) to the invariants file;
  causal chain is P3 → P5 → P1/P4, so F3's pre-flight also shrinks P5 incidence.
- **F2:** assert the *direction* of the routing change when stub is excluded, not just
  binary difference.
- **F6:** `test_capture_at_chokepoint.py` (5 tests) joins the policy-exists test; the
  policy file must land **before** capture ships, hard-ordered.

## 2. Sequencing (revised after sweep)

- **orchestrator-mvp lane:** F1 → F2 → F3 → F4, each independently shippable.
- **odysseus lane (parallel):** F7 (critpath for Brief 5) → F6 → F9 → F5 → F8 → F10.
Validation per item: `rtk pytest <item tests> -q --no-cov`.

## 3. Open inputs

- ~~Background sweep~~ **Done — merged above (§1b).** Full report in the sweep agent
  transcript; rules MR-OD-011…028 verbatim in the two github-harvester source files.
- Ingestion still running (3,450/5,954 at blueprint time); re-harvest latest-per-architect
  when the cursor bottoms out — expect mostly loop noise per the sweep's 79% finding.
- GitHits research quota dead until ~2026-06-12 noon; no external-research lanes before then.
