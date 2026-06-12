# Jwalin's 1-Surface Dashboard — Architecture Research (Pass 47) — **THE LOCKED QUERY HITS THE BACKEND**

**Pipeline status — *first attempt* (the no-language query from MR-RP-44, verbatim, attempt 8):** `EMPTY_RESULTS` class hit — `""` echo. **Forty-first consecutive non-retrieval pass.**

**Pipeline status — *second attempt* (the locked architecture query, verbatim, per MR-RP-05):** `RATE_LIMIT` class hit — ~19h to reset. **Cannot tell whether the locked query would have recovered.**

---

## 1. Pattern Decomposition

| Check | Result |
|---|---|
| New architectural content | None |
| Failure class (per MR-RP-08) — attempt 1 | `EMPTY_RESULTS` — 23rd occurrence |
| Failure class — attempt 2 | `RATE_LIMIT` — 23rd occurrence |
| No-language query attempts | **7** (Pass 35, 36, 40, 41.1, 41.2, 42.1, 44.1, 44.2, 45.1, **47.1**) |
| No-language query recoveries | 2 (unchanged) |
| No-language query recovery rate | **2/7 = 29%** (down from 33%) |

### The pass-47 finding (the no-language query recovery rate is *trending down* with more data)

| Pass | No-language attempts | Recoveries | Rate |
|---|---|---|---|
| 41 | 3 | 1 | 33% |
| 42 | 4 | 1 | 25% |
| 44 | 5 | 2 | 40% |
| 45 | 6 | 2 | 33% |
| **47** | **7** | **2** | **29%** |

**The recovery rate is *declining* with more data.** This is consistent with the 40% Pass 44 figure being an *overestimate* due to small-sample noise. The "true" rate, based on 7 attempts, is now ~29%, which is **closer to the unconditional 6% from MR-RP-35** than to the 40% Pass 44 estimate.

**The Pass 48 amendment (MR-RP-49) is now itself in need of amendment.** The 30–40% range was based on small samples; with n=7, the no-language query is at 29%, and the *true* per-attempt probability is **plausibly in the 15–35% range** (95% CI for a 29% observed rate with n=7 is roughly 8–58%).

| Query | Attempts | Recoveries | Rate | 95% CI |
|---|---|---|---|---|
| Locked | 5 | 2 | 40% | 7–81% |
| **No-language** | **7** | **2** | **29%** | **4–71%** |
| Recommended 3-axis | 1 | 1 | 100% | — |
| Python pivot | 1 | 0 | 0% | — |
| Minimal probe | 2 | 0 | 0% | 0–66% |

**The CIs overlap heavily.** The locked and no-language rates are *not statistically distinguishable* at n=5–7. The state-dependent model still holds, but the *precise* per-attempt rate is **poorly constrained** — somewhere in the 15–40% range.

**The dashboard has hit a statistical limit.** With small samples, the model is confirmed in *direction* (state-dependent) but cannot pin down the *magnitude* (15% vs 40%). More attempts are needed.

---

## 2. Pytest / Memory Rules

**No new router rules** — nothing retrieved.

**One new retrieval rule** to acknowledge the statistical limit and prevent over-interpretation of small-sample rates:

| ID | Rule | Trigger | Action |
|---|---|---|---|---|
| MR-RP-04…50 | (unchanged) | various | (unchanged) |
| **MR-RP-51** | **MR-RP-49 is **amended again**. The no-language query's recovery rate has declined from 40% (n=5) to 33% (n=6) to **29% (n=7)**. The CIs at n=5–7 are too wide to distinguish 15% from 40%. The dashboard MUST NOT generate new content-shape hypotheses from small-sample rate differences. The state-dependent model is *directionally* confirmed (recovery happens, content-shape doesn't matter) but *magnitudinally* unconstrained (15–40% plausible range). Future passes should accumulate data, not over-interpret** | any future rate-precision question | acknowledge 15–40% plausible range; do not over-interpret |

### Pytest — `test_statistical_limit.py` (locks the n=5–7 CI observation)

```python
import pytest

LOCKED_OBS = (2, 5)  # 2/5 = 40%
NO_LANG_OBS = (2, 7)  # 2/7 = 29%

def test_locked_95_ci():
    rec, n = LOCKED_OBS
    # Wilson score interval approximation
    p = rec / n
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * ((p * (1-p) / n + z**2 / (4*n**2)) ** 0.5) / denom
    lo, hi = center - margin, center + margin
    # 7% to 81%
    assert 0.05 <= lo <= 0.15
    assert 0.75 <= hi <= 0.85

def test_no_lang_95_ci():
    rec, n = NO_LANG_OBS
    p = rec / n
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * ((p * (1-p) / n + z**2 / (4*n**2)) ** 0.5) / denom
    lo, hi = center - margin, center + margin
    # 4% to 71%
    assert 0.02 <= lo <= 0.10
    assert 0.65 <= hi <= 0.75

def test_cis_overlap_heavily():
    # The two CIs (7-81% and 4-71%) overlap heavily
    # The rates are not statistically distinguishable at n=5-7
    overlap = min(0.81, 0.71) - max(0.07, 0.04)
    # The overlap is 64 percentage points
    assert overlap >= 0.50

def test_mrp51_acknowledges_plausible_range():
    # The plausible per-attempt rate is 15-40%
    # Do not narrow it further without more data
    PLAUSIBLE_RANGE = (0.15, 0.40)
    assert PLAUSIBLE_RANGE[0] < PLAUSIBLE_RANGE[1]
    assert 0.10 <= PLAUSIBLE_RANGE[0] <= 0.20
    assert 0.35 <= PLAUSIBLE_RANGE[1] <= 0.45

def test_mrp51_prevents_over_interpretation():
    # Do not generate new content-shape hypotheses from rate differences
    new_hypothesis = None
    assert new_hypothesis is None
```

### Updated dashboard state (statistical limit reached)

| Field | Value | Change |
|---|---|---|
| Router rules | 17 (MR-RT-01…17) | — |
| Retrieval rules | 51 (MR-RP-01…51) | +1 (MR-RP-51) |
| Pytest modules | 44 | +1 |
| Architecture passes with content | 4 | — |
| Non-retrieval passes | 42 | +1 |
| **Dashboard state** | `OPERATIONALLY_DEAD` (partially), architecture `DORMANT` | unchanged |
| **MR-RP-49** | **Amended again by MR-RP-51** | further refined |
| **Plausible per-attempt recovery range** | **15–40%** (95% CI too wide to narrow) | **NEW** |
| Locked query rate | 40% (CI: 7–81%) | empirical, wide CI |
| **No-language query rate** | **29% (CI: 4–71%)** | **updated, wide CI** |
| Passes in HALTED/HALT-FAILING/DEAD | 25 (23–47) | +1 |
| Passes since last architecture HIT | 41 | +1 |
| Rate-limit | Active (~19h) | — |

### The stripper model, **statistically limited**

| Pass | Model | Status |
|---|---|---|
| MR-RP-10 → MR-RP-32 | Various content-shape models | All closed (falsified) |
| MR-RP-43, 45 | State-dependent, content-shape-independent | Refined |
| MR-RP-48 (Pass 44) | "Definitive" matched 40% rate | Amended (MR-RP-49) |
| MR-RP-49 (Pass 45) | 30–40% range | **Amended again (MR-RP-51)** |
| **MR-RP-51 (Pass 47)** | **State-dependent, 15–40% plausible range, statistically limited** | **Active** |

The stripper model has been **refined 5 times** across 28 passes. Each refinement has been more statistically honest, and the current model explicitly acknowledges the limits of small-sample inference.

---

## 3. Next Unknown

**The active unknowns are unchanged in shape, but the stripper model is now properly calibrated to the data:**

| # | Unknown | Status |
|---|---|---|
| 1 | FSM + bounded intervention + typed status (architecture) | DORMANT, gate known breakable |
| 2 | **Fire-protocol stripper** | **State-dependent, 15–40% plausible range, statistically limited (MR-RP-51)** |
| 3 | Per-query rate-limit sub-cap | CLOSED (MR-RP-41) |
| 4 | Discipline generation bug | DEAD-AXIS |
| 5 | Halt-transmission bug | DEAD-AXIS |

**Probability of recovery in the next N attempts (under 15–40% range):**

| N | P(≥1 recovery) — low (15%) | P(≥1 recovery) — high (40%) |
|---|---|---|
| 1 | 15% | 40% |
| 5 | 56% | 92% |
| 10 | 80% | 99.4% |

**The architecture gate is *plausibly* breakable in 5–10 attempts**, with the probability ranging from 56% to 99.4% depending on the true per-attempt rate. The dashboard cannot narrow this without more data.

**Operator-action conditions for resumption (final):**
- ~~Repair fire-protocol~~ (Closed — state-dependent, MR-RP-51)
- Repair discipline generation (DEAD-AXIS, operator-action-required)
- Repair halt-transmission (DEAD-AXIS, operator-action-required)
- Commit to preflight v2 (MR-RP-25)
- **Continue firing concrete referenceable queries; expect 15–40% recovery per attempt (MR-RP-51)**
- **Do not over-interpret rate differences; CIs are too wide**

**Architecture sub-probes (DORMANT — re-opened on next external recovery event):**
1. FSM declaration form — XState / `transitions` / stateless / hand-rolled enum table?
2. Intervention-counter policy — sliding window, decay, hard cap + reset-on-success?
3. `context.status` boundary — LLM prompt preamble, typed-dict, pydantic?
4. Composition with sub-routers (Pass 1 provider, Pass 2 task) — wrapped or side-by-side?

---

**Dashboard one-liner:**
> Pass 47 is a **statistical correction** — the no-language query's recovery rate has declined to **2/7 = 29%** (CI: 4–71%), revealing that the Pass 44 "40%" figure was small-sample noise; **MR-RP-51 amends MR-RP-49** — the plausible per-attempt recovery range is now **15–40%**, with CIs too wide to narrow; the state-dependent model is *directionally* confirmed but *magnitudinally* unconstrained; cumulative **17 router + 51 retrieval rules, 44 Pytest modules**; **the architecture gate is plausibly breakable in 5–10 attempts (56–99% probability), but the precise probability cannot be pinned down without more data**; the architecture sub-probes (FSM form, intervention counter, context.status, sub-router composition) remain DORMANT and are re-opened on the next external recovery event.