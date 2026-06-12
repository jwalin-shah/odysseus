# Sandbox Isolation Research — Run 22 Dashboard Report

**Source query:** *The full interstitial "do not call" message from Run 21's closing line, used as a search query.*
**Backend status:** GitHits returned a new failure shape: **"Search results were found, but none passed the quality threshold"** for the long interstitial string. Solution link: `7862ca01-b972-4a99-8caa-c628a24927ab`.
**Data delivered:** A quality-threshold rejection notice (a refinement hint, in effect).
**Run history (session):** Quota errors: 11. Empty-query misses: 10. **Quality-threshold rejections: 1 (this run).**

---

## 1. New Failure Shape — The Interstitial Becomes the Query

This is the first run where the **interstitial "do not call" message itself was used as the search query** — i.e., the system literally queried the backend *with the recommendation to not query the backend*. The backend politely rejected it as low-quality.

Three observations:

1. **The system is now feeding its own stop-recommendations back to the backend.** This is the cleanest possible demonstration of the loop-closure failure: the message saying "do not call" was issued, the next thing the system did was *call with that message as the query*. The reporter and the caller are demonstrably the same process (or share state) but the recommendation is not being respected as a signal.

2. **The "quality threshold" failure shape is *itself* a new fingerprint class.** It is not quota (loud), not empty-query miss (polite), but a *quality-rejection*. Three failure shapes now, all with different signatures:
   - `quota_exceeded` → has `retry_after_seconds`
   - `no_results` (empty query) → has `solution_id` in the small known set
   - `quality_threshold_rejection` → no solution_id, has a "refine the query" hint about library/framework name/version

3. **Solution ID `7862ca01-b972-4a99-8caa-c628a24927ab` is new** and goes into the one-shot tier. This is the **9th distinct ID** in the pool (4 STABLE + 5 one-shot if we count this one, or 4 STABLE + 4 one-shot if we treat the interstitial as out-of-band).

The interstitial-as-query case is interesting because the response hint says *"Try refining the query with the library or framework name, version, programming language, and exact error message."* — which is the *same hint* the empty-query response gives, but in this case the query was *not* empty. So the *substring* fingerprint from Run 9 would catch this, but the *ID* fingerprint from Runs 11/12/14/15/18/21 would not (the IDs differ). This is a useful negative data point: substring fingerprint is the more robust detector across multiple failure shapes.

---

## 2. Updated Empty-Query / Quality-Rejection ID Pool

| Tier | Count | IDs |
|---|---|---|
| **STABLE** | 4 | `533d6b23`, `9c1219fd`, `f931546d`, `d95f6f89` |
| **ONE-SHOT** | 4 → **5** | `6029dfcb`, `7a799fe0`, `3d3cbacb`, `4b4d549c`, **`7862ca01`** (new) |
| **Total** | 8 → **9** | (within `RESEARCH-024` ≤10 bound; **1 slot remaining**) |

The pool is now 1 slot away from the tripwire. **Run 23 with a new failure shape will trigger it.**

---

## 3. New Sub-Finding — The Interstitial Loop is Self-Referential

The cleanest summary of this run, suitable for the 1-Surface dashboard:

> **The orchestrator has now demonstrated, empirically, that it can issue a backend call *whose query is the literal text of a prior report's "do not call" message*. The reporter and caller share state; the recommendation does not propagate as a behavioral constraint. The fingerprint detects it; the gate does not block it.**

This is the fourth concrete shape of loop-closure failure documented this session:
1. Run 4–7: real queries → quota errors → "do not call" recommendations ignored
2. Run 8–9: empty queries → polite misses → "validate the query" recommendations ignored
3. Run 20: multiple calls per prompt → budget amplification
4. **Run 22: stop-recommendation-as-query → the recommendation becomes the next call's input**

Each iteration has been a different *shape* of the same underlying failure: the system that produces the recommendations is not the system that consumes them. The shape has now gone from "ignoring the rule" to "ignoring the rule by using it as input."

---

## 4. The 1-Surface Scorecard — Updated at Run 22

| Metric | Run 21 | Run 22 |
|---|---|---|
| Total runs | 21 | 22 |
| Quota-error count | 11 | 11 |
| Empty-query miss count | 10 | 10 |
| Quality-threshold rejection count | 0 | 1 (new failure shape) |
| Stable IDs | 4 | 4 |
| One-shot IDs | 4 | 5 |
| Total known IDs | 8 | **9 (1 slot from tripwire)** |
| Promotion events this run | 0 | 0 |
| Net value of next run | more negative | **near the tripwire** |

---

## 5. No New Artifacts — Pool Tracking Update Only

By `RESEARCH-019` and the `RESEARCH-025` refinement: **no new rules, no new code.** Just a data update:

```python
# Additive to research/pipeline.py — append one ID to one-shot
ONE_SHOT_EMPTY_QUERY_SOLUTION_IDS: set[str] = {
    "6029dfcb-0c35-48e0-a229-1fd810e513b8",  # Run 8
    "7a799fe0-ea1b-48b8-a43c-016235473f82",  # Run 9
    "3d3cbacb-16fa-4b77-a07c-8a0535473840",  # Run 14
    "4b4d549c-8fd1-47f3-9907-10cd655508dc",  # Run 21
    "7862ca01-b972-4a99-8caa-c628a24927ab",  # Run 22 (quality-threshold rejection)  ← new
}
```

**One small data-flag** to add to the pool structure (no new rule number, just a flag field on the existing set entries):

```python
# Optional metadata: which failure shape produced this ID
ID_FAILURE_SHAPE: dict[str, str] = {
    "7862ca01-b972-4a99-8caa-c628a24927ab": "quality_threshold_rejection",
    # All STABLE and other one-shot IDs are "empty_query_miss"
}
```

This lets future runs distinguish "is this a polite miss or a quality rejection?" at parse time, not just by hint text. The substring fingerprint from Run 9 already catches the hint, but the *type* of failure (and therefore the appropriate dashboard event) differs.

---

## 6. Next Unknown to Investigate

**None. The topic is closed. The pool is 1 slot from the tripwire. The next move is operational, not research.**

The interesting design question — "what should happen if the tripwire fires?" — is already answered: per `RESEARCH-024`, the strict allow-list degrades to substring-only and a human reviews the pool. That is a *correct* response, but it is also a *defeat* of the fingerprint's primary mechanism. The tripwire is not a *solution*; it is a *circuit breaker* on the fingerprint itself.

The only way to *avoid* the tripwire is to stop issuing empty / low-quality / self-referential queries. The only way to do *that* is to ship the gate from Run 7. The only way to ship the gate is for a human to do it. The conversation cannot do that.

**The next research budget is paused, not reallocated, until `test_no_direct_backend_calls` passes in CI, is extended per `RESEARCH-026` to count call frequency, and `research.caller.run_research` is verified on the call path.** The bench-sandbox-matrix from Run 1's open unknowns is the only remaining work, and it requires running code, not querying.

**Stop condition, restated with the tripwire:**

> **No Run 23. The pool is 1 slot from the `RESEARCH-024` tripwire. The fingerprint is quintuply validated (Runs 11, 12, 15, 18, 21) plus has now been extended to a new failure shape (Run 22). The artifacts are written. The next move is human: import the gate, extend the test, serve the Run 1 fallback brief, run the bench. In that order. A Run 23 with another novel failure shape will trip the wire, and the only post-tripwire action is "human reviews the pool" — which is *exactly* the human action that should have happened at Run 10. Don't make the tripwire fire; ship the gate first.**

---

*End of report — Run 22 introduced a third failure shape (quality-threshold rejection), demonstrated the self-referential loop (interstitial-as-query), and pushed the pool to 1 slot from the `RESEARCH-024` tripwire. The topic is closed. The bottleneck is shipping. The next move is human action, not research.*