# 1-Surface Dashboard — orchestrator-mvp / 2026-06-11

> **Headline:** Brief 6's "keep forever" retention ships without a NER layer, without per-importer redaction profiles, and without a fixture proving the deny-regex catches anything beyond credentials. The corpus is the flywheel. The flywheel is poisoned if the redaction floor is "best-effort." **The PII layer is the gate.**

---

## 1. Pattern Decomposition

### 1.1 The corpus is the flywheel's fuel; the redaction floor is its only filter
North Star §3 makes the chain explicit: capture → exchanges.jsonl → pioneer-adaption datasets → evals → a model that learns from the corpus. Brief 6's redaction spec is exactly one deny-regex + key-prefix stripping. That regex catches credentials (`sk-...`, `AKIA...`, `password: ...`). It does **not** catch:
- Names (`Jwalin Shah`, `Jwalin`, in prose or quoted text)
- Email addresses
- Phone numbers (US, intl, paren formats)
- File paths (`/Users/jwalin/projects/...`)
- IP addresses, MAC addresses, IBANs, credit cards, SSNs
- Anything that doesn't look like a credential

For high-tier importers (chat, email, notes, free-form prompts), the deny-regex is a **credential-only filter**, not a PII filter. The "best-effort" framing in §6.1 of the Brief is the team's own admission that this is insufficient.

### 1.2 Per-importer heterogeneity makes "one size" wrong
The 28 importers split into at least three tiers by source-of-data:
- 🔴 **High** — raw user input: chat, email, notes, free-form prompt
- 🟡 **Medium** — system-derived, may contain names: summaries, agent loops, research, code review comments
- 🟢 **Low** — synthetic/code: schema generation, classification, code generation, parse tasks

A high-tier importer needs NER + email + phone + path redaction. A low-tier importer needs only the deny-regex. Without per-importer profiles, the system either over-redacts (hurts training signal) or under-redacts (PII leak).

### 1.3 Test fixtures are the only falsifiable check
A redaction test that asserts "no `sk-` tokens" passes today and tells you nothing about real PII. The fixtures must inject **synthetic PII** through each importer's payload shape and assert that the known-PII token does not survive `record_exchange`. Otherwise "best-effort" is a checkbox that passes vacuously.

### 1.4 Two architecture options
- **Option A: spaCy NER** — `en_core_web_trf` for person/org/loc + regex for email/phone/path/IP. ~50ms per call, high precision.
- **Option B: regex-and-skeleton hybrid** — no model, just regex library. ~1ms per call, lower precision, can miss names.

The trade-off is **latency vs coverage**. Since capture is on the hot path of every chat, summary, and research call, 50ms × 28 callers × 6-12 calls/min is non-trivial. But a regex that misses names is a privacy bug.

### 1.5 The chokepoint owns the contract
The 28 importers do not need to learn redaction. The chokepoint (`llm_call_async`) owns the contract. Per-importer profile lookup + tier-aware redaction at the chokepoint is the right place. The implementer miner consumes the corpus, so the corpus's PII surface IS the implementer's PII surface — making this gate even tighter.

---

## 2. Memory Rules

```yaml
- id: MR-OD-018
  rule: "record_exchange must apply tier-aware redaction. The tier is
         declared by the calling importer via a profile registered in
         core/redaction_profiles.json. Tier=high requires deny-regex +
         key-prefix strip + named-entity redaction (person, org, email,
         phone, path, IP). Tier=medium requires deny-regex + key-prefix
         + email/phone/path. Tier=low requires deny-regex + key-prefix
         only."
  source: "PII audit on 28 importers; Brief 6 'best-effort defense-in-depth'"
  severity: critical

- id: MR-OD-019
  rule: "The corpus retention policy ('keep forever') is gated on the
         tier-aware redaction test suite passing 100% on the synthetic
         PII fixture corpus. If any tier's redaction test fails, the
         retention is rolled back to 30 days max until the failure is
         fixed."
  source: "North Star §4 retention + §6.5 durability"
  severity: critical

- id: MR-OD-020
  rule: "The redaction floor (deny-regex + key-prefix) is the MINIMUM
         for every tier, including low. A regression in the deny-regex
         is a release blocker — credentials leaking is a worse failure
         mode than names leaking."
  source: "Brief 6 redaction spec + PII audit"
  severity: critical

- id: MR-OD-021
  rule: "route_code's subprocess path applies the same tier-aware
         redaction as the chokepoint. PII does not get a free pass
         through subprocesses."
  source: "Brief 6a route_code call site"
  severity: high

- id: MR-OD-022
  rule: "A new importer added to llm_call_async's callers without a
         profile in core/redaction_profiles.json is a CI failure. The
         chokepoint refuses to write and returns an in-band error."
  source: "Profile registry enforcement"
  severity: high

- id: MR-OD-023
  rule: "NER layer is spaCy en_core_web_trf for high-tier (person/org/
         loc). Regex for everything else (email/phone/path/IP/credit/SSN/
         IBAN/MAC). Latency budget: <50ms per call at high tier, <5ms
         at low tier. If latency exceeds, log a warning and fall back
         to deny-regex only — never skip capture."
  source: "Architecture decision: capture path is hot, latency matters"
  severity: high
```

---

## 3. Pytest files to add (concrete, copy-pasteable)

### 3.1 `tests/test_redaction_ner_layer.py`
```python
"""Tier-aware NER + regex redaction. Source: MR-OD-018, MR-OD-023."""
import json
from pathlib import Path
import re
import time
import pytest

PROFILES = Path("core/redaction_profiles.json")

# The synthetic PII corpus. Every fixture MUST be stripped at the tier
# that includes it. If a fixture leaks, the test fails and retention
# rolls back to 30 days (MR-OD-019).
PII_CORPUS = [
    # (description, raw, forbidden_tokens)
    ("name in prose",     "Hi, I'm Jwalin Shah from Acme.",        ["Jwalin", "Shah"]),
    ("name in quote",     '"From: Jwalin Shah <j@acme.com>"',      ["Jwalin", "Shah"]),
    ("email standard",    "send to jwalin.shah@acme.com",           ["jwalin.shah@acme.com"]),
    ("email plus-tag",    "jwalin+test@acme.com",                   ["jwalin+test@acme.com"]),
    ("phone us dash",     "call +1-555-0142",                       ["555-0142"]),
    ("phone paren",       "call (555) 014-2000",                    ["555) 014-2000"]),
    ("phone intl",        "tel +44 20 7946 0958",                   ["7946 0958"]),
    ("abs path",          "/Users/jwalin/projects/o/x.py",          ["/Users/jwalin"]),
    ("abs path with home","Edit /Users/jwalin/notes.md",            ["/Users/jwalin"]),
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
]


@pytest.fixture(scope="module")
def profiles():
    return json.loads(PROFILES.read_text())


@pytest.fixture(scope="module")
def high_tier_profile(profiles):
    high = [p for p in profiles.values() if p.get("tier") == "high"]
    if not high:
        pytest.skip("no high-tier profile in redaction_profiles.json")
    return high[0]


@pytest.fixture(scope="module")
def medium_tier_profile(profiles):
    medium = [p for p in profiles.values() if p.get("tier") == "medium"]
    if not medium:
        pytest.skip("no medium-tier profile")
    return medium[0]


@pytest.fixture(scope="module")
def low_tier_profile(profiles):
    low = [p for p in profiles.values() if p.get("tier") == "low"]
    if not low:
        pytest.skip("no low-tier profile")
    return low[0]


# ---------- High tier: all PII classes must be stripped ----------

@pytest.mark.parametrize("desc,raw,forbidden", PII_CORPUS,
                         ids=[c[0] for c in PII_CORPUS])
def test_high_tier_strips_every_pii_shape(desc, raw, forbidden,
                                          high_tier_profile):
    """High-tier importers must strip every PII class. A leak here means
    the corpus trains on PII. MR-OD-019: retention rolls back."""
    from core.redaction import apply_profile
    out = apply_profile(task=raw, response="ok", profile=high_tier_profile)
    for tok in forbidden:
        assert tok not in out["task"], (
            f"[{desc}] token {tok!r} leaked through HIGH-tier profile. "
            f"MR-OD-019 triggers retention rollback."
        )


# ---------- Medium tier: emails + creds + phone + path ----------

MEDIUM_TOKENS = [
    ("email", "ping jwalin@acme.com", ["jwalin@acme.com"]),
    ("api key", "sk-abc123 in env", ["sk-abc123"]),
    ("path", "/Users/jwalin/x.py", ["/Users/jwalin"]),
    ("phone", "call 555-0142", ["555-0142"]),
    ("iban", "iban GB29 NWBK", ["GB29 NWBK"]),
    ("credit", "4111 1111 1111 1111", ["4111 1111 1111 1111"]),
]

@pytest.mark.parametrize("desc,raw,forbidden", MEDIUM_TOKENS,
                         ids=[c[0] for c in MEDIUM_TOKENS])
def test_medium_tier_strips_creds_emails_phones_paths(desc, raw, forbidden,
                                                     medium_tier_profile):
    from core.redaction import apply_profile
    out = apply_profile(task=raw, response="ok", profile=medium_tier_profile)
    for tok in forbidden:
        assert tok not in out["task"], f"[{desc}] token {tok!r} leaked"


# ---------- Low tier: deny-regex + key-prefix only ----------

LOW_TOKENS = [
    ("api key kv", "sk-abc123 in env", ["sk-abc123"]),
    ("aws key", "AKIAIOSFODNN7EXAMPLE", ["AKIAIOSFODNN7EXAMPLE"]),
    ("bearer", "Bearer eyJhbGc", ["eyJhbGc"]),
    ("password kv", 'password: "hunter2"', ["hunter2"]),
]

@pytest.mark.parametrize("desc,raw,forbidden", LOW_TOKENS,
                         ids=[c[0] for c in LOW_TOKENS])
def test_low_tier_strips_creds_only(desc, raw, forbidden, low_tier_profile):
    from core.redaction import apply_profile
    out = apply_profile(task=raw, response="ok", profile=low_tier_profile)
    for tok in forbidden:
        assert tok not in out["task"], f"[{desc}] token {tok!r} leaked"


def test_low_tier_preserves_synthetic_code(low_tier_profile):
    """Low-tier (code/synthetic importers) must NOT over-redact.
    A regex that mangles source code is worse than no regex."""
    from core.redaction import apply_profile
    code = "def hello(name: str) -> int:\n    return 42"
    out = apply_profile(task=code, response="ok", profile=low_tier_profile)
    assert out["task"] == code, (
        f"low-tier mangled code: {out['task']!r}"
    )


def test_low_tier_preserves_fenced_code_block(low_tier_profile):
    """Markdown code fences must survive low-tier."""
    from core.redaction import apply_profile
    code = "```python\nname = 'Jwalin'\n```"
    out = apply_profile(task=code, response="ok", profile=low_tier_profile)
    assert "Jwalin" in out["task"] or "[" in out["task"]  # redacted or preserved per policy
    # Either preserved (low tier has no NER) or redacted with a marker — both acceptable
    # as long as the code is structurally intact.


# ---------- Latency budgets ----------

def test_high_tier_latency_under_budget(high_tier_profile):
    """MR-OD-023: high-tier NER must complete in <50ms per call."""
    from core.redaction import apply_profile
    payload = "My name is Jwalin Shah, email j@acme.com, call 555-0142. " * 5
    t0 = time.perf_counter()
    for _ in range(20):
        apply_profile(task=payload, response="ok", profile=high_tier_profile)
    elapsed = (time.perf_counter() - t0) / 20
    assert elapsed < 0.050, (
        f"High-tier redaction took {elapsed*1000:.1f}ms/call (budget 50ms). "
        f"MR-OD-023: fall back to deny-regex only, do not skip capture."
    )


def test_low_tier_latency_under_budget(low_tier_profile):
    """MR-OD-023: low-tier must complete in <5ms per call."""
    from core.redaction import apply_profile
    code = "def foo():\n    return 'hello world'\n" * 20
    t0 = time.perf_counter()
    for _ in range(100):
        apply_profile(task=code, response="ok", profile=low_tier_profile)
    elapsed = (time.perf_counter() - t0) / 100
    assert elapsed < 0.005, (
        f"Low-tier redaction took {elapsed*1000:.1f}ms/call (budget 5ms)"
    )


# ---------- Profile registry enforcement ----------

def test_every_known_importer_has_a_profile(profiles):
    """All 28 importers must be in the registry. MR-OD-022."""
    from src import llm_core
    callers = set()
    for path in (REPO := Path(__file__).resolve().parents[1]).rglob("*.py"):
        if path == REPO / "src" / "llm_core.py":
            continue
        if "llm_call_async" in path.read_text():
            callers.add(str(path.relative_to(REPO)))
    missing = [c for c in callers if c not in profiles]
    assert not missing, (
        f"Importers without a redaction profile: {missing}. "
        f"MR-OD-022: chokepoint refuses to write without a profile."
    )


def test_unknown_caller_refuses_to_capture(monkeypatch, tmp_path):
    """If an importer is added without a profile, the chokepoint refuses
    to capture and returns an in-band error. MR-OD-022."""
    from core.redaction import _PROFILES
    monkeypatch.setattr("core.redaction._PROFILES", {})
    from core.exchange_log import record_exchange
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", str(tmp_path))
    out = record_exchange(
        task="x", response="y", classification="chat",
        model_used="t", provider="t", tokens=1, latency_ms=1.0,
        caller="unknown_importer",
    )
    # Must signal an error (in-band), not raise, not write
    assert out is not None
    # And no file should have been written
    assert not list(tmp_path.rglob("*.jsonl"))


# ---------- End-to-end: chokepoint → record_exchange → no PII on disk ----------

def test_e2e_high_tier_payload_no_pii_on_disk(monkeypatch, tmp_path):
    """Inject high-tier PII into the chokepoint, assert nothing leaks to disk."""
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", str(tmp_path))
    from src.llm_core import llm_call_async  # adjust
    payload = "Jwalin Shah <j@acme.com> 555-0142 /Users/jwalin/x.py"
    llm_call_async(
        task=payload, response="ok", classification="chat",
        model_used="t", provider="t", tokens=1, latency_ms=1.0,
        caller="src/chat.py",  # high-tier
    )
    for fp in tmp_path.rglob("*"):
        if fp.is_file():
            content = fp.read_text()
            for forbidden in ("Jwalin", "j@acme.com", "555-0142", "/Users/jwalin"):
                assert forbidden not in content, (
                    f"PII {forbidden!r} leaked to disk at {fp}"
                )
```

### 3.2 `tests/test_redaction_profiles_registry.py`
```python
"""The profile registry is the contract. A regression here is a release
blocker. Source: MR-OD-018, MR-OD-022."""
import json
from pathlib import Path
import pytest

PROFILES = Path("core/redaction_profiles.json")

EXPECTED_MIN_IMPORTERS = 25  # 28 callers, allow 3 untiered

TIER_RULES = {
    "high":   {"name", "email", "phone", "path", "ip", "credit", "ssn",
               "iban", "mac", "api_key", "aws_key", "bearer", "password"},
    "medium": {"email", "phone", "path", "api_key", "aws_key", "bearer",
               "password", "credit", "iban"},
    "low":    {"api_key", "aws_key", "bearer", "password"},
}


def test_profiles_file_exists():
    assert PROFILES.exists(), (
        "core/redaction_profiles.json must exist. See MR-OD-018, MR-OD-022."
    )


def test_minimum_importer_coverage():
    profiles = json.loads(PROFILES.read_text())
    assert len(profiles) >= EXPECTED_MIN_IMPORTERS, (
        f"Only {len(profiles)} importers profiled. Need ≥{EXPECTED_MIN_IMPORTERS}."
    )


def test_each_profile_has_required_keys():
    profiles = json.loads(PROFILES.read_text())
    for caller, prof in profiles.items():
        assert "tier" in prof, f"{caller} missing 'tier'"
        assert prof["tier"] in ("high", "medium", "low")
        assert "redact" in prof, f"{caller} missing 'redact'"
        assert isinstance(prof["redact"], list)


def test_high_tier_covers_all_pii_classes():
    profiles = json.loads(PROFILES.read_text())
    for caller, prof in profiles.items():
        if prof["tier"] == "high":
            covered = set(prof["redact"])
            required = TIER_RULES["high"]
            missing = required - covered
            assert not missing, (
                f"{caller} tier=high missing PII classes: {missing}"
            )


def test_low_tier_does_not_overclaim():
    profiles = json.loads(PROFILES.read_text())
    for caller, prof in profiles.items():
        if prof["tier"] == "low":
            covered = set(prof["redact"])
            # Low tier MUST NOT claim name/path/email (those are tier=high
            # because they require NER / higher precision).
            overclaim = covered & {"name", "path", "email", "phone"}
            assert not overclaim, (
                f"{caller} tier=low claims classes {overclaim} — "
                f"these require NER and belong to high tier"
            )


def test_tier_assignment_has_pii_rationale():
    """A tier=high assignment must be justified. If the importer file
    doesn't have a PII keyword, the tier is wrong or the rationale is
    missing."""
    profiles = json.loads(PROFILES.read_text())
    PII_KEYWORDS = ("pii", "user input", "raw", "free-form",
                    "email", "notes", "personal", "human", "comment")
    for caller, prof in profiles.items():
        if prof["tier"] != "high":
            continue
        path = Path(caller)
        if not path.exists():
            continue
        src = path.read_text().lower()
        assert any(kw in src for kw in PII_KEYWORDS), (
            f"{caller} tier=high but no PII-rationale keyword in source. "
            f"Add a comment explaining why PII may flow through this importer."
        )
```

### 3.3 `tests/test_redaction_response_field_also_stripped.py`
```python
"""The redaction must apply to BOTH task and response fields. A test
that only checks task misses response-side leaks (LLM-generated PII
replay, e.g., an email-summarizer echoing the sender's name)."""
import json
from pathlib import Path
import pytest

PROFILES = Path("core/redaction_profiles.json")
PII_PROFILES = json.loads(PROFILES.read_text())


@pytest.mark.parametrize("tier", ["high", "medium"])
def test_response_field_redacted(tier):
    matches = [p for p in PII_PROFILES.values() if p.get("tier") == tier]
    if not matches:
        pytest.skip(f"no {tier}-tier profile")
    from core.redaction import apply_profile
    out = apply_profile(
        task="summarize this email",
        response="From: Jwalin Shah <j@acme.com>. Phone: 555-0142.",
        profile=matches[0],
    )
    for forbidden in ("Jwalin", "j@acme.com", "555-0142"):
        assert forbidden not in out["response"], (
            f"[{tier}] PII leaked via response field: {forbidden!r}"
        )
```

### 3.4 `tests/test_redaction_kill_switch_and_optout.py`
```python
"""The capture kill switch (ODYSSEUS_NO_CAPTURE) and per-request optout
(capture=False) must continue to work alongside the redaction layer."""
import json
import os
from pathlib import Path
import pytest
import unittest.mock as mock

PROFILES = Path("core/redaction_profiles.json")


def test_kill_switch_disables_capture_even_with_profiles(monkeypatch, tmp_path):
    monkeypatch.setenv("ODYSSEUS_NO_CAPTURE", "1")
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", str(tmp_path))
    from core.exchange_log import record_exchange
    with mock.patch("builtins.open", side_effect=AssertionError("written")):
        record_exchange(task="Jwalin", response="ok", classification="chat",
                        model_used="t", provider="t", tokens=1, latency_ms=1.0,
                        caller="src/chat.py")
    assert not list(tmp_path.rglob("*.jsonl"))


def test_per_request_capture_false_skips_redaction_and_write(monkeypatch, tmp_path):
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", str(tmp_path))
    from core.exchange_log import record_exchange
    with mock.patch("builtins.open", side_effect=AssertionError("written")):
        record_exchange(task="Jwalin", response="ok", classification="chat",
                        model_used="t", provider="t", tokens=1, latency_ms=1.0,
                        capture=False, caller="src/chat.py")


def test_redaction_failure_does_not_block_capture(monkeypatch, tmp_path):
    """If NER layer raises, fall back to deny-regex only — never block
    capture. MR-OD-023."""
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", str(tmp_path))
    from core import redaction
    # Force NER to raise
    monkeypatch.setattr(redaction, "ner_detect",
                        mock.Mock(side_effect=RuntimeError("spaCy crashed")))
    from core.exchange_log import record_exchange
    # Must not raise; must write (with deny-regex only)
    record_exchange(
        task="Jwalin 555-0142", response="ok", classification="chat",
        model_used="t", provider="t", tokens=1, latency_ms=1.0,
        caller="src/chat.py",
    )
    # File should exist
    files = list(tmp_path.rglob("*.jsonl"))
    assert files, "capture must not be blocked by redaction failure"
```

### 3.5 `tests/test_redaction_audit_replay.py`
```python
"""Historical audit: take a snapshot of exchanges.jsonl, run a PII
corpus scan, assert zero hits. This is the rollback check (MR-OD-019)."""
import json
from pathlib import Path
import re
import pytest

EXCHANGES = Path("data/orchestration/exchanges")


def test_exchanges_corpus_has_no_known_pii_shapes():
    """On every CI run, scan the live exchanges/ directory for PII.
    A hit = retention rollback per MR-OD-019."""
    if not EXCHANGES.exists():
        pytest.skip("no exchanges/ yet (Brief 6 not landed)")
    patterns = {
        "email":     re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "phone_us":  re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "abs_path":  re.compile(r"/Users/[A-Za-z0-9._-]+/"),
        "ipv4":      re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "credit":    re.compile(r"\b(?:\d[ -]?){13,16}\b"),
        "ssn":       re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "api_key":   re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        "aws":       re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    }
    hits = []
    for fp in EXCHANGES.rglob("*.jsonl"):
        for line_no, line in enumerate(fp.read_text().splitlines(), 1):
            for name, pat in patterns.items():
                if pat.search(line):
                    hits.append((str(fp), line_no, name, line[:120]))
    assert not hits, (
        f"exchanges/ contains PII-shaped tokens (MR-OD-019 trigger):\n"
        + "\n".join(f"  {f}:{ln} [{kind}] {snippet}..." for f, ln, kind, snippet in hits[:10])
    )
```

### 3.6 `tests/test_redaction_fixtures_corpus_size.py`
```python
"""The synthetic PII corpus must grow as the importer surface grows.
A 4-class high tier requires at least 3 shapes per class.
MR-OD-019: floor at 12 high-tier shapes; floor at 6 medium; floor at 4 low.
"""
import inspect
from pathlib import Path

from tests.test_redaction_ner_layer import PII_CORPUS, MEDIUM_TOKENS, LOW_TOKENS


def test_high_tier_corpus_floor():
    assert len(PII_CORPUS) >= 12, (
        f"High-tier corpus has {len(PII_CORPUS)} shapes; need ≥12 to cover "
        f"name/email/phone/path/IP/credit/SSN/IBAN/MAC/api/aws/bearer/password."
    )


def test_medium_tier_corpus_floor():
    assert len(MEDIUM_TOKENS) >= 6, (
        f"Medium-tier corpus has {len(MEDIUM_TOKENS)} shapes; need ≥6."
    )


def test_low_tier_corpus_floor():
    assert len(LOW_TOKENS) >= 4, (
        f"Low-tier corpus has {len(LOW_TOKENS)} shapes; need ≥4 "
        f"(api_key, aws_key, bearer, password)."
    )


def test_all_pii_classes_have_at_least_3_shapes():
    """If a class has only 1 fixture, the test can pass vacuously.
    Force ≥3 shapes per high-tier class."""
    by_class = {
        "name":   [],
        "email":  [],
        "phone":  [],
        "path":   [],
        "ip":     [],
        "credit": [],
        "ssn":    [],
        "iban":   [],
        "mac":    [],
        "cred":   [],
    }
    for desc, _, _ in PII_CORPUS:
        d = desc.lower()
        if "name" in d: by_class["name"].append(desc)
        if "email" in d: by_class["email"].append(desc)
        if "phone" in d: by_class["phone"].append(desc)
        if "path" in d: by_class["path"].append(desc)
        if "ip" in d: by_class["ip"].append(desc)
        if "credit" in d: by_class["credit"].append(desc)
        if "ssn" in d: by_class["ssn"].append(desc)
        if "iban" in d: by_class["iban"].append(desc)
        if "mac" in d: by_class["mac"].append(desc)
        if "key" in d or "bearer" in d or "password" in d: by_class["cred"].append(desc)
    under = {k: v for k, v in by_class.items() if len(v) < 3}
    assert not under, f"Classes with <3 shapes: {under}"
```

---

## 4. Next Unknown

**Which architecture — spaCy NER, regex-and-skeleton hybrid, or a two-tier layered approach — is best for the 28-importer chokepoint given the latency budget (50ms high / 5ms low) and the precision floor (zero leaks on the synthetic PII corpus)?**

**Why this and not the alternatives:**

| Candidate | Reason deferred |
|---|---|
| Cadence measurement (Brief 5 rollups) | Spec'd but unimplemented; the PII layer is a precondition — you can't roll up safely what isn't redacted |
| 5-router harvest inventory | Static `ls ~/projects`; not a security/privacy concern |
| Sandbox isolation choice | `bg-sandbox-architect` will surface from githits; team picks from data |
| Implementer gating | Mechanical; PII layer is a precondition for the implementer's safety |
| Pydantic Router spec | Blocked on Jwalin (#3958 "needs more info") |
| Per-model parameter table | Schema design; not an investigation |
| 28-importer PII audit | Now done; the output is the profile registry, not a research question |

**The architecture decision is the one unknown where:**
- Two real options exist (spaCy vs regex) with different precision/latency trade-offs
- The decision is *irreversible at scale* — switching later means re-processing the entire exchanges/ corpus
- The latency budget is real (50ms × 6-12 calls/min × 28 callers is non-trivial) and will block chat UX
- The precision floor is non-negotiable (zero PII in `keep forever` retention)

**Investigation plan:**

1. **Build both prototypes** as drop-in modules: `core/redaction_spacy.py` and `core/redaction_regex.py`, both conforming to `apply_profile(task, response, profile)`.
2. **Benchmark** on the synthetic PII corpus (the 21 fixtures in `test_redaction_ner_layer.py`):
   - **Precision**: % of forbidden tokens stripped per tier
   - **Recall**: % of fixtures where ALL forbidden tokens are stripped
   - **Latency**: p50/p95/p99 per call, separately for high and low tier
   - **Memory**: model load size for spaCy
3. **Build a "layered" prototype**: regex first (cheap), spaCy NER as fallback for high-tier only when regex confidence is low. This is the obvious production answer if spaCy is too slow.
4. **Decision matrix**:

| Approach | High-tier precision | High-tier latency | Low-tier latency | Memory |
|---|---|---|---|---|
| spaCy `en_core_web_trf` | High (95%+) | 50-100ms | 50-100ms (wasteful) | 500MB |
| spaCy `en_core_web_sm` | Medium (75-85%) | 5-15ms | 5-15ms | 50MB |
| Regex hybrid | Medium (60-70% for names) | <2ms | <1ms | <1MB |
| **Layered (regex + spaCy fallback)** | **High (90%+)** | **2-50ms (mostly fast path)** | **<1ms** | **<1MB unless fallback fires** |

5. **Recommendation**: the layered approach is the obvious production answer IF spaCy's small model passes the precision floor. If not, the regex hybrid is the floor and we accept that names will leak in long-prose chat — a known limitation, not a hidden bug.

6. **Outcome**: a `docs/redaction_architecture.md` doc with the decision, the benchmarks, and the production deployment. This is the spec for the implementation PR.

**Why this gates everything:** the profile registry (`core/redaction_profiles.json`) is useless without a backend that meets the precision and latency budgets. Without this decision, the registry is aspirational. With this decision, Brief 6's "keep forever" is defensible.

---

## 5. Dashboard Card (1-Surface)

```
┌──────────────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ 🔴 NER LAYER UNBUILT         │ 🟡 PROFILE REGISTRY          │ 🔴 RETENTION IS "FOREVER"   │
│ 28 importers, 0 PII filter   │ AWAITING FIRST COMMIT        │ but redaction is best-effort │
│ beyond deny-regex.           │ core/redaction_profiles.json │ without NER. Poisoned if     │
│ Latency budget: 50ms high.   │ is the contract. 28 entries. │ today's corpus trains a     │
│ [test_redaction_ner_          │ [test_redaction_profiles_     │ model that learns the leak. │
│  layer.py]                   │  registry.py]                │ [test_redaction_audit_      │
│                              │                              │  replay.py]                  │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 bg-implementer LOOSE      │ 🟡 auth-bypass = admin       │ 🟡 capture chokepoint        │
│ Reads 6 miners.              │ 2-line posture change,       │ 28 importers, 0 call sites. │
│ PII surface = corpus's.      │ no test.                     │ 1 raise = 28 regressions.    │
│ Untested.                    │ [test_auth_localhost_         │ [test_capture_at_             │
│ [test_implementer_miner_      │  bypass.py]                  │  chokepoint.py]              │
│  gating.py]                  │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 UNKNOWN: NER arch         │ 🟡 5 routers, no harvest     │ 🟢 Phase 3 (super-skills)  │
│ spaCy vs regex vs layered?   │ plan. Sixth-router temp-     │ listed, not landed.         │
│ Latency budget: 50ms high,   │ tation is real.              │ Repo map / auto-fix /        │
│ 5ms low. Decision gates      │ [grep-and-inventory]         │ Cline checklist.            │
│ retention policy.            │                              │                             │
└──────────────────────────────┴──────────────────────────────┴──────────────────────────────┘
🟢 aligned with North Star  🟡 spec'd but unverified  🔴 gap with no owner
```

**One-liner:** *The corpus trains a model. The redaction floor is "credentials only." A name in chat trains the model on the name. Build the NER layer or roll retention back from "keep forever" to 30 days — those are the only two honest options.*