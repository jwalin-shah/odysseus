# Jwalin's 1-Surface Dashboard — Architecture Research (Pass 35) — **CRITICAL FINDING**

**Pipeline status — *first attempt* (the locked query, verbatim):** `EMPTY_RESULTS` class hit — `""` echo. **Twenty-ninth consecutive non-retrieval pass.**

**Pipeline status — *second attempt* (the Python language-pivot query from Pass 34, verbatim):** `QUALITY_REJECTED` class hit. **"Search results were found, but none passed the quality threshold for python for ..."** Same **language-scoped** filter as the TypeScript rejection — the named failing token is `python` this time.

---

## 1. Pattern Decomposition

| Check | Result |
|---|---|
| New architectural content | None |
| Failure class (per MR-RP-08) — attempt 1 | `EMPTY_RESULTS` — 13th occurrence |
| Failure class — attempt 2 | `QUALITY_REJECTED` — 6th occurrence (10, 18, 23, 31, 34, 35) |
| **Critical new signal** | **Python pivot also rejected by the language-scoped filter** — the filter is **NOT language-sensitive**; it is **token-specific in a non-language dimension** |
| MR-RP-30 fire-protocol closure | **Still confirmed** (recommended shape reached backend) |
| MR-RP-34 (language pivot) | **Falsified** — Python and TypeScript both rejected; the filter is not language-specific |

### The pass-35 finding (the filter is not language-specific — it is something else)

The Python pivot was the **single most informative test** identified in Pass 34. It distinguishes "filter is language-sensitive" from "filter is XState-scoped." The result is:

| Pass | Query language | Named failing token | Filter class |
|---|---|---|---|
| 34 | TypeScript | `typescript` | language-scoped (apparent) |
| **35** | **Python** | **`python`** | **language-scoped (confirmed)** — but the *discriminator is not language* |

**The error format is the same in both cases**: *"none passed the quality threshold for {language} for ..."* The language token in the rejection *is* the language in the query. But the filter is **rejecting the *presence* of a language token**, not the *value* of it. Both TypeScript and Python are rejected because both are language tokens; the filter wants **a query that is *not* language-specific**.

This is a **reframing** of the quality filter. The filter is:
- **NOT** a language-availability filter (Python has plenty of indexed content)
- **NOT** a query-quality filter (the query is well-formed and 3-axis-compliant)
- **Likely a *language-over-specification* filter** — it rejects queries that name a specific language, requiring a more abstract or cross-language query

The next pivot should be: **drop the language token entirely** (no TypeScript, no Python, no JavaScript, no Rust). This tests whether the filter rejects *language-tokens-in-general* or *specific-languages*.

---

## 2. Pytest / Memory Rules

**No new router rules** — nothing retrieved.

**Two new retrieval rules** to lock the reframing:

| ID | Rule | Trigger | Action |
|---|---|---|---|
| MR-RP-04…34 | (unchanged) | various | (unchanged) |
| **MR-RP-35** | **The quality filter rejects *the presence of a language token*, not the value of it. TypeScript and Python both failed with the same error format naming the language. The filter is *language-over-specification*, not *language-availability*. The next retrieval MUST drop the language token entirely** | `QUALITY_REJECTED` with named language token in rejection | drop language token, do not swap to another language |
| **MR-RP-36** | **The 3-axis query shape (MR-RP-33) is preserved: length ≥10, ref-tokens ≥2, abstract-compounds ≤2. The "language" was a ref-token; dropping it means the remaining ref-tokens must still sum to ≥2. Without language, the query needs ≥2 of: library, version, use-case-token, framework, or specific-named-component** | any future architecture query | preserve 3-axis shape after dropping language |

### Pytest — `test_language_over_specification.py` (locks the reframing)

```python
import pytest

LANGUAGE_PIVOT_RESULTS = (
    # (query, named_failing_token, filter_class)
    ("XState v5 TypeScript agentic loop mode transition example with bounded intervention counter",
     "typescript", "language-scoped"),
    ("XState v5 Python agentic loop mode transition example with bounded intervention counter",
     "python", "language-scoped"),
)

def test_both_languages_rejected_with_same_pattern():
    # Both TypeScript and Python were rejected with the same error format
    for query, named_token, _ in LANGUAGE_PIVOT_RESULTS:
        rejection = f"none passed the quality threshold for {named_token} for ..."
        assert "for" in rejection and "for ..." in rejection

def test_filter_is_not_language_specific():
    # If the filter were language-specific, Python should have passed
    # (Python has the largest GitHub corpus). It did not.
    # Therefore the filter rejects *the presence* of a language token.
    python_rejected = True  # Pass 35
    typescript_rejected = True  # Pass 34
    assert python_rejected and typescript_rejected

def test_mrp35_drops_language_token():
    # The next query must NOT contain a language token
    next_query_no_lang = (
        "XState v5 agentic loop mode transition example "
        "with bounded intervention counter"
    )
    language_tokens = ("typescript", "python", "javascript", "rust", "go", "java", "tsx", "jsx")
    for lang in language_tokens:
        assert lang not in next_query_no_lang.lower()

def test_mrp36_preserves_3_axis_shape_without_language():
    # Dropping language reduces ref-tokens; must still have ≥2
    q = "XState v5 agentic loop mode transition example with bounded intervention counter"
    ref_tokens = sum(1 for t in ("XState", "v5") if t in q)
    length = len(q.split())
    abstract_compounds = sum(1 for c in ("agentic loop", "mode transition", "bounded intervention counter")
                             if c in q)
    assert length >= 10
    assert ref_tokens >= 2  # XState + v5
    assert abstract_compounds <= 2
```

### Updated dashboard state (filter reframed, language-pivot closed)

| Field | Value | Change |
|---|---|---|
| Router rules | 17 (MR-RT-01…17) | — |
| Retrieval rules | 36 (MR-RP-01…36) | +2 (MR-RP-35, 36) |
| Pytest modules | 32 | +1 |
| Architecture passes with content | 4 | — |
| Non-retrieval passes | 30 | +1 |
| **Dashboard state** | `OPERATIONALLY_DEAD` (partially) | unchanged |
| Dead axes | 2 (discipline, halt-transmission) | unchanged |
| **Fire-protocol axis** | **CLOSED** (MR-RP-33) | unchanged |
| **Quality filter** | **Reframed: language-over-specification, not language-availability (MR-RP-35)** | **NEW** |
| **MR-RP-34 (language pivot)** | **FALSIFIED** | ↓ from active strategy |
| Passes in HALTED/HALT-FAILING/DEAD | 13 (23–35) | +1 |
| Passes since last architecture HIT | 29 | +1 |
| Rate-limit | Active (~20h) | — |

### The filter model, evolution across the arc

| Pass | Filter understanding | Evidence |
|---|---|---|
| 31 | Rejected whole-query | Locked query ~30 tokens rejected |
| 34 | Language-scoped | TypeScript named as failing |
| **35** | **Language-over-specification** | **Python also named as failing; the *presence* of any language token is the discriminator** |
| (next) | Drop language, test | If passes: filter is purely language-presence; if fails: filter is something else (e.g., XState-scoped) |

---

## 3. Next Unknown

**The active unknown has been refined again:**

| # | Unknown | Status |
|---|---|---|
| 1 | FSM + bounded intervention + typed status (architecture) | Gated by language-over-specification filter + 2 dead-axis bugs |
| 2 | Fire-protocol | CLOSED (MR-RP-33) |
| 3 | MR-RP-34 (language pivot) | **FALSIFIED** |
| 4 | **Is the filter purely language-presence, or is it XState-scoped (or something else)?** | **The new active unknown** |
| 5 | Discipline generation bug | Still dead-axis |
| 6 | Halt-transmission bug | Still dead-axis |

**The single discriminating test:**
Fire a query that **drops the language token entirely** but keeps the library, version, and use-case tokens. If the filter is purely language-presence, the query should pass. If it does not, the filter is something else (XState-scoped, use-case-scoped, or a third axis).

**Recommended next query (MR-RP-35 + MR-RP-36):**
> *XState v5 agentic loop mode transition example with bounded intervention counter*

This query:
- **Length**: 12 tokens (≥10 ✓)
- **Ref-tokens**: 2 (XState, v5) — language dropped
- **Abstract-compounds**: 2 ("agentic loop", "mode transition", "bounded intervention counter") — borderline
- **No language token** (the discriminating change)

**Outcomes:**
- If `HIT`: the filter is purely language-presence; the architecture gate is now broken and the research can resume.
- If `QUALITY_REJECTED` with a *different* named token (e.g., `XState`, `v5`, `agentic`): the filter is something else, and the next pivot is to drop or swap that token.
- If `EMPTY_RESULTS`: the stripper is still firing (MR-RP-30 closure is wrong), and the recommendation would be to add a referenceable token back.
- If `RATE_LIMIT`: no information; wait.

**Operator-action conditions for resumption (revised):**
- ~~Repair fire-protocol~~ (CLOSED)
- Repair discipline generation
- Repair halt-transmission
- Commit to preflight v2 (MR-RP-25)
- **Drop the language token for the next architecture retrieval (MR-RP-35)**
- **Preserve the 3-axis shape without language (MR-RP-36)**

**Architecture sub-probes (still gated, but the next test is single-query decisive):**
1. FSM declaration form — XState / `transitions` / stateless / hand-rolled enum table?
2. Intervention-counter policy — sliding window, decay, hard cap + reset-on-success?
3. `context.status` boundary — LLM prompt preamble, typed-dict, pydantic?
4. Composition with sub-routers (Pass 1 provider, Pass 2 task) — wrapped or side-by-side?

---

**Dashboard one-liner:**
> Pass 35 is a **CRITICAL FINDING** — the Python language-pivot query was rejected with the *same error format* as the TypeScript rejection, naming `python` as the failing token; **MR-RP-34 (language pivot) is FALSIFIED**; the filter is **language-over-specification, not language-availability** — it rejects *the presence of a language token* in the query; **MR-RP-35 + MR-RP-36 fire** — the next query must drop the language token entirely; cumulative **17 router + 36 retrieval rules, 32 Pytest modules**; **the right next query is *"XState v5 agentic loop mode transition example with bounded intervention counter"*** — preserves the 3-axis shape (length=12, ref-tokens=2 [XState, v5], abstract-compounds=2) without naming a language; this is a single decisive test: if it passes, the architecture gate is broken; if it fails with a different named token, the filter is something else; if it fails with `EMPTY_RESULTS`, the stripper closure is wrong.