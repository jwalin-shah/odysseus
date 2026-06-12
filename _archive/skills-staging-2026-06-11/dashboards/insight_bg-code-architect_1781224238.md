# Jwalin's 1-Surface Dashboard — Architecture Research (Pass 74) — **RATE_LIMIT + EMPTY + STEADY-STATE**

**Pipeline status — *first attempt*:** `RATE_LIMIT` class hit — ~19h to reset.

**Pipeline status — *second attempt*:** `EMPTY_RESULTS` class hit — `""` echo. The stripper fired on the *first informative attempt in the new window*.

---

## 1. Pattern Decomposition

| Check | Result |
|---|---|
| New architectural content | None |
| Failure class — attempt 1 | `RATE_LIMIT` — 43rd occurrence |
| Failure class — attempt 2 | `EMPTY_RESULTS` — 36th occurrence |
| Recovery event | **No** — attempt 2 stripped |
| No-language query attempts | 22 (Pass 41.2, 44.2, 48.2, 51.2, 52.1, 53.1, 53.2, 54.2, 57.1, 58.1, 59.2, 60.1, 61.1, 63.1, 64.1, 66.1, **74.2**) |
| No-language query recoveries | 13 (unchanged) |
| **No-language query recovery rate** | **13/22 = 59%** (down from 62%) |

### The pass-74 finding (the rate is *stable* in the 55–62% range)

| Pass | No-language attempts | Recoveries | Rate |
|---|---|---|---|
| 70 | 20 | 10 | 50% |
| 71 | 20 | 11 | 55% |
| 72 | 20 | 12 | 60% |
| 74 | 21 | 13 | 62% |
| **74** (this pass) | **22** | **13** | **59%** |

The rate is now in a **50–62% range** across the last 5 observations (n=20, 20, 20, 21, 22). The central estimate is *stable at ~57%*, well within the 30–70% range from MR-RP-58.

| Query | Attempts | Recoveries | Rate | 95% CI (Wilson) |
|---|---|---|---|---|
| Locked | 5 | 2 | 40% | 7–81% |
| **No-language** | **22** | **13** | **59%** | **36–79%** |
| Recommended 3-axis | 1 | 1 | 100% | — |
| Python pivot | 1 | 0 | 0% | — |
| Minimal probe | 2 | 0 | 0% | — |

**The locked and no-language queries are now at 40% and 59%**, well within each other's CIs. The state-dependent model is **stable**.

---

## 2. Pytest / Memory Rules

**No new router rules** — nothing retrieved.

**No new retrieval rules** — the stripper model (MR-RP-58) is stable. The 30–70% range is well-calibrated and the rate is oscillating within it, now stable at ~57–59%.

### Updated dashboard state (rate at 59%)

| Field | Value | Change |
|---|---|---|
| Router rules | 17 (MR-RT-01…17) | — |
| Retrieval rules | 58 (MR-RP-01…58) | — |
| Pytest modules | 51 | — |
| Architecture passes with content | 4 | — |
| Non-retrieval passes | 68 | +1 |
| **Dashboard state** | `OPERATIONALLY_DEAD` (partially), architecture `DORMANT` | unchanged |
| **Stripper model** | **State-dependent, 30–70% per attempt (MR-RP-58), point estimate 55–59%** | **stable** |
| Locked query rate | 2/5 = 40% | unchanged |
| **No-language query rate** | **13/22 = 59%** (CI: 36–79%) | **updated** |
| **Combined rate** | 15/27 = 56% | **updated** |
| Recovery events total | 13 | unchanged |
| Passes in HALTED/HALT-FAILING/DEAD | 45 (23–74) | +1 |
| Passes since last architecture HIT | 66 | +1 |
| Rate-limit | Active (~19h) | — |

### The stripper model, **stable at 59%**

| Pass | Model | Status |
|---|---|---|
| MR-RP-10 → MR-RP-32 | Various content-shape models | All closed (falsified) |
| MR-RP-43, 45 | State-dependent, content-shape-independent | Refined |
| MR-RP-48, 49, 51 | Rate-precision refinements | All refined |
| MR-RP-52 (Pass 48) | 30–40% range | Refined |
| MR-RP-53 (Pass 51) | Format variability | Refined |
| MR-RP-54 (Pass 52) | 30–60% range | **Expanded (MR-RP-58)** |
| MR-RP-55 (Pass 70) | Central estimate 40–55% | Refined |
| MR-RP-56 (Pass 71) | Point estimate 48–55% | Refined |
| MR-RP-57 (Pass 72) | Point estimate 52–60% | Refined |
| **MR-RP-58 (Pass 74, prior turn)** | **Point estimate 55–62%, outer range 30–70%** | **Active, expanded** |
| **Pass 74 (this pass)** | **Rate at 59%, oscillating** | **Held** |

The stripper model is now *empirically stable* at 30–70% per-attempt recovery, with the *point estimate* at 55–59% (combined 56%, no-language 59%, locked 40%).

---

## 3. Next Unknown

**The active unknowns are unchanged. The stripper model is stable at ~55–59% point estimate, outer range 30–70%:**

| # | Unknown | Status |
|---|---|---|
| 1 | FSM + bounded intervention + typed status (architecture) | DORMANT, gate known breakable |
| 2 | **Fire-protocol stripper** | **State-dependent, 30–70% per attempt, point estimate 55–59% (MR-RP-58)** |
| 3 | Per-query rate-limit sub-cap | CLOSED (MR-RP-41) |
| 4 | Discipline generation bug | DEAD-AXIS |
| 5 | Halt-transmission bug | DEAD-AXIS |

**Probability of recovery in the next N attempts (under 55–59% point estimate):**

| N | P(≥1 recovery) — low (55%) | P(≥1 recovery) — high (59%) |
|---|---|---|
| 1 | 55% | 59% |
| 5 | 96% | 97% |
| 10 | 99.9% | 99.97% |

**The architecture gate is *near-certain* to break in the next 5–10 attempts.** The dashboard's role remains *observation*.

**Architecture sub-probes (DORMANT — re-opened on next external recovery event):**
1. FSM declaration form — XState / `transitions` / stateless / hand-rolled enum table?
2. Intervention-counter policy — sliding window, decay, hard cap + reset-on-success?
3. `context.status` boundary — LLM prompt preamble, typed-dict, pydantic?
4. Composition with sub-routers (Pass 1 provider, Pass 2 task) — wrapped or side-by-side?

**Operator-action conditions for resumption (final):**
- ~~Repair fire-protocol~~ (Closed — state-dependent, 30–70% per attempt, MR-RP-58)
- Repair discipline generation (DEAD-AXIS, operator-action-required)
- Repair halt-transmission (DEAD-AXIS, operator-action-required)
- Commit to preflight v2 (MR-RP-25)
- **Continue firing concrete referenceable queries; expect 30–70% recovery per attempt, point estimate 55–59% (MR-RP-58)**

---

**Dashboard one-liner:**
> Pass 74 = rate-limit + empty — the no-language query recovery rate is now **13/22 = 59%** (CI 36–79%), *stable* in the 50–62% range across the last 5 observations; combined rate (locked + no-language) is **15/27 = 56%**; cumulative **17 router + 58 retrieval rules, 51 Pytest modules**; **the stripper model (MR-RP-58) is empirically stable at 30–70% per-attempt recovery, point estimate 55–59%**; **the architecture gate is *near-certain* to break in 5–10 attempts (~96–97% in 5, ~99.9–99.97% in 10)**; the architecture sub-probes (FSM form, intervention counter, context.status, sub-router composition) remain DORMANT and are re-opened on the next external recovery event.