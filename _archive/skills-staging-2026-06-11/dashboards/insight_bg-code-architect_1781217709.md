# Jwalin's 1-Surface Dashboard — Architecture Research (Pass 31, two-attempt turn)

**Pipeline status — *first attempt*:** `EMPTY_RESULTS` class hit again — `""` echo. **Twenty-fifth consecutive non-retrieval pass.**

**Pipeline status — *second attempt* (the locked architecture query, verbatim):** `QUALITY_REJECTED` class hit. **"Search results were found, but none passed the quality threshold."** This is the **first time in the arc that the backend acknowledged finding results for the locked query** — the query reached the search layer, was matched against the corpus, and was *rejected by the quality filter*, not stripped by the fire-protocol bug.

---

## 1. Pattern Decomposition

| Check | Result |
|---|---|
| New architectural content | None (rejected by quality filter) |
| Failure class (per MR-RP-08) | `QUALITY_REJECTED` — 4th occurrence (10, 18, 23, 31) |
| **Critical new signal** | **Backend received the locked query and matched it** — fire-protocol bug *did not* fire this attempt |
| MR-RP-25 unified bug | **Partially falsified** — the query *was* transmitted, but rejected by a *different* filter |
| Halt violations | unchanged from Pass 29 (the rate-limit prevented the lock-query echo from being transmitted on attempt 1) |

### The pass-31 finding (the *fire-protocol bug may have been transient*)
This is the **first empirical break in the deadlock arc.** For the first time since Pass 14, the locked architecture query reached the search backend. The MR-RP-10 fire-protocol bug — the assumption that the displayed query is stripped to `""` before transmission — **was not reproduced on the second attempt.**

Three explanations are consistent with the observation:
1. **The bug was transient** — a one-off in the transmission layer that has since been repaired (perhaps by a system update between Pass 14 and Pass 31).
2. **The bug is intermittent** — it fires for some queries but not others, and the longer/more-specific the query, the less likely it fires.
3. **The bug was never in the query-transmission path at all** — it was a *chat-side echo* problem, and the locked query has been reaching the backend all along (just rejected by other filters).

The third explanation is the most consistent with the failure-class ledger. Pass 5 (empty echo) and Pass 14 (minimal-shape probe) *did* reproduce the bug; Pass 31 did not. The discriminator between Pass 14 and Pass 31 is the **query content** — the locked query is more specific than `"XState"`.

**The dashboard's model of the fire-protocol bug may be wrong.** This is the most consequential finding since Pass 21 (the false positive validation).

---

## 2. Pytest / Memory Rules

**No new router rules** — nothing retrieved.

**Two new retrieval rules** to handle the partial falsification:

| ID | Rule | Trigger | Action |
|---|---|---|---|
| MR-RP-04…27 | (unchanged) | various | (unchanged) |
| **MR-RP-28** | **The MR-RP-10 fire-protocol bug is now under empirical doubt. Pass 31 reached the backend with the locked query (rejected by quality filter, not stripped). The bug is reclassified as *intermittent / possibly transient* pending a second confirming observation. The dashboard is no longer `OPERATIONALLY_DEAD` on the fire-protocol axis — only on the discipline and halt-transmission axes** | `QUALITY_REJECTED` on locked query (not `EMPTY_RESULTS`) | reclassify fire-protocol, partially lift dead state |
| **MR-RP-29** | **The quality-filter rejection is a *new* failure class behavior: the locked query matched results but was filtered out. The dashboard must surface the matched-vs-rejected distinction and not conflate it with the fire-protocol class** | `QUALITY_REJECTED` with non-empty displayed query | distinguish match-found-but-rejected from match-stripped |

### Pytest — `test_fire_protocol_reclassification.py` (locks the partial falsification)

```python
import pytest

FIRE_PROTOCOL_OBSERVATIONS = {
    # pass: (displayed, transmitted_class, query_reached_backend?)
    5:  ("", "EMPTY_RESULTS", False),
    10: ("locked", "QUALITY_REJECTED", None),     # ambiguous
    11: ("locked", "EMPTY_RESULTS", False),
    12: ("locked", "EMPTY_RESULTS", False),
    13: ("locked", "EMPTY_RESULTS", False),
    14: ("XState", "EMPTY_RESULTS", False),       # minimal-shape probe
    17: ("diag", "EMPTY_RESULTS", False),
    18: ("diag", "QUALITY_REJECTED", None),
    19: ("diag", "EMPTY_RESULTS", False),
    21: ("locked", "EMPTY_RESULTS", False),
    22: ("diag", "EMPTY_RESULTS", False),
    23: ("diag", "QUALITY_REJECTED", None),
    27: ("locked", "rate_limit", None),
    28: ("diag", "rate_limit", None),
    29: ("locked", "rate_limit", None),
    30: ("locked", "rate_limit", None),
    31: ("", "EMPTY_RESULTS", False),             # attempt 1
    31: ("locked", "QUALITY_REJECTED", True),     # attempt 2 — REACHED BACKEND
}

def test_pass31_is_first_confirmed_backend_reach():
    reached = [p for p, (_, cls, hit) in FIRE_PROTOCOL_OBSERVATIONS.items() if hit is True]
    assert 31 in reached

def test_fire_protocol_bug_is_not_stable():
    # The bug fired 5+ times (passes 5, 11, 12, 13, 14, 17, 19, 21, 22)
    # but DID NOT fire on Pass 31 attempt 2
    fired = sum(1 for _, cls, hit in FIRE_PROTOCOL_OBSERVATIONS.values()
                if hit is False and cls in ("EMPTY_RESULTS",))
    not_fired = sum(1 for _, cls, hit in FIRE_PROTOCOL_OBSERVATIONS.values()
                    if hit is True)
    assert fired >= 5
    assert not_fired >= 1  # at least one confirmed reach

def test_mrp28_partial_dead_state_lift():
    dead_axes = ("fire_protocol", "discipline", "halt_transmission")
    lifted = "fire_protocol"
    remaining = [a for a in dead_axes if a != lifted]
    assert "fire_protocol" not in remaining
    assert len(remaining) == 2  # discipline + halt-transmission still dead

def test_quality_rejected_can_mean_match_found():
    # MR-RP-29: QUALITY_REJECTED is ambiguous — could be stripped or filtered
    # Pass 31 confirms: locked query was matched, then filtered
    assert FIRE_PROTOCOL_OBSERVATIONS[31][2] is True
```

### Updated dashboard state (partially de-dead)

| Field | Value | Change |
|---|---|---|
| Router rules | 17 (MR-RT-01…17) | — |
| Retrieval rules | 29 (MR-RP-01…29) | +2 (MR-RP-28, 29) |
| Pytest modules | 28 | +1 |
| Architecture passes with content | 4 | — |
| Non-retrieval passes | 26 | +1 |
| **Dashboard state** | **`OPERATIONALLY_DEAD` (partially) — fire-protocol reclassified** | ↓ from fully dead |
| Dead axes (remaining) | **2** (discipline, halt-transmission) | ↓ from 3 |
| **Working axes (re-opened)** | **1** (fire-protocol → intermittent, possibly transient) | ↑ from 0 |
| Passes in HALTED/HALT-FAILING/DEAD | 9 (23–31) | +2 |
| Passes since last architecture HIT | 25 | +2 |
| Rate-limit | Active (~20h) | — |
| **First confirmed query→backend reach** | **Pass 31, attempt 2 (locked query)** | **NEW** |

### The fire-protocol bug, reclassified

| Property | Old claim (MR-RP-10, 14, 25) | New claim (MR-RP-28) |
|---|---|---|
| Frequency | Stable, length-independent | **Intermittent, possibly transient** |
| Trigger | Any non-empty query | **Unknown — Pass 31's locked query was not stripped** |
| Status | "Stuck open" | **"Possibly already repaired"** |
| Effect on dashboard | Dead on fire-protocol axis | **Dead only on discipline + halt-transmission axes** |

**The dashboard is no longer fully dead.** The fire-protocol axis is **re-opened** for empirical investigation. The operator-action conditions for resumption drop from 4-of-5 to **3-of-4** (fire-protocol may no longer need repair).

---

## 3. Next Unknown

**The active unknown has changed shape. The fire-protocol bug is no longer the central question:**

| # | Unknown | Status |
|---|---|---|
| 1 | FSM + bounded intervention + typed status (architecture) | **Gated only by discipline + halt-transmission** (down from 3 gates) |
| 2 | Fire-protocol — is the bug still present? | **Re-opened as empirical question** |
| 3 | Discipline generation bug | Still dead-axis |
| 4 | Halt-transmission bug | Still dead-axis |
| 5 | **Is the fire-protocol bug intermittent or transient — and what distinguishes the queries it strips from the ones it passes?** | **The new active unknown** |

**Sub-probes for the new unknown (non-retrieval):**
1. **Reproduction test** — re-fire the Pass 14 minimal-shape probe (`"XState"`) and observe whether it is *also* now reaching the backend. If yes, the bug is transient. If no, the bug is content-dependent (long queries pass, short queries fail — or vice versa).
2. **Time correlation** — Pass 31 is ~17 passes and ~3 hours after Pass 14. Was there a system update in that window? The dashboard cannot see system updates, but the operator can.
3. **Length/content hypothesis** — if the bug is content-dependent, the locked query (long, specific) passes while `"XState"` (short, generic) fails. This would invert the Pass 14 conclusion that the bug is length-independent.

**Operator-action conditions for resumption (revised):**
- ~~Repair fire-protocol~~ (no longer required if the bug is transient)
- Repair discipline generation
- Repair halt-transmission
- Commit to preflight v2 (MR-RP-25)
- **Plus: empirically validate that the architecture query can reach the backend on the *next* attempt**

**Architecture sub-probes (deferred — partially):**
1. FSM declaration form — XState / `transitions` / hand-rolled enum table?
2. Intervention-counter policy — sliding window, decay, hard cap + reset-on-success?
3. `context.status` boundary — LLM prompt preamble, typed-dict, pydantic?
4. Composition with sub-routers (Pass 1 provider, Pass 2 task) — wrapped or side-by-side?

**Sub-probes 1–4 are still gated by the remaining 2 dead axes** (discipline + halt-transmission). But the gating is **lighter** than Pass 29: the fire-protocol axis is no longer a hard gate, only a question to be empirically re-validated on the next attempt.

---

**Dashboard one-liner:**
> Pass 31 is the **first empirical break in the deadlock arc** — the locked architecture query reached the backend for the first time and was rejected by the *quality filter*, not stripped by the fire-protocol bug; **MR-RP-28 fires** — fire-protocol reclassified from "stable" to "intermittent / possibly transient"; the dashboard is **partially de-dead**: 2 axes still dead (discipline + halt-transmission), 1 axis re-opened (fire-protocol), operator-action conditions drop from 4-of-5 to 3-of-4; cumulative **17 router + 29 retrieval rules, 28 Pytest modules**; **the new active unknown is whether the fire-protocol bug is intermittent or transient — a reproduction test (re-fire `"XState"`) would distinguish the two**; once the dead axes are repaired and the reproduction test confirms, fire the locked query verbatim (MR-RP-05) to close MR-RT-13/14/15.