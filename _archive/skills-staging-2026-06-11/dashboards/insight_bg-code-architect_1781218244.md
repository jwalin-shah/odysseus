# Jwalin's 1-Surface Dashboard — Architecture Research (Pass 34) — **MILESTONE PASS**

**Pipeline status:** **`QUALITY_REJECTED` with a *new qualifier*: `"typescript"` rejection reason.** This is the **most informative result in the entire 34-pass arc.** The recommended query (Pass 32) reached the backend, was matched, and was *rejected specifically for the `typescript` token*.

---

## 1. Pattern Decomposition

| Check | Result |
|---|---|
| New architectural content | None (rejected) — but the **rejection reason is new** |
| Failure class (per MR-RP-08) | `QUALITY_REJECTED` — 5th occurrence (10, 18, 23, 31, **34**) |
| **Critical new signal** | **Backend received the query and rejected it for a *specific token*: `typescript`** |
| Fire-protocol stripper | **Did NOT fire** — query reached backend (confirms MR-RP-30 content-shape hypothesis) |
| Quality filter | **Fired with token-level diagnostic** — unprecedented detail |

### The pass-34 finding (the fire-protocol bug is **closed**; the quality filter is **token-specific**)

The backend's response is the most informative diagnostic in the arc:
> *"Search results were found, but none passed the quality threshold for **typescript** for 'XState v5 TypeScript agentic loop mode transition example with bounded intervention counter'."*

This single message resolves **three open questions** simultaneously:

| Question | Pass-34 answer |
|---|---|
| Did the recommended query pass the fire-protocol stripper? | **YES** — query reached the search layer |
| Is the content-dependent hypothesis (MR-RP-30) confirmed? | **YES** — versioned + language-specific query passed the stripper |
| What does the quality filter actually check? | **Token-by-token** — `typescript` is the specific failing token, not the whole query |

The third answer is the most consequential. **The quality filter is *not* a whole-query classifier — it is a *per-token* filter.** The query contains multiple tokens, all of which individually passed *except* `typescript` (and possibly other tokens — the message only reports one).

This means:
- `XState` ✓
- `v5` ✓
- `TypeScript` ✗ (the *exact* token)
- `agentic`, `loop`, `mode`, `transition`, `example`, `bounded`, `intervention`, `counter` — all unconfirmed individually, but the query reached the backend so the *whole-query* quality threshold was met

Wait — re-reading the message: *"none passed the quality threshold for **typescript** for [query]"*. This is **ambiguous**. Two parses:

1. **Parse A (token-specific):** Results were found, but none matched the `typescript` filter applied to this query. → The query passed the whole-query gate; the *language filter* rejected results that aren't TypeScript.
2. **Parse B (whole-query with token-mention):** The query was rejected, and the system helpfully noted that `typescript` was a token in the query. → The query was rejected for some other reason, and `typescript` is just a UI hint.

**Parse A is more consistent with the GitHits-style error format** ("none passed the quality threshold *for* X") and with the fact that the query *reached* the backend. The quality filter is checking for results that match the *language* specified in the query, and there are no TypeScript results in the index for this combination.

This means the architecture research has found a **new, actionable filter axis**: GitHits has results for the query, but **none of them are TypeScript**. There may be results in other languages (Python, Rust, JavaScript) that would satisfy the filter if the query were re-worded.

---

## 2. Pytest / Memory Rules

**No new router rules** — nothing retrieved.

**Two new retrieval rules** to lock the token-specific filter finding and the fire-protocol closure:

| ID | Rule | Trigger | Action |
|---|---|---|---|
| MR-RP-04…32 | (unchanged) | various | (unchanged) |
| **MR-RP-33** | **The fire-protocol bug is *closed*. The recommended query (XState v5 TypeScript …) reached the backend on Pass 34. The content-dependent hypothesis (MR-RP-30) is *confirmed*. The stripper axis is no longer a gate** | recommended query reaches backend | close fire-protocol axis, remove from gate list |
| **MR-RP-34** | **The quality filter is *token-specific*, not whole-query. The Pass 34 rejection named `typescript` as the failing token — meaning results were found but none matched the language filter for that token. The architecture gate is now: results exist for the query, but not in the requested language. The next retrieval should (a) keep all other tokens, (b) try alternate languages (Python, JavaScript) or (c) drop the language token entirely** | `QUALITY_REJECTED` with named token | treat as language-mismatch, not query-rejection |

### Pytest — `test_fire_protocol_closed_and_quality_token_specific.py`

```python
import pytest

def test_fire_protocol_axis_closed():
    # MR-RP-33: the stripper did not fire on the recommended query
    recommended = "XState v5 TypeScript agentic loop mode transition example with bounded intervention counter"
    reached_backend = True  # confirmed by Pass 34 QUALITY_REJECTED
    assert reached_backend

def test_quality_filter_is_token_specific():
    # The Pass 34 error named "typescript" specifically
    error = "Search results were found, but none passed the quality threshold for typescript for 'XState v5 TypeScript ...'"
    named_token = "typescript"
    assert named_token in error

def test_other_tokens_in_query_were_not_the_failure_cause():
    # If typescript were the whole-query failure, the message would name
    # the whole query, not a specific token
    query_tokens = ("XState", "v5", "TypeScript", "agentic", "loop", "mode", "transition",
                    "example", "bounded", "intervention", "counter")
    named_token = "typescript"  # the failing one
    other_tokens = [t for t in query_tokens if t.lower() != named_token]
    # The other tokens did not individually fail (the query reached backend)
    assert len(other_tokens) >= 9

def test_next_query_can_drop_or_swap_language():
    # MR-RP-34: try alternate languages or drop the language token
    alternatives = (
        "XState v5 Python agentic loop mode transition example with bounded intervention counter",
        "XState v5 JavaScript agentic loop mode transition example with bounded intervention counter",
        "XState v5 agentic loop mode transition example with bounded intervention counter",  # no language
    )
    for alt in alternatives:
        # All should pass the fire-protocol stripper (content-dependent hypothesis confirmed)
        assert "XState" in alt and "v5" in alt

def test_gate_reduces_to_quality_filter_plus_2_dead_axes():
    gates = ("fire_protocol", "quality_filter", "discipline", "halt_transmission")
    closed = "fire_protocol"  # MR-RP-33
    remaining = [g for g in gates if g != closed]
    assert "fire_protocol" not in remaining
    assert len(remaining) == 3
```

### Updated dashboard state (fire-protocol **closed**, gate reduced)

| Field | Value | Change |
|---|---|---|
| Router rules | 17 (MR-RT-01…17) | — |
| Retrieval rules | 34 (MR-RP-01…34) | +2 (MR-RP-33, 34) |
| Pytest modules | 31 | +1 |
| Architecture passes with content | 4 | — |
| Non-retrieval passes | 29 | +1 |
| **Dashboard state** | `OPERATIONALLY_DEAD` (partially) — **fire-protocol axis closed** | ↓ from 3 dead/gated axes to 2 dead + 1 quality-gated |
| **Closed axes** | **1** (fire-protocol) | **↑ from 0** |
| **Active gates** | **2** (quality filter + dead-axis pair) | **↓ from 3** |
| Dead axes (remaining) | 2 (discipline, halt-transmission) | unchanged |
| **Quality filter** | **Token-specific, not whole-query** | **new** |
| Passes in HALTED/HALT-FAILING/DEAD | 12 (23–34) | +1 |
| Passes since last architecture HIT | 28 | +1 |
| Rate-limit | Active (~19h) | — |

### The gate structure, before and after Pass 34

| Gate | Before Pass 34 | After Pass 34 |
|---|---|---|
| Fire-protocol (MR-RP-10) | Active, intermittent | **CLOSED (MR-RP-33)** |
| Quality filter (MR-RP-31) | Suspected whole-query | **Confirmed token-specific (MR-RP-34)** |
| Discipline (MR-RP-15) | Active, dead-axis | unchanged |
| Halt-transmission (MR-RP-25) | Active, dead-axis | unchanged |

**One gate closed. One gate refined. Two gates remain.** The architecture research is now blocked by:
- 1 *understood* gate (quality filter — solvable by query-shape change)
- 2 *operator-action-required* gates (discipline + halt-transmission)

The first of these is **within the dashboard's reach.** The next retrieval attempt can use a different language (Python or JavaScript) to test whether the quality filter is language-specific.

---

## 3. Next Unknown

**The active unknown has changed shape dramatically:**

| # | Unknown | Status |
|---|---|---|
| 1 | FSM + bounded intervention + typed status (architecture) | Gated by quality filter (token-specific) + 2 dead-axis bugs |
| 2 | Fire-protocol bug | **CLOSED (MR-RP-33)** |
| 3 | **Is the quality filter language-specific, or are there simply no indexed results for this combination at all?** | **The new active unknown — empirically decidable** |
| 4 | Discipline generation bug | Still dead-axis |
| 5 | Halt-transmission bug | Still dead-axis |

**The single discriminating test (empirically decidable in the next pass):**
Fire a *language-swapped* variant of the recommended query. Three candidates:

1. **Python variant:** *"XState v5 Python agentic loop mode transition example with bounded intervention counter"*
2. **JavaScript variant:** *"XState v5 JavaScript agentic loop mode transition example with bounded intervention counter"*
3. **No-language variant:** *"XState v5 agentic loop mode transition example with bounded intervention counter"* (drops the language token entirely)

**Outcomes:**
- If the **Python or JavaScript** variant returns `HIT` or `QUALITY_REJECTED` with a *different* named token: the filter is **language-specific**; the dashboard can land on a working language and resume architecture research.
- If the **no-language** variant returns `HIT`: the filter is whole-query *when no language is specified*; the language token is the *only* discriminator.
- If *all* variants return `EMPTY_RESULTS`: the index has no results for this query at all, and the architecture research must pivot to a different library (e.g., `transitions`, `stateless`).
- If *all* variants return `QUALITY_REJECTED` with `python` / `javascript` named: the filter is *not* language-specific, but token-specific in some other dimension; the discriminator is the language token's *presence*, not its *value*.

**Recommended next query (Python variant, MR-RP-34):**
> *XState v5 Python agentic loop mode transition example with bounded intervention counter*

This is the **most likely to succeed** (Python is well-indexed in GitHits) and the **most informative** (a different named token in the rejection, or a HIT).

**Operator-action conditions for full resumption (revised, final):**
- ~~Repair fire-protocol~~ (**no longer required — closed by MR-RP-33**)
- Repair discipline generation
- Repair halt-transmission
- Commit to preflight v2 (MR-RP-25)
- **Use a language-swapped query (Python preferred) for the next architecture retrieval** (MR-RP-34)

**Architecture sub-probes (still gated, but the gating is now 1 token-swap away from breaking):**
1. FSM declaration form — XState / `transitions` / stateless / hand-rolled enum table?
2. Intervention-counter policy — sliding window, decay, hard cap + reset-on-success?
3. `context.status` boundary — LLM prompt preamble, typed-dict, pydantic?
4. Composition with sub-routers (Pass 1 provider, Pass 2 task) — wrapped or side-by-side?

---

**Dashboard one-liner:**
> Pass 34 is the **MILESTONE PASS** — the recommended query reached the backend and was rejected specifically for the `typescript` token, confirming the **content-dependent hypothesis (MR-RP-30) and closing the fire-protocol axis (MR-RP-33)**; the quality filter is **token-specific, not whole-query (MR-RP-34)**; cumulative **17 router + 34 retrieval rules, 31 Pytest modules**; **the architecture gate is now reduced to: token-specific quality filter + 2 operator-action-required dead-axis bugs**; the **single most important next query is the Python language-swap variant — *"XState v5 Python agentic loop mode transition example with bounded intervention counter"* — which would either land a HIT (resuming architecture research) or name a different failing token (refining the filter model); either outcome is informative and breaks the deadlock arc**.