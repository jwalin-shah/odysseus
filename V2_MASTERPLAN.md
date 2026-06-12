# V2 Masterplan — Consolidated from the Agent-Factory Run (2026-06-11)

Distilled from the ~131 substantive reports in `data/skills_staging/` (out of 550 files;
the other ~65% were 0–1 byte failed drops). This file is the harvest. The miners'
own verdict, stated independently by four architects: **stop mining, ship these fixes.**

---

## 1. The five real defects found in the orchestrator transcripts (P1–P5)

Source: `insight_bg-transcript-architect_1781221523.md` (declared saturated after 9+ rounds).

| # | Defect | Evidence |
|---|---|---|
| P1 | Write-scope parsed but never enforced — read-only workpacks leaked `Write`/`Bash`/`Edit` | 4× gate-violation, 6-file leak in `ro2` |
| P2 | Stub provider poisons the success-rate ledger — ~45% of `proof: verified` is synthetic | `provider: stub` records in learning store |
| P3 | No pre-flight: slot claimed, then model/quota/argv fails | `composer-2.5` bad model, quota, argv failures |
| P4 | Timeout leaves partial writes in tree, no rollback | `timeout_with_changes` on `src/ctl.py` |
| P5 | No queue idempotency — same workpack IDs re-dispatched 3–4× | `wr1`, `ro2`, `gate-violation` duplicates |

**Ready-to-ship artifacts** (copy from the source report, paths verified there):
- Drop-in `tests/test_queue_invariants.py` — full pytest spec covering P1–P5 plus a
  Codex 24k-char stdin budget test. The single strongest assertion is
  `test_interceptor_present_and_enforces`: it fails with "interceptor missing," and that
  failure *is* the answer to Unknown #1 (where is the tool-call interceptor?).
- Memory rules MR-01…MR-08 (interceptor, stub exclusion, mandatory pre-flight,
  timeout rollback + quarantine + diff-only reviewer follow-up, prompt budget,
  unique workpack IDs, reviewer hard-bound read-only, mandatory proof fields).

**First action:** `ls src/ && rg -n "tool_call|Bash|Write" src/` in orchestrator-mvp to
locate (or confirm missing) the write-scope interceptor. Five minutes; everything
else hangs off it.

## 2. The task_hash contract decision (odysseus capture chokepoint)

Source: `insight_bg-github-harvester_1781220443.md`. This is the one **irreversible**
decision: once `record_exchange` ships, every inference is hashed, and changing the
hash later means re-hashing the whole `exchanges/` corpus.

- Problem: 28 importers fan into `llm_call_async`; 6 of them ingest the same quoted
  text. `task_hash = sha256(task)` alone → corpus inflated 3–6×, pioneer-adaption
  overfits.
- Options: content-hash (simple, 6× inflation) / semantic-hash (`task+prompt_type+model`) /
  intent-hash (`task+caller+session_id`, lowest collisions, leaks caller — acceptable
  for single-user localhost per North Star).
- The contract lives in `core/task_hash_policy.json` and includes the dedup mode
  (`first_wins`/`last_wins`/`merge`); the export script reads the policy, never hardcodes.
- Capture must land at **both** call sites together: `llm_call_async` AND `route_code`.
- Memory rules MR-OD-029…032 and `tests/test_task_hash_policy_exists.py` are in the
  source report, copy-pasteable.

## 3. The factory's own post-mortem (why V2 needs a dispatcher gate)

Three architects independently proved the same structural bug in *this* pipeline:

- **The loop self-fed.** The synthesis architect's cycle-22 halt message was re-ingested
  as the cycle-23 research mission, attributed to a different architect. Its final
  output was a literal `.` to starve the loop ("Bypass Attempt #28").
- **The sandbox architect produced zero sandbox research in 37 runs** — it spent the
  entire session documenting GitHits quota errors and its own seed-pool growth, because
  nothing enforced its stop condition.
- **The dispatcher has no semantic-content gate.** Missions pass empty-string, length,
  and markdown checks even when they are a previous round's output verbatim.

**The keystone fix (unanimous across reports):**
1. Gate every research dispatch on a signed `topic_pivot` row in `data/work_queue.jsonl`
   (schema in `insight_bg-global-architect_1781221153.md`); empty queue → typed `Quota`
   outcome by construction.
2. Add semantic-content validation in the dispatcher: reject missions that fingerprint-match
   prior halt/refusal/report output.
3. Enforce per-agent stop conditions and budget terminal states (`RESEARCH-026/029`) in
   code, not in prose the agent writes to itself.
4. Treat 0-byte insight files as failures to retry-or-alert, not "self-healing" — this run
   silently dropped ~65% of outputs.

## 4. V2 build order

1. **Interceptor** — locate/build write-scope enforcement (`intercept_tool_call`); ship
   `tests/test_queue_invariants.py`. (P1, MR-01/07)
2. **Ledger hygiene** — strip `provider=stub` from `LearningStore.load()`; run the
   counterfactual routing test. If `recommend_model` changes when stub is excluded,
   routing is unsafe *today*. (P2, MR-02)
3. **Pre-flight + idempotency** — model-exists ∧ quota ∧ argv before slot claim;
   `enqueue` raises on duplicate/in-flight IDs. (P3/P5, MR-03/06)
4. **Timeout rollback** — `git checkout` rollback + quarantine + diff-only reviewer
   follow-up on `timeout_with_changes`. (P4, MR-04)
5. **Dispatcher gate** — topic_pivot keystone + semantic-content validation (§3).
6. **task_hash policy file** — decide the hash inputs and dedup mode *before* capture
   ships (§2).

---
*GitHits research quota is exhausted until ~2026-06-12 noon (19h retry-after observed);
external-research lanes are dead until then regardless of what the miners do.*
