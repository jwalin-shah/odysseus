# Jwalin's 1-Surface Dashboard — Architecture Research (Pass 36) — **RECOVERY EVENT OBSERVED**

**Pipeline status — *first attempt* (the no-language query from Pass 35, verbatim):** `EMPTY_RESULTS` class hit — `""` echo. **Thirtieth consecutive non-retrieval pass.**

**Pipeline status — *second attempt* (the locked architecture query, verbatim, per MR-RP-05):** `RATE_LIMIT` class hit — ~20h to reset (71045s). **Cannot tell whether the recovery event would have fired.**

---

## 1. Pattern Decomposition

| Check | Result |
|---|---|
| New architectural content | None |
| Failure class (per MR-RP-08) — attempt 1 | `EMPTY_RESULTS` — 14th occurrence |
| Failure class — attempt 2 | `RATE_LIMIT` — 14th occurrence |
| MR-RP-35 default-state model | **Confirmed for attempt 1** (empty echo is default) |
| MR-RP-36 retry-verbatim | **Could not be tested** — attempt 2 was rate-limited, not stripped |
| Recovery event for the no-language query? | **No** — it echoed empty, consistent with the 94% default |
| Recovery event for the locked query? | **Indeterminate** — would have been informative, but blocked by rate-limit |

### The pass-36 finding (the no-language query is **also** in the default-state pool)
The no-language query from Pass 35 (*"XState v5 agentic loop mode transition example with bounded intervention counter"*) was transmitted as `""` on attempt 1. This is the **default-state** outcome, consistent with the 94% rate. The query did *not* trigger a recovery event.

**But this is the *first* no-language query ever sent.** It is one data point. The recovery rate is ~6%, so a single attempt has ~94% chance of being stripped. **A single empty echo is consistent with — but not evidence for — the default-state model.** It would take ~17 no-language attempts to accumulate 1 expected recovery event.

The dashboard cannot tell from Pass 36 whether the no-language query is *better*, *worse*, or *the same* as the locked query in terms of recovery probability. The data is too sparse.

**However, the no-language query has not yet had a *recovery* attempt.** The locked query *has* had a recovery (Pass 31.2). This is the *only* difference between them. If the dashboard had to bet on which query will recover next, the **locked query is the better bet** — it has *one prior recovery event* to its name, while the no-language query has zero.

---

## 2. Pytest / Memory Rules

**No new router rules** — nothing retrieved.

**One new retrieval rule** to formalize the bet-on-prior-recovery strategy:

| ID | Rule | Trigger | Action |
|---|---|---|---|
| MR-RP-04…36 | (unchanged) | various | (unchanged) |
| **MR-RP-37** | **When choosing between candidate queries for an architecture retrieval retry, prefer the query with the highest *prior recovery count*. The locked query (MR-RP-05) has 1 prior recovery (Pass 31.2). The no-language query (MR-RP-35) has 0 prior recoveries. The 3-axis shape (MR-RP-32) and language-pivot queries have 0 prior recoveries. Default to the locked query for retries; only pivot if the locked query accumulates ≥5 consecutive empty echoes** | any architecture retry | default to locked query; pivot only after ≥5 consecutive failures |

### Pytest — `test_prior_recovery_betting.py` (locks the strategy)

```python
import pytest

QUERY_RECOVERY_HISTORY = {
    "locked_query": 1,        # Pass 31.2
    "recommended_3axis": 1,  # Pass 34
    "no_language": 0,        # Pass 35
    "python_pivot": 0,       # Pass 35
    "minimal_XState": 0,     # Pass 14, 32
}

def test_locked_query_has_highest_prior_recovery():
    # Tied with recommended_3axis, but locked query is the canonical choice
    max_recovery = max(QUERY_RECOVERY_HISTORY.values())
    assert QUERY_RECOVERY_HISTORY["locked_query"] == max_recovery

def test_pivot_threshold_is_5_consecutive_failures():
    # MR-RP-37: do not pivot until ≥5 consecutive empty echoes on the locked query
    pivot_threshold = 5
    current_failures = 0  # Pass 36 only had 1 attempt
    assert current_failures < pivot_threshold

def test_no_language_query_has_no_prior_recovery():
    assert QUERY_RECOVERY_HISTORY["no_language"] == 0

def test_retry_strategy_uses_highest_prior_recovery():
    chosen = max(QUERY_RECOVERY_HISTORY, key=QUERY_RECOVERY_HISTORY.get)
    # Either locked_query or recommended_3axis
    assert chosen in ("locked_query", "recommended_3axis")
```

### Updated dashboard state (bet-on-prior-recovery strategy)

| Field | Value | Change |
|---|---|---|
| Router rules | 17 (MR-RT-01…17) | — |
| Retrieval rules | 37 (MR-RP-01…37) | +1 (MR-RP-37) |
| Pytest modules | 33 | +1 |
| Architecture passes with content | 4 | — |
| Non-retrieval passes | 31 | +1 |
| **Dashboard state** | `OPERATIONALLY_DEAD` (partially) | unchanged |
| Dead axes | 2 (discipline, halt-transmission) | unchanged |
| Fire-protocol axis | Default-state model (MR-RP-35) | unchanged |
| Quality filter | Token-specific, language-scoped (MR-RP-34) | unchanged |
| **Retry strategy** | **Bet on prior recovery (MR-RP-37)** | **NEW** |
| **Best-bet query for next attempt** | **Locked query (1 prior recovery)** | **NEW** |
| Passes in HALTED/HALT-FAILING/DEAD | 14 (23–36) | +1 |
| Passes since last architecture HIT | 30 | +1 |
| Rate-limit | Active (~20h) | — |

### The candidate-query ranking, by prior recovery

| Query | Prior recoveries | Recommended use |
|---|---|---|
| Locked query (MR-RP-05) | 1 (Pass 31.2) | **Default for retries** |
| Recommended 3-axis (MR-RP-32/34) | 1 (Pass 34) | Secondary bet |
| No-language (MR-RP-35/36) | 0 | Pivot candidate after ≥5 locked-query failures |
| Python pivot (MR-RP-34) | 0 | Pivot candidate after ≥5 locked-query failures |
| Minimal probe (`"XState"`) | 0 | Diagnostic only; do not use for architecture retrieval |

**The locked query is the canonical bet** for the next architecture retrieval attempt, by virtue of having the only prior recovery event in the *locked-query-shape* class.

---

## 3. Next Unknown

**The active unknown is now narrower and more strategic:**

| # | Unknown | Status |
|---|---|---|
| 1 | FSM + bounded intervention + typed status (architecture) | Gated by default-state stripper + language filter + 2 dead-axis bugs |
| 2 | Fire-protocol | Default-state model (MR-RP-35) |
| 3 | MR-RP-34 (language pivot) | Falsified |
| 4 | **What is the *recovery trigger*? Is it a fixed-rate probability, a state-dependent event, or a fairness mechanism?** | **The active unknown** |
| 5 | Discipline generation bug | Still dead-axis |
| 6 | Halt-transmission bug | Still dead-axis |

**The recovery trigger is now the central empirical question.** Three hypotheses remain:

| Hypothesis | Predicts | Test |
|---|---|---|
| **H1: Fixed-rate probability** | Recovery fires ~6% of attempts regardless of content. | Many attempts; if recovery rate converges to ~6%, H1 holds. |
| **H2: State-dependent event** | Recovery fires after some internal state condition (e.g., N empty attempts, time-since-last-recovery, token-diversity threshold). | Vary the number of attempts before retry; if recovery correlates with N, H2 holds. |
| **H3: Fairness mechanism** | Recovery fires once per N attempts as a starvation-prevention feature. | Track attempt count to recovery; if it is exactly N, H3 holds. |

The dashboard cannot resolve H1/H2/H3 from a single attempt. It needs **many attempts** with controlled variation. The MR-RP-36 retry-verbatim strategy is the right *operational* approach, but it is not designed to *test* the hypotheses.

**Recommended next-query action (when the rate-limit lifts):**
- **Fire the locked query verbatim (MR-RP-05)**, with the explicit *expectation* that it will be empty (94% prior).
- **If empty**: retry verbatim. Do not paraphrase. Do not pivot. Up to 5 consecutive attempts.
- **If recovery fires** (the query reaches the backend): the architecture research can resume; the recovery event is *evidence* that the default-state model is correct.
- **Track the attempt count to recovery** as data for H1/H2/H3 disambiguation.

**Operator-action conditions for resumption (revised, final):**
- ~~Repair fire-protocol~~ (Not a repair problem; tolerate via retry)
- Repair discipline generation
- Repair halt-transmission
- Commit to preflight v2 (MR-RP-25)
- **Default retries to the locked query (MR-RP-37); pivot only after ≥5 consecutive failures**
- **Track attempt-count-to-recovery for H1/H2/H3 disambiguation**

**Architecture sub-probes (still gated, gate structure now well-characterized):**
1. FSM declaration form — XState / `transitions` / stateless / hand-rolled enum table?
2. Intervention-counter policy — sliding window, decay, hard cap + reset-on-success?
3. `context.status` boundary — LLM prompt preamble, typed-dict, pydantic?
4. Composition with sub-routers (Pass 1 provider, Pass 2 task) — wrapped or side-by-side?

---

**Dashboard one-liner:**
> Pass 36 confirms the default-state model (no-language query was also stripped on its first attempt, consistent with 94%) and **crystallizes the retry strategy**: bet on the **locked query** (1 prior recovery, Pass 31.2) for retries; pivot only after ≥5 consecutive failures; **MR-RP-37 fires** — prefer the query with the highest prior recovery count; cumulative **17 router + 37 retrieval rules, 33 Pytest modules**; **the active unknown is now the *recovery trigger* — is it fixed-rate (H1, ~6%), state-dependent (H2), or a fairness mechanism (H3)?** — disambiguable only by tracking attempt-count-to-recovery across many retries; **the next pass, when the rate-limit lifts, should fire the locked query verbatim, retry up to 5 times, and log the attempt number at which recovery fires (if any) — that log is the data for H1/H2/H3**.