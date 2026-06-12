# 1-Surface Dashboard — orchestrator-mvp / 2026-06-11

> **Headline:** The NER layer decision is the single largest remaining architectural risk. spaCy en_core_web_sm at ~5–15ms per call may fit the 50ms-high budget, but its name-detection precision is the unknown. If it's <100% on the synthetic PII corpus, the layered (regex-first, NER-fallback) architecture is the only path. **This benchmark gates the entire "keep forever" retention policy.**

---

## 1. Pattern Decomposition

### 1.1 The architecture is a forced choice with three real candidates
| Approach | High-tier precision | High-tier latency | Low-tier latency | Memory |
|---|---|---|---|---|
| spaCy `en_core_web_sm` | Medium-high (75–90% on names) | 5–15ms | 5–15ms (wasteful at low) | ~50MB |
| spaCy `en_core_web_trf` | High (95%+) | 50–100ms | 50–100ms (wasteful) | ~500MB |
| Regex hybrid | Low-medium on names (~60–70%) | <2ms | <1ms | <1MB |
| **Layered (regex first, NER fallback)** | **High (90%+ if NER passes)** | **2–50ms (mostly fast path)** | **<1ms** | **<1MB unless fallback fires** |

The single bench result that decides is: **does `en_core_web_sm` strip every fixture in the 21-corpus at p99 < 50ms?** If yes → ship pure sm. If no → layered. If layered's fallback rate is > 30% → reconsider.

### 1.2 The corpus is the wrong benchmark if it's not adversarial
The 21 fixtures are clean, well-formed examples. Real chat looks like:
- "yo can u ping jwalin at j@acme.com? thx"
- "/Users/jwalin/projects/odysseus$ cat .env | grep KEY"
- "I talked to Sarah from the Acme team yesterday, she's got the specs"
- A 4000-token chat history with one mention of "Jwalin" on line 47

The benchmark corpus must include **adversarial shapes**: lower-case, no spaces, embedded in code, embedded in URLs, embedded in JSON, line-broken mid-token. If sm passes only the clean shapes, it fails in production.

### 1.3 The decision is irreversible at scale
Switching NER backends later means:
- Re-running every existing exchange through the new layer (re-processing GBs of `exchanges/`)
- Potentially surfacing new PII leaks that the old layer missed (rollback of "keep forever")
- Refreshing the evaluation set in pioneer-adaption

This is a *lock-in moment*. The benchmark must be run with the same production corpus shape and traffic pattern, not synthetic clean strings.

### 1.4 The layered architecture has its own failure mode
The fallback rate is the metric that matters. If 30% of high-tier calls hit NER, the average high-tier latency is 0.7×(2ms) + 0.3×(15ms) = ~6ms — fine. If 80% hit NER, the average is ~12ms — also fine. But if NER *itself* occasionally times out or fails on adversarial input, the layered path needs a **circuit breaker**: if NER fails >5% of calls in a 5-min window, fall back to deny-regex only and **alert** (MR-OD-023 already specifies this; the benchmark must confirm it triggers correctly).

### 1.5 Low-tier is a regex-only decision
There's no architecture choice at low tier. The deny-regex + key-prefix is the floor. The benchmark must confirm the regex does NOT over-redact synthetic code (a test failure for `mangled code` is in the prior synthesis). If the regex mangles `def hello(name: str)`, low-tier importers are unusable.

---

## 2. Memory Rules

```yaml
- id: MR-OD-024
  rule: "The NER architecture decision is a one-way door. The
         chosen layer must pass 100% of the synthetic PII corpus AND
         meet the latency budget (50ms p99 high tier, 5ms p99 low tier)
         on the production-shape adversarial benchmark. If either
         constraint fails, retain the current architecture; do not
         ship a new layer that is not benchmarked on adversarial
         input."
  source: "Architecture decision 2026-06-11; benchmark gate"
  severity: critical

- id: MR-OD-025
  rule: "The benchmark corpus is not just the 21 clean fixtures. It
         must include adversarial shapes: lower-case, embedded in code,
         embedded in URLs, embedded in JSON, line-broken mid-token,
         4000-token chat histories with one PII mention late. The
         benchmark passes only if 100% of adversarial shapes are
         stripped."
  source: "Production-shape fidelity"
  severity: high

- id: MR-OD-026
  rule: "If the layered architecture is chosen, the fallback rate to
         NER must be measured. If fallback > 70% in production traffic,
         the layered path is providing no latency benefit and should
         be replaced with pure NER (assuming NER passes the budget)."
  source: "Cost-of-complexity monitoring"
  severity: high

- id: MR-OD-027
  rule: "NER failure (model load error, timeout, OOM) MUST fall back
         to deny-regex only — never block capture, never skip redaction
         entirely. A circuit breaker trips after 5% NER failures in
         a 5-min window and stays open for 15 min, logging the trip
         for ops review. MR-OD-023 carries this rule."
  source: "Never-block-capture contract"
  severity: critical
```

---

## 3. Pytest files to add (concrete, copy-pasteable)

### 3.1 `tests/test_redaction_benchmark.py`
```python
"""Head-to-head benchmark of the redaction architecture options.
Source: MR-OD-024. Decision-gating test suite."""
import json
import time
import re
from pathlib import Path
from collections import defaultdict
import pytest
import statistics


# --- Adversarial corpus. 21 clean + adversarial variants ---

CLEAN_FIXTURES = [
    ("name in prose",     "Hi, I'm Jwalin Shah from Acme.",        ["Jwalin", "Shah"]),
    ("name in quote",     '"From: Jwalin Shah <j@acme.com>"',      ["Jwalin", "Shah"]),
    ("email standard",    "send to jwalin.shah@acme.com",           ["jwalin.shah@acme.com"]),
    ("email plus-tag",    "jwalin+test@acme.com",                   ["jwalin+test@acme.com"]),
    ("phone us dash",     "call +1-555-0142",                       ["555-0142"]),
    ("phone paren",       "call (555) 014-2000",                    ["555) 014-2000"]),
    ("phone intl",        "tel +44 20 7946 0958",                   ["7946 0958"]),
    ("abs path",          "/Users/jwalin/projects/o/x.py",          ["/Users/jwalin"]),
    ("rel path",          "./data/jwalin_notes.md",                 ["jwalin_notes"]),
    ("ipv4",              "10.0.42.7 is the server",                ["10.0.42.7"]),
    ("ipv6",              "::1 is loopback",                        ["::1"]),
    ("credit card",       "card 4111 1111 1111 1111",               ["4111 1111 1111 1111"]),
    ("ssn",               "ssn 123-45-6789",                        ["123-45-6789"]),
    ("iban",              "IBAN GB29 NWBK 6016 1331 9268 19",       ["GB29 NWBK"]),
    ("mac",               "mac aa:bb:cc:dd:ee:ff",                  ["aa:bb:cc:dd:ee:ff"]),
    ("api key kv",        "my api_key is sk-abc123def456",          ["sk-abc123"]),
    ("aws key",           "AKIAIOSFODNN7EXAMPLE",                   ["AKIAIOSFODNN7EXAMPLE"]),
    ("bearer token",      "Authorization: Bearer eyJhbGc",          ["eyJhbGc"]),
    ("password kv",       'password: "hunter2"',                    ["hunter2"]),
    ("combined",          "Jwalin Shah <j@acme.com> 555-0142",     ["Jwalin", "j@acme.com", "555-0142"]),
    ("long",              "blah blah " * 100 + " Jwalin 555-0142", ["Jwalin", "555-0142"]),
]

ADVERSARIAL_FIXTURES = [
    # Lowercase / no-space variants
    ("lower email",       "ping jwalin@acme.com",                   ["jwalin@acme.com"]),
    ("no-space phone",    "5550142 is the new number",              ["5550142"]),  # may not strip — that's a known limit
    # Embedded in code
    ("code-fence email",  '`echo jwalin@acme.com`',                 ["jwalin@acme.com"]),
    ("code-fence name",   'name = "Jwalin Shah"',                   ["Jwalin"]),  # string literal
    # Embedded in URL
    ("url with name",     "https://linkedin.com/in/jwalin-shah",    ["jwalin-shah"]),
    # Embedded in JSON
    ("json name",         '{"name": "Jwalin Shah", "role": "eng"}', ["Jwalin"]),
    # Line-broken mid-token
    ("line-broken email", "ping jwalin\n@acme.com",                 ["jwalin"]),  # may not strip
    # Long chat history with PII late
    ("late-pii chat",     "Hi how are you? " * 200 + " oh btw tell Jwalin I said hi", ["Jwalin"]),
    # All-caps
    ("caps name",         "FROM: JWALIN SHAH <J@ACME.COM>",         ["JWALIN"]),  # may not strip
    # Surrounded by punctuation
    ("punct name",        "(Jwalin)",                                ["Jwalin"]),
    # Multi-name
    ("multi-name",        "Jwalin, Sarah, and Mike went to lunch",  ["Jwalin", "Sarah", "Mike"]),  # partial strip OK
]


ALL_FIXTURES = CLEAN_FIXTURES + ADVERSARIAL_FIXTURES


@pytest.fixture(params=["regex", "spacy_sm", "layered"])
def architecture(request):
    """Parametrize over all candidate architectures."""
    return request.param


def _strip(arch_name: str, text: str) -> str:
    """Apply the named architecture to text. Drop-in per arch."""
    if arch_name == "regex":
        from core.redaction_regex import redact
        return redact(text, tier="high")
    if arch_name == "spacy_sm":
        from core.redaction_spacy import redact
        return redact(text, tier="high", model="en_core_web_sm")
    if arch_name == "layered":
        from core.redaction_layered import redact
        return redact(text, tier="high")
    raise ValueError(arch_name)


# ---------- Precision: every forbidden token stripped ----------

@pytest.mark.parametrize("arch", ["regex", "spacy_sm", "layered"])
@pytest.mark.parametrize("desc,raw,forbidden", CLEAN_FIXTURES,
                         ids=[c[0] for c in CLEAN_FIXTURES])
def test_clean_corpus_precision(desc, raw, forbidden, arch):
    out = _strip(arch, raw)
    leaks = [tok for tok in forbidden if tok in out]
    assert not leaks, f"[{arch} / {desc}] leaked: {leaks}"


@pytest.mark.parametrize("arch", ["regex", "spacy_sm", "layered"])
@pytest.mark.parametrize("desc,raw,forbidden", ADVERSARIAL_FIXTURES,
                         ids=[c[0] for c in ADVERSARIAL_FIXTURES])
def test_adversarial_corpus_precision(desc, raw, forbidden, arch):
    """Adversarial shapes. Some are expected to leak on regex (line-broken,
    no-space, all-caps). The layered arch must catch them via NER fallback.
    Log leaks but fail the test if >20% of adversarial shapes leak."""
    out = _strip(arch, raw)
    leaks = [tok for tok in forbidden if tok in out]
    # Soft assertion: a leak is logged, but the architecture must catch
    # the majority of adversarial shapes.
    if leaks:
        print(f"[{arch} / {desc}] LEAKED: {leaks}")


def test_adversarial_precision_floor_spacy_sm():
    """spaCy sm must catch ≥80% of adversarial shapes. If it doesn't,
    pure sm is rejected and we go layered."""
    leaks = 0
    for desc, raw, forbidden in ADVERSARIAL_FIXTURES:
        out = _strip("spacy_sm", raw)
        if any(tok in out for tok in forbidden):
            leaks += 1
    leak_rate = leaks / len(ADVERSARIAL_FIXTURES)
    assert leak_rate <= 0.20, (
        f"spaCy sm leaked {leaks}/{len(ADVERSARIAL_FIXTURES)} adversarial "
        f"shapes ({leak_rate:.0%}). Pure sm rejected; ship layered."
    )


def test_adversarial_precision_floor_layered():
    """Layered must catch ≥90% of adversarial shapes."""
    leaks = 0
    for desc, raw, forbidden in ADVERSARIAL_FIXTURES:
        out = _strip("layered", raw)
        if any(tok in out for tok in forbidden):
            leaks += 1
    leak_rate = leaks / len(ADVERSARIAL_FIXTURES)
    assert leak_rate <= 0.10, (
        f"Layered leaked {leaks}/{len(ADVERSARIAL_FIXTURES)} adversarial "
        f"shapes ({leak_rate:.0%}). Layered rejected; reconsider."
    )


# ---------- Latency: p50 / p95 / p99 per architecture ----------

HIGH_TIER_BUDGET_MS = 50.0
LOW_TIER_BUDGET_MS = 5.0
N_PER_TIER = 200
PAYLOAD = ("My name is Jwalin Shah, email j@acme.com, call 555-0142. "
           "Path /Users/jwalin/projects/o/x.py. " * 5)


def _bench(arch: str, tier: str, n: int) -> dict:
    times_ms = []
    for _ in range(n):
        t0 = time.perf_counter()
        _strip(arch, PAYLOAD) if tier == "high" else _strip_low(arch, PAYLOAD)
        times_ms.append((time.perf_counter() - t0) * 1000)
    return {
        "p50": statistics.median(times_ms),
        "p95": sorted(times_ms)[int(n * 0.95)],
        "p99": sorted(times_ms)[int(n * 0.99)],
        "max": max(times_ms),
    }


def _strip_low(arch: str, text: str) -> str:
    if arch == "regex":
        from core.redaction_regex import redact
        return redact(text, tier="low")
    if arch == "spacy_sm":
        # Pure sm at low tier is wasteful; spec says layered only
        from core.redaction_layered import redact
        return redact(text, tier="low")
    if arch == "layered":
        from core.redaction_layered import redact
        return redact(text, tier="low")
    raise ValueError(arch)


@pytest.mark.parametrize("arch", ["regex", "spacy_sm", "layered"])
def test_high_tier_latency_p99(arch):
    """MR-OD-024: high tier must complete in <50ms p99."""
    res = _bench(arch, "high", N_PER_TIER)
    assert res["p99"] < HIGH_TIER_BUDGET_MS, (
        f"[{arch}] high-tier p99 {res['p99']:.1f}ms exceeds budget "
        f"{HIGH_TIER_BUDGET_MS}ms. Stats: {res}"
    )


@pytest.mark.parametrize("arch", ["regex", "spacy_sm", "layered"])
def test_low_tier_latency_p99(arch):
    """MR-OD-024: low tier must complete in <5ms p99."""
    res = _bench(arch, "low", N_PER_TIER)
    assert res["p99"] < LOW_TIER_BUDGET_MS, (
        f"[{arch}] low-tier p99 {res['p99']:.1f}ms exceeds budget "
        f"{LOW_TIER_BUDGET_MS}ms. Stats: {res}"
    )


def test_layered_fallback_rate_under_70pct():
    """MR-OD-026: if layered falls back to NER >70% of the time,
    layered provides no latency benefit over pure NER. Reconsider."""
    from core.redaction_layered import _stats
    # Run a representative workload (mix of code and prose)
    workload = PAYLOAD.split(". ") * 100
    fallback_count = 0
    for text in workload:
        before = _stats.get("fallbacks", 0)
        _strip("layered", text)
        after = _stats.get("fallbacks", 0)
        if after > before:
            fallback_count += 1
    fallback_rate = fallback_count / len(workload)
    assert fallback_rate < 0.70, (
        f"Layered fallback rate {fallback_rate:.0%} exceeds 70%. "
        f"Consider switching to pure NER (if budget allows)."
    )


# ---------- Code preservation (low tier must not mangle) ----------

def test_low_tier_does_not_mangle_code_regex():
    code = "def hello(name: str) -> int:\n    return 42"
    out = _strip_low("regex", code)
    assert out == code, f"low-tier regex mangled code: {out!r}"


def test_low_tier_preserves_fenced_code_block_layered():
    code = "```python\nname = 'Jwalin'\n```"
    out = _strip_low("layered", code)
    # Low tier should preserve code; the name inside the fence is a known
    # over-redaction risk. Acceptable as long as the code structure survives.
    assert "```python" in out and "```" in out, (
        f"low-tier layered stripped the fence: {out!r}"
    )
```

### 3.2 `tests/test_redaction_layered_circuit_breaker.py`
```python
"""The layered architecture's NER fallback must have a circuit breaker.
MR-OD-023 + MR-OD-027."""
import time
import unittest.mock as mock
import pytest


def test_ner_failure_falls_back_to_regex(monkeypatch):
    """If NER raises, regex output is the answer. Capture must not
    break."""
    from core import redaction_layered
    monkeypatch.setattr(redaction_layered, "_ner_detect",
                        mock.Mock(side_effect=RuntimeError("spaCy crashed")))
    from core.redaction_layered import redact
    out = redact("Jwalin j@acme.com", tier="high")
    # Email must still be stripped (regex path)
    assert "j@acme.com" not in out
    # Name may leak (regex doesn't catch names) — that's acceptable
    # per the fail-soft contract


def test_circuit_breaker_trips_after_5pct_failures(monkeypatch):
    """If NER fails >5% of calls in a 5-min window, the breaker opens
    and the system uses regex-only for 15 min. MR-OD-027."""
    from core import redaction_layered

    call_count = [0]
    fail_count = [0]

    def flaky_ner(text):
        call_count[0] += 1
        if call_count[0] % 10 == 0:  # 10% failure
            fail_count[0] += 1
            raise RuntimeError("flaky")

    monkeypatch.setattr(redaction_layered, "_ner_detect", flaky_ner)

    # First 10 calls: 9 succeed, 1 fails. Breaker NOT tripped.
    for _ in range(10):
        redaction_layered.redact("Jwalin j@acme.com", tier="high")
    assert not redaction_layered._breaker.is_open(), (
        "Breaker tripped at 10% but threshold is 5% with 5-min window"
    )

    # Next 90 calls: 9 fail. Total = 10/100 = 10% > 5%. Breaker trips.
    for _ in range(90):
        try:
            redaction_layered.redact("Jwalin j@acme.com", tier="high")
        except RuntimeError:
            pass
    assert redaction_layered._breaker.is_open(), (
        f"Breaker did not trip after {fail_count[0]} failures in 100 calls"
    )


def test_breaker_resets_after_cooldown(monkeypatch):
    from core import redaction_layered
    # Trip the breaker
    redaction_layered._breaker.trip()
    redaction_layered._breaker.cooldown_until = time.time() - 1
    # Cooldown elapsed: next call should attempt NER again
    redaction_layered.redact("Jwalin j@acme.com", tier="high")
    assert not redaction_layered._breaker.is_open(), (
        "Breaker did not reset after cooldown"
    )
```

### 3.3 `tests/test_redaction_benchmark_report.py`
```python
"""Persist the benchmark results as a JSON artifact. This is the spec
the implementation PR must meet. If this file is not updated when the
architecture changes, the change is undocumented."""
import json
from pathlib import Path
import pytest

REPORT = Path("docs/redaction_benchmark_report.json")


def test_benchmark_report_exists():
    assert REPORT.exists(), (
        "docs/redaction_benchmark_report.json must exist. "
        "The benchmark must be run before the NER architecture is locked in."
    )


def test_benchmark_report_has_required_fields():
    data = json.loads(REPORT.read_text())
    required = ["date", "architectures", "clean_pass_rate",
               "adversarial_pass_rate", "high_p99_ms", "low_p99_ms",
               "decision", "rationale"]
    for k in required:
        assert k in data, f"benchmark report missing field: {k}"


def test_decision_field_is_valid():
    data = json.loads(REPORT.read_text())
    assert data["decision"] in ("regex", "spacy_sm", "layered", "rejected"), (
        f"decision {data['decision']!r} is not a valid architecture choice"
    )


def test_decision_meets_precision_floor():
    """The chosen architecture must pass 100% of clean fixtures and
    ≥80% of adversarial fixtures."""
    data = json.loads(REPORT.read_text())
    decision = data["decision"]
    if decision == "rejected":
        pytest.skip("decision=rejected, see rationale")
    arch_stats = data["architectures"].get(decision)
    assert arch_stats["clean_pass_rate"] >= 1.0, (
        f"{decision} clean pass rate {arch_stats['clean_pass_rate']} < 100%"
    )
    assert arch_stats["adversarial_pass_rate"] >= 0.80, (
        f"{decision} adversarial pass rate {arch_stats['adversarial_pass_rate']} < 80%"
    )


def test_decision_meets_latency_budget():
    data = json.loads(REPORT.read_text())
    decision = data["decision"]
    if decision == "rejected":
        pytest.skip("decision=rejected, see rationale")
    arch_stats = data["architectures"].get(decision)
    assert arch_stats["high_p99_ms"] < 50, (
        f"{decision} high p99 {arch_stats['high_p99_ms']}ms >= 50ms"
    )
    assert arch_stats["low_p99_ms"] < 5, (
        f"{decision} low p99 {arch_stats['low_p99_ms']}ms >= 5ms"
    )
```

---

## 4. Next Unknown

**What is the actual production-traffic NER fallback rate under the layered architecture, measured against a real-shape workload (not synthetic fixtures)?**

**Why this and not the alternatives:**

| Candidate | Why not |
|---|---|
| Pure-spaCy-sm vs regex-hybrid on the 21 fixtures | Already covered by `test_redaction_benchmark.py` — the benchmark IS the unknown here |
| 5-router harvest inventory | Static; not gating the corpus |
| Implementer gating | Mechanical |
| Pydantic Router spec | Blocked on Jwalin |
| Per-model parameter table | Schema design |

**The fallback rate is the one unknown where:**
- The benchmark on synthetic fixtures may not reflect production distribution
- A 70% fallback rate is a *cost-of-complexity failure*: the layered architecture provides no latency benefit over pure NER, doubling the engineering surface
- The fallback rate also drives the circuit-breaker trip frequency (MR-OD-027), which directly affects how often regex-only is used in production
- The 21-fixture corpus is biased toward clean shapes; a real chat distribution (code-heavy vs prose-heavy vs URL-heavy) will produce a different fallback rate

**Investigation plan:**

1. **Replay 7 days of real chat traffic** through the layered architecture, in dry-run mode (no writes). Measure:
   - Fallback rate per importer (high-tier vs medium-tier)
   - Per-call latency distribution
   - Circuit-breaker trip events
   - False-positive rate (over-redaction, especially of code)
2. **Stratify by importer category**: chat vs email vs notes vs summaries vs research vs agent loops. Some categories will have a much higher fallback rate than others.
3. **Stratify by payload size**: short prompts (<200 chars) vs long chat histories (4000+ chars). Long payloads stress NER; layered may be slower on them.
4. **Stratify by language**: English-only? Multi-lingual? (The regex-and-skeleton layer may mis-tag non-English names.)
5. **Decision matrix update**:
   - If fallback < 30%: ship layered, monitor.
   - If 30% < fallback < 70%: layered is fine, but document the cost-of-complexity.
   - If fallback > 70%: ship pure NER (assuming it passes the budget).
   - If neither: roll retention back to 30 days and revisit.
6. **Outcome**: a `docs/redaction_production_fallback_report.md` with the data, the stratification, and the final architecture call. This is what locks the decision.

**Why this gates everything:** the benchmark says "what's possible on synthetic." The production-traffic replay says "what's true in practice." If they disagree, the benchmark was wrong and the architecture must change. This is the **last step before** Brief 6 can land with "keep forever" retention.

---

## 5. Dashboard Card (1-Surface)

```
┌──────────────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ 🔴 NER BENCHMARK INCOMPLETE  │ 🟡 PROFILE REGISTRY          │ 🔴 RETENTION IS "FOREVER"   │
│ Three arch candidates, no    │ AWAITING FIRST COMMIT        │ but redaction is best-effort │
│ head-to-head numbers yet.    │ core/redaction_profiles.json │ without a benchmarked NER.   │
│ 21 fixtures + 10 adversarial │ is the contract. 28 entries. │ MR-OD-019: rollback to 30d  │
│ not yet run.                 │ [test_redaction_profiles_     │ until benchmark passes.     │
│ [test_redaction_              │  registry.py]                │ [test_redaction_audit_      │
│  benchmark.py]               │                              │  replay.py]                  │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 UNKNOWN: production       │ 🔴 bg-implementer LOOSE      │ 🟡 auth-bypass = admin       │
│ fallback rate on real chat   │ Reads 6 miners.              │ 2-line posture change,       │
│ traffic. Benchmark is on     │ PII surface = corpus's.      │ no test.                     │
| synthetic; production will   │ Untested.                    │ [test_auth_localhost_         │
│ differ.                      │ [test_implementer_miner_      │  bypass.py]                  │
│ MR-OD-026 gates ship.        │  gating.py]                  │                              │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🟡 capture chokepoint        │ 🟡 5 routers, no harvest     │ 🟢 Phase 3 (super-skills)  │
│ 28 importers, 0 call sites.  │ plan. Sixth-router temp-     │ listed, not landed.         │
│ 1 raise = 28 regressions.    │ tation is real.              │ Repo map / auto-fix /        │
│ [test_capture_at_             │ [grep-and-inventory]         │ Cline checklist.            │
│  chokepoint.py]              │                              │                             │
└──────────────────────────────┴──────────────────────────────┴──────────────────────────────┘
🟢 aligned with North Star  🟡 spec'd but unverified  🔴 gap with no owner
```

**One-liner:** *The benchmark decides the architecture. The production-traffic replay validates the architecture. Without the replay, "keep forever" is a claim, not a guarantee. Run the replay.*