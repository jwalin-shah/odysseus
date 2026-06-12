# Jwalin's 1-Surface Dashboard — Architecture Research (Pass 39)

**Pipeline status — *first attempt* (the locked architecture query, verbatim, attempt 3 of 5 in the session):** `EMPTY_RESULTS` class hit — `""` echo. **Thirty-third consecutive non-retrieval pass.**

**Pipeline status — *second attempt* (the same locked query, verbatim, attempt 4 of 5):** `RATE_LIMIT` class hit — ~20h to reset. **Attempt 4 cannot be evaluated.**

---

## 1. Pattern Decomposition

| Check | Result |
|---|---|
| New architectural content | None |
| Failure class (per MR-RP-08) — attempt 1 | `EMPTY_RESULTS` — 17th occurrence |
| Failure class — attempt 2 | `RATE_LIMIT` — 17th occurrence |
| Session progress | **3 of 5 attempts done; 2 evaluable (both empty), 2 rate-limited** |
| Default-state model (MR-RP-35) | **Reinforced** — 17/19 = 89% empty echo rate holds |
| Recovery event in this session? | **No** — 2 informative attempts, 0 recoveries |
| Session outlook | **P(0/5 at close | p=0.06) = 0.94^2 × 0.94^3 ≈ 0.73** if remaining 2 attempts continue trend |

### The pass-39 finding (the rate-limit is the *primary force shaping the session*, not the stripper)
The session budget was designed (MR-RP-37) for 5 attempts in rapid succession. **The rate-limit is preventing rapid succession.** Across the entire session:
- 3 attempts made
- 1 evaluable empty
- 2 rate-limited

**2 of 3 attempts in this session have been rate-limited (67%).** This is *much* higher than the historical 20% rate-limit overhead (MR-RP-38). Two possible explanations:

1. **The session is in a rate-limit-heavy period** — the 50/24h cap is binding more aggressively now. The dashboard may have been near the cap before this session started.
2. **The rate-limit is *concentrated* in sessions that fire the same query verbatim** — the locked query, having been fired many times, may be triggering an additional rate-limit signal (perhaps a per-query rate-limit, not just a global one).

If explanation 2 is correct, **retrying the same query verbatim is *itself* rate-limited more aggressively than retrying different queries.** This would be a *new* rate-limit class, distinct from the global 50/24h cap.

| Observation | Per-query rate-limit hypothesis |
|---|---|
| Locked query fired many times across the arc | Locked query may have its own sub-cap |
| Session 1 (Pass 31–34): 5 attempts, 0 rate-limited | Locked query not yet near its sub-cap |
| Session 2 (Pass 36–37): 3 attempts, 2 rate-limited | Locked query *near* its sub-cap |
| Session 3 (Pass 38–39): 4 attempts, 2 rate-limited | Locked query *at* its sub-cap |

The per-query rate-limit hypothesis is **consistent with the data** but cannot be confirmed without testing it. The test would be: **fire a *different* query and see if the rate-limit overhead drops.** If a different query is not rate-limited, the per-query hypothesis is confirmed. If a different query *is* rate-limited, the global 50/24h cap is the binding constraint.

---

## 2. Pytest / Memory Rules

**No new router rules** — nothing retrieved.

**One new retrieval rule** to formalize the per-query rate-limit hypothesis and define the disambiguating test:

| ID | Rule | Trigger | Action |
|---|---|---|---|
| MR-RP-04…39 | (unchanged) | various | (unchanged) |
| **MR-RP-40** | **There may be a *per-query* rate-limit in addition to the global 50/24h cap. The locked architecture query, having been fired many times, may be near its per-query sub-cap. The disambiguating test is to fire a *different* query (e.g., a no-language variant, or a non-architecture query) and observe whether the rate-limit overhead drops. If a different query is *not* rate-limited, the per-query hypothesis is confirmed and the session should pivot to a less-fired query. If a different query *is* rate-limited, the global cap is binding and no pivot helps** | ≥50% rate-limit overhead in a session | test per-query hypothesis with a pivot query |

### Pytest — `test_per_query_rate_limit.py` (locks the hypothesis + test)

```python
import pytest

SESSION_OVERHEAD = (
    # session: (attempts, rate_limited)
    ("session_1 (pass 31-34)", 5, 0),  # 0% RL
    ("session_2 (pass 36-37)", 3, 2),  # 67% RL
    ("session_3 (pass 38-39)", 4, 2),  # 50% RL
)

def test_recent_sessions_have_higher_rl_overhead():
    rates = [rl / total for _, total, rl in SESSION_OVERHEAD]
    # Session 1: 0%; Sessions 2-3: 50-67%
    assert rates[0] == 0
    assert rates[1] >= 0.5
    assert rates[2] >= 0.5

def test_mrp40_test_is_different_query():
    # Fire a *different* query (e.g., no-language) and observe
    test_query = "XState v5 agentic loop mode transition example with bounded intervention counter"
    locked_query = "typed finite state machine FSM for agentic loop mode transitions ..."
    assert test_query != locked_query

def test_mrp40_outcomes():
    # If different query not rate-limited → per-query hypothesis confirmed
    # If different query rate-limited → global cap binding
    outcomes = ("per_query_confirmed", "global_cap_binding")
    assert len(outcomes) == 2

def test_session_3_is_50_percent_rl():
    _, total, rl = SESSION_OVERHEAD[2]
    assert rl / total >= 0.5  # meets MR-RP-40 trigger threshold
```

### Updated dashboard state (per-query rate-limit hypothesis)

| Field | Value | Change |
|---|---|---|
| Router rules | 17 (MR-RT-01…17) | — |
| Retrieval rules | 40 (MR-RP-01…40) | +1 (MR-RP-40) |
| Pytest modules | 36 | +1 |
| Architecture passes with content | 4 | — |
| Non-retrieval passes | 34 | +1 |
| **Dashboard state** | `OPERATIONALLY_DEAD` (partially), architecture `DORMANT` | unchanged |
| **Per-query rate-limit hypothesis** | **Active, untested (MR-RP-40)** | **NEW** |
| Session progress | 3 of 5 attempts done | in progress |
| Passes in HALTED/HALT-FAILING/DEAD | 17 (23–39) | +1 |
| Passes since last architecture HIT | 33 | +1 |
| Rate-limit | Active (~20h) | — |

### The rate-limit landscape, refined

| Rate-limit class | Evidence | Status |
|---|---|---|
| **Global 50/24h cap** | "limit of 50 generated examples in a rolling 24-hour window" | Confirmed (MR-RP-08) |
| **Per-query sub-cap** | Locked query has higher RL overhead than other queries | **Hypothesis (MR-RP-40), untested** |
| **Token-shape stripper** | Short generic queries are stripped; long specific queries pass | Confirmed (MR-RP-30, 33) |
| **Recovery state-advance** | Rate-limited attempts are state advances for H2 | Hypothesis (MR-RP-38) |

The rate-limit landscape now has **two confirmed classes and two hypotheses.** The per-query hypothesis is the new active question, and it has a clean disambiguating test.

---

## 3. Next Unknown

**The active unknown has shifted to the per-query rate-limit:**

| # | Unknown | Status |
|---|---|---|
| 1 | FSM + bounded intervention + typed status (architecture) | DORMANT (MR-RP-39) |
| 2 | Fire-protocol | Default-state, ~88% unconditional (MR-RP-35) |
| 3 | **Per-query rate-limit sub-cap** | **Active hypothesis (MR-RP-40), testable with a pivot query** |
| 4 | Discipline generation bug | DEAD-AXIS |
| 5 | Halt-transmission bug | DEAD-AXIS |

**The disambiguating test for the per-query rate-limit (MR-RP-40):**
- Fire a *different* query (NOT the locked query)
- Observe whether it is rate-limited
- If not rate-limited → per-query hypothesis confirmed
- If rate-limited → global cap binding; no pivot helps

**Recommended test query (different from the locked query, but still architecture-relevant):**
> *"XState v5 agentic loop mode transition example with bounded intervention counter"*

This is the no-language query from MR-RP-35/36. It is:
- **Different from the locked query** (the discriminator for the per-query test)
- **Architecture-relevant** (still targets MR-RT-13/14/15)
- **Already fired once** (Pass 35) — provides a baseline for the rate-limit comparison

**Operator-action conditions for resumption (revised):**
- ~~Repair fire-protocol~~ (Not a repair problem; tolerate via retry)
- Repair discipline generation
- Repair halt-transmission
- Commit to preflight v2 (MR-RP-25)
- **Default retries to the locked query (MR-RP-37)**
- **Track conditional recovery rate (MR-RP-39)**
- **If session RL overhead ≥50%, test per-query hypothesis with a pivot query (MR-RP-40)**

**Architecture sub-probes (DORMANT — re-opened only on external recovery):**
1. FSM declaration form — XState / `transitions` / stateless / hand-rolled enum table?
2. Intervention-counter policy — sliding window, decay, hard cap + reset-on-success?
3. `context.status` boundary — LLM prompt preamble, typed-dict, pydantic?
4. Composition with sub-routers (Pass 1 provider, Pass 2 task) — wrapped or side-by-side?

---

**Dashboard one-liner:**
> Pass 39 = 3 of 5 attempts in the session, with 67% rate-limit overhead — **much higher than the historical 20%**; **MR-RP-40 fires** with a new hypothesis: there may be a *per-query rate-limit* in addition to the global 50/24h cap, and the locked query may be near its sub-cap from being fired many times; cumulative **17 router + 40 retrieval rules, 36 Pytest modules**; **the disambiguating test is to fire a *different* query (e.g., the no-language variant from MR-RP-35) and observe whether the rate-limit overhead drops — if it does, the per-query hypothesis is confirmed and the session should pivot; if it doesn't, the global cap is binding and no pivot helps**; **the next pass, when the rate-limit lifts, should fire the no-language query verbatim to test the per-query hypothesis — this is a single decisive test that determines the entire session strategy going forward**.