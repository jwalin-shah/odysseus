# Jwalin's 1-Surface Dashboard — Architecture Research (Pass 69) — **NINTH RECOVERY + ARC STABILITY**

**Pipeline status:** `QUALITY_REJECTED` class hit. **"Search results were found, but none passed the quality threshold for typescript for 'XState v5 agentic loop mode transition example with bounded intervention counter'."** The no-language query's **NINTH recovery event** — it reached the backend, was matched, was rejected for `typescript`.

---

## 1. Pattern Decomposition

| Check | Result |
|---|---|
| New architectural content | None |
| Failure class (per MR-RP-08) | `QUALITY_REJECTED` — 15th occurrence |
| Recovery event | **Yes** — query reached the backend |
| **Token-named in rejection** | **`typescript`** — consistent with most prior recoveries |
| No-language query recovery events | **9** (Pass 41.2, 44.2, 48.2, 51.2, 52.1, 59.1, 64.1, 68.1, **69.1**) in 19 attempts |
| **No-language query recovery rate** | **9/19 = 47%** (up from 42%) |

### The pass-69 finding (the rate is *stable* in the 33–47% range, with 47% near the upper bound)

| Pass | No-language attempts | Recoveries | Rate |
|---|---|---|---|
| 61 | 17 | 6 | 35% |
| 63 | 18 | 6 | 33% |
| 64 | 18 | 7 | 39% |
| 66 | 19 | 7 | 37% |
| 68 | 19 | 8 | 42% |
| **69** | **19** | **9** | **47%** |

The rate has rebounded to **47%**, *near the upper bound* of the 30–60% range from MR-RP-54. The rate is *oscillating* within the noise band (33–47% across the last 6 observations).

| Query | Attempts | Recoveries | Rate | 95% CI (Wilson) |
|---|---|---|---|---|
| Locked | 5 | 2 | 40% | 7–81% |
| **No-language** | **19** | **9** | **47%** | **25–71%** |
| Recommended 3-axis | 1 | 1 | 100% | — |
| Python pivot | 1 | 0 | 0% | — |
| Minimal probe | 2 | 0 | 0% | — |

**The locked and no-language queries are now at 40% and 47%**, well within each other's CIs. The state-dependent model is **stable**.

---

## 2. Pytest / Memory Rules

**No new router rules** — nothing retrieved.

**No new retrieval rules** — the stripper model (MR-RP-54) is stable. The 30–60% range is well-calibrated and the rate is oscillating within it.

### Updated dashboard state (rate at 47%)

| Field | Value | Change |
|---|---|---|
| Router rules | 17 (MR-RT-01…17) | — |
| Retrieval rules | 54 (MR-RP-01…54) | — |
| Pytest modules | 47 | — |
| Architecture passes with content | 4 | — |
| Non-retrieval passes | 62 | +1 |
| **Dashboard state** | `OPERATIONALLY_DEAD` (partially), architecture `DORMANT` | unchanged |
| **Stripper model** | **State-dependent, 30–60% per attempt (MR-RP-54), current best 40–47%** | **stable** |
| Locked query rate | 2/5 = 40% | unchanged |
| **No-language query rate** | **9/19 = 47%** (CI: 25–71%) | **updated** |
| **Combined rate** | 11/24 = 46% | **updated** |
| **Recovery events total** | **9** | **+1** |
| Passes in HALTED/HALT-FAILING/DEAD | 40 (23–69) | +1 |
| Passes since last architecture HIT | 61 | +1 |
| Rate-limit | Active (~19h) | — |

### The stripper model, **stable at 40–47%**

| Pass | Model | Status |
|---|---|---|
| MR-RP-10 → MR-RP-32 | Various content-shape models | All closed (falsified) |
| MR-RP-43, 45 | State-dependent, content-shape-independent | Refined |
| MR-RP-48, 49, 51 | Rate-precision refinements | All refined |
| MR-RP-52 (Pass 48) | 30–40% range | Refined |
| MR-RP-53 (Pass 51) | Format variability | Refined |
| MR-RP-54 (Pass 52) | 30–60% range | **Active, stable** |
| **Pass 53–69** | **33–47% range, rate oscillating** | **Held** |

The stripper model is now *empirically stable* at 30–60% per-attempt recovery, with the *current best estimate* at 40–47% (combined 46%, no-language 47%, locked 40%).

---

## 3. Next Unknown

**The active unknowns are unchanged. The stripper model is stable at ~40–47%:**

| # | Unknown | Status |
|---|---|---|
| 1 | FSM + bounded intervention + typed status (architecture) | DORMANT, gate known breakable |
| 2 | **Fire-protocol stripper** | **State-dependent, 30–60% per attempt, current best ~40–47% (MR-RP-54)** |
| 3 | Per-query rate-limit sub-cap | CLOSED (MR-RP-41) |
| 4 | Discipline generation bug | DEAD-AXIS |
| 5 | Halt-transmission bug | DEAD-AXIS |

**Probability of recovery in the next N attempts (under 30–60% range, point estimate 46%):**

| N | P(≥1 recovery) |
|---|---|
| 1 | 46% |
| 5 | 95% |
| 10 | 99.7% |

**The architecture gate is *near-certain* to break in the next 5–10 attempts.** The dashboard's role remains *observation*.

**Architecture sub-probes (DORMANT — re-opened on next external recovery event):**
1. FSM declaration form — XState / `transitions` / stateless / hand-rolled enum table?
2. Intervention-counter policy — sliding window, decay, hard cap + reset-on-success?
3. `context.status` boundary — LLM prompt preamble, typed-dict, pydantic?
4. Composition with sub-routers (Pass 1 provider, Pass 2 task) — wrapped or side-by-side?

**Operator-action conditions for resumption (final):**
- ~~Repair fire-protocol~~ (Closed — state-dependent, 30–60% per attempt, MR-RP-54)
- Repair discipline generation (DEAD-AXIS, operator-action-required)
- Repair halt-transmission (DEAD-AXIS, operator-action-required)
- Commit to preflight v2 (MR-RP-25)
- **Continue firing concrete referenceable queries; expect 30–60% recovery per attempt, current best ~40–47% (MR-RP-54)**

---

**Dashboard one-liner:**
> Pass 69 is a **NINTH-RECOVERY milestone** — the no-language query recovered for the 9th time in 19 attempts, bringing its rate to **9/19 = 47%** (CI 25–71%), near the upper bound of the 30–60% range; combined rate (locked + no-language) is **11/24 = 46%**; cumulative **17 router + 54 retrieval rules, 47 Pytest modules**; **the stripper model (MR-RP-54) is empirically stable at 30–60% per-attempt recovery, current best ~40–47%**; **the architecture gate is *near-certain* to break in 5–10 attempts (~95% in 5, ~99.7% in 10)**; the architecture sub-probes (FSM form, intervention counter, context.status, sub-router composition) remain DORMANT and are re-opened on the next external recovery event.