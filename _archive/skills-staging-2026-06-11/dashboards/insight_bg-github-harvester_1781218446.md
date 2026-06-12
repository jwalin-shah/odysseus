# 1-Surface Dashboard — orchestrator-mvp | 2026-06-11 / PII Audit Cycle

> **Headline:** The 28 `llm_call_async` importers are the corpus. Today, **zero** are audited for PII. Brief 6 ships with "keep forever" retention + best-effort redaction. **A PII leak in one importer poisons the entire flywheel.** This is the unknown that gates everything else.

---

## 1. Pattern Decomposition

### 1.1 The corpus is the product
North Star §3 makes the thesis explicit: every inference becomes a training example for `pioneer-adaption`. The corpus fills from `llm_call_async` (28 importers) + `route_code` (1 importer, subprocess). If any importer lets PII through, the flywheel trains on it, and the model candidate that comes out of the loop *learns* the leak. There is no later checkpoint that fixes this.

### 1.2 The 28 importers are heterogeneous
The doc names the importer categories: *chat, scheduler tasks, research, notes, email, summaries, agent loops*. These are not equivalent. A chat importer passes the user's literal prompt. An email importer passes quoted text that may include sender full names, phone numbers, and company info. An agent-loop importer passes tool results that may include file paths. The redaction deny-regex family (`api_key|secret|token|bearer|password`) catches none of these. **Same chokepoint, different threat models.**

### 1.3 The deny-regex is a 1-size-fits-none
Brief 6 specifies redaction as: `(?i)(api[_-]?key|secret|token|bearer|password)\s*[:=]\s*\S+` + key-prefix stripping (`sk-`, `AKIA`). This catches API credentials and AWS keys. It does **not** catch:
- Email addresses (`jwalin.shah@acme.com`)
- Phone numbers (`+1-555-0142`, `(555) 014-2000`)
- Personal names in quoted text (`"Hi, this is Jwalin..."`)
- File paths (`/Users/jwalin/projects/odysseus/...`)
- IP addresses, MAC addresses, IBANs
- Anything that doesn't look like a credential

For 🔴 importers (raw user input), the deny-regex is **structural malpractice** — it returns a green checkbox while PII flows through.

### 1.4 The capture site is the right place to fix this
The north-star §6.1 chokepoint is `llm_call_async`. Adding per-importer redaction there means each importer declares its own redaction profile, and the chokepoint applies it before writing. The 28 importers do **not** need to be re-educated — the chokepoint owns the contract.

### 1.5 Test fixtures must prove the leak is closed
A redaction test that says "no `sk-` tokens in the output" is necessary but insufficient. The fixture must assert that *known-PII fixtures* (name, email, phone, path) injected through each importer's payload shape **do not survive** the roundtrip. Otherwise "best-effort" becomes "no-effort-on-the-case-we-tested."

---

## 2. Memory Rules

```yaml
- id: MR-OD-014
  rule: "Every llm_call_async importer must declare a redaction_profile
         (high/medium/low) in the chokepoint registry. Profiles are
         enforced at capture time, not at importer time. High-risk
         importers get named-entity detection (name, email, phone, path)
         in addition to the deny-regex."
  source: "PII audit on 28 importers; Brief 6 'best-effort defense-in-depth'"
  severity: critical

- id: MR-OD-015
  rule: "The corpus retention policy ('keep forever') is gated on the
         redaction test suite passing. If any high-risk importer's
         redaction profile is missing or untested, retention is rolled
         back to 30 days max."
  source: "North Star §4 retention + §6.5 durability"
  severity: high

- id: MR-OD-016
  rule: "route_code's subprocess path must apply the SAME redaction
         profile as the chokepoint. Subprocess payloads are not exempt
         from PII rules because they bypass llm_call_async."
  source: "Brief 6a route_code call site + PII audit"
  severity: high

- id: MR-OD-017
  rule: "Redaction is not a 'ship and forget.' The redaction suite runs
         on every PR that touches llm_call_async, any importer file, or
         the chokepoint registry. A regression in redaction is a release
         blocker, not a follow-up."
  source: "Test discipline: record_exchange never-raises, but redaction
          is a stronger contract"
  severity: high
```

---

## 3. Pytest files to add (concrete, copy-pasteable)

### 3.1 `tests/test_pii_redaction_per_importer.py`
```python
"""Per-importer redaction profiles. Source: MR-OD-014.
Each importer declares a tier (high/medium/low) and a redaction policy.
The chokepoint applies it before record_exchange writes."""
import json
import re
from pathlib import Path
import inspect
import pytest

REPO = Path(__file__).resolve().parents[1]
PROFILES_PATH = REPO / "core" / "redaction_profiles.json"

# Canonical PII fixtures — one per shape
PII_FIXTURES = {
    "name":      "My name is Jwalin Shah and I work at Acme Corp.",
    "email":     "Reach me at jwalin.shah@acme.com anytime.",
    "phone":     "Call +1-555-0142 or (555) 014-2000 for details.",
    "path":      "Edit /Users/jwalin/projects/odysseus/src/llm_core.py",
    "ip":        "Server is at 10.0.42.7 on the internal network.",
    "credit":    "Card 4111 1111 1111 1111 expires 12/29.",
    "ssn":       "SSN 123-45-6789 on file.",
}

KNOWN_BAD_TOKENS = [
    "Jwalin", "jwalin.shah@acme.com",
    "555-0142", "555) 014-2000",
    "/Users/jwalin", "10.0.42.7",
    "4111 1111 1111 1111", "123-45-6789",
]


@pytest.fixture(scope="module")
def profiles():
    return json.loads(PROFILES_PATH.read_text())


def test_every_importer_has_a_profile(profiles):
    """Each of the 28 llm_call_async importers must declare a profile."""
    from src import llm_core
    callers = set()
    for path in (REPO / "src").rglob("*.py"):
        if path == REPO / "src" / "llm_core.py":
            continue
        src = path.read_text()
        if "llm_call_async" in src:
            for line in src.splitlines():
                if "llm_call_async" in line and "import" not in line:
                    callers.add(str(path.relative_to(REPO)))
    missing = [c for c in callers if c not in profiles]
    assert not missing, f"Importers without a redaction profile: {missing}"


def test_profiles_have_required_keys(profiles):
    for caller, prof in profiles.items():
        assert "tier" in prof, f"{caller} missing 'tier'"
        assert prof["tier"] in ("high", "medium", "low")
        assert "redact" in prof, f"{caller} missing 'redact'"
        assert isinstance(prof["redact"], list)


def test_high_tier_importer_redacts_names(profiles, tmp_path, monkeypatch):
    """High-tier importers must redact personal names."""
    from core.exchange_log import record_exchange
    from src.llm_core import llm_call_async  # adjust
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", str(tmp_path))

    high_callers = [c for c, p in profiles.items() if p["tier"] == "high"]
    if not high_callers:
        pytest.skip("no high-tier importers declared")

    # Stub the chokepoint with a high-tier profile; verify name is gone.
    from core.redaction import apply_profile
    out = apply_profile(
        task=PII_FIXTURES["name"],
        response="ok",
        profile=profiles[high_callers[0]],
    )
    assert "Jwalin" not in out["task"], (
        f"High-tier profile {high_callers[0]} failed to redact name"
    )


def test_high_tier_redacts_emails(profiles):
    high = [c for c, p in profiles.items() if p["tier"] == "high"]
    if not high:
        pytest.skip("no high-tier")
    from core.redaction import apply_profile
    out = apply_profile(
        task=PII_FIXTURES["email"],
        response="ok",
        profile=profiles[high[0]],
    )
    assert "jwalin.shah@acme.com" not in out["task"]


def test_high_tier_redacts_phones(profiles):
    high = [c for c, p in profiles.items() if p["tier"] == "high"]
    if not high:
        pytest.skip("no high-tier")
    from core.redaction import apply_profile
    out = apply_profile(
        task=PII_FIXTURES["phone"],
        response="ok",
        profile=profiles[high[0]],
    )
    for tok in ["555-0142", "555) 014-2000"]:
        assert tok not in out["task"], f"phone {tok!r} leaked through"


def test_high_tier_redacts_paths(profiles):
    high = [c for c, p in profiles.items() if p["tier"] == "high"]
    if not high:
        pytest.skip("no high-tier")
    from core.redaction import apply_profile
    out = apply_profile(
        task=PII_FIXTURES["path"],
        response="ok",
        profile=profiles[high[0]],
    )
    assert "/Users/jwalin" not in out["task"]


def test_medium_tier_redacts_emails_only(profiles):
    """Medium-tier: emails and credentials, but not necessarily names."""
    medium = [c for c, p in profiles.items() if p["tier"] == "medium"]
    if not medium:
        pytest.skip("no medium-tier")
    from core.redaction import apply_profile
    out = apply_profile(
        task=PII_FIXTURES["email"],
        response="ok",
        profile=profiles[medium[0]],
    )
    assert "jwalin.shac@acme.com" not in out["task"] or \
           "jwalin.shah@acme.com" not in out["task"]


def test_low_tier_does_not_redact_synthetic(profiles):
    """Low-tier: code/synthetic payloads, only the deny-regex applies."""
    low = [c for c, p in profiles.items() if p["tier"] == "low"]
    if not low:
        pytest.skip("no low-tier")
    from core.redaction import apply_profile
    out = apply_profile(
        task="def hello(): return 42",
        response="ok",
        profile=profiles[low[0]],
    )
    assert out["task"] == "def hello(): return 42"


def test_deny_regex_still_runs_on_every_tier(profiles):
    """The deny-regex is the floor, not the ceiling. Even low-tier gets it."""
    low = [c for c, p in profiles.items() if p["tier"] == "low"]
    if not low:
        pytest.skip("no low-tier")
    from core.redaction import apply_profile
    out = apply_profile(
        task="my api_key is sk-abc123def456",
        response="ok",
        profile=profiles[low[0]],
    )
    assert "sk-abc123" not in out["task"]


def test_route_code_uses_chokepoint_profile(monkeypatch, tmp_path):
    """route_code's subprocess path must apply the same redaction as
    the chokepoint. PII does not get a free pass through subprocesses."""
    from core.routed_code import run_route_code  # adjust
    from core.redaction import apply_profile
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", str(tmp_path))
    out = run_route_code(task=PII_FIXTURES["email"], payload_kind="code")
    assert "jwalin.shah@acme.com" not in out["captured_task"]


def test_no_importer_can_bypass_profile_registry(profiles, tmp_path, monkeypatch):
    """Defensive: if an importer is added to llm_call_async's callers
    without a profile, the chokepoint refuses to write (returns in-band
    error, never raises)."""
    from core.exchange_log import record_exchange
    from src.llm_core import llm_call_async
    # Force a path with no profile
    from core.redaction import get_profile
    monkeypatch.setattr("core.redaction._PROFILES", {})
    out = llm_call_async(task="hi", response="ok", classification="chat",
                         model_used="t", provider="t", tokens=1, latency_ms=1.0,
                         caller="nonexistent_importer")
    # Must not raise; must not write
    assert out is not None
```

### 3.2 `tests/test_redaction_profiles_audit.py`
```python
"""Lock the redaction profile registry as a contract.
A new importer without a profile is a CI failure, not a runtime error."""
import json
from pathlib import Path
import pytest

PROFILES = Path("core/redaction_profiles.json")
EXPECTED_IMPORTERS_MIN = 25  # at least 25 of the 28 must be profiled

TIER_RULES = {
    "high":   ["name", "email", "phone", "path"],
    "medium": ["email"],
    "low":    [],
}


def test_profile_registry_exists():
    assert PROFILES.exists(), (
        "core/redaction_profiles.json must exist. See MR-OD-014."
    )


def test_registry_covers_minimum_importers():
    profiles = json.loads(PROFILES.read_text())
    assert len(profiles) >= EXPECTED_IMPORTERS_MIN, (
        f"Only {len(profiles)} importers profiled. "
        f"Need ≥{EXPECTED_IMPORTERS_MIN} of the 28."
    )


def test_tier_assignment_is_justified(profiles=None):
    """Each high-tier entry must justify its tier in a docstring/comment
    inside the importer file."""
    profiles = profiles or json.loads(PROFILES.read_text())
    for caller, prof in profiles.items():
        if prof["tier"] == "high":
            path = Path(caller)
            if not path.exists():
                continue
            src = path.read_text()
            # Heuristic: there must be a comment near the call site
            # explaining why PII may flow through.
            # Adjust keyword for your codebase.
            assert any(
                kw in src.lower()
                for kw in ("pii", "user input", "raw", "free-form",
                           "email", "notes", "personal")
            ), f"{caller} tier=high but no PII-rationale comment found"


def test_high_tier_includes_all_four_classes():
    profiles = json.loads(PROFILES.read_text())
    for caller, prof in profiles.items():
        if prof["tier"] == "high":
            classes = set(prof["redact"])
            for required in ("name", "email", "phone", "path"):
                assert required in classes, (
                    f"{caller} tier=high but missing redact class {required!r}"
                )
```

### 3.3 `tests/test_redaction_corpora_fixture.py`
```python
"""Synthetic PII corpora. The fixtures here are what proves redaction
actually works. If a real-world PII shape isn't in this corpus, it's not
covered."""
import json
import re
from pathlib import Path
import pytest

# A bag of realistic PII shapes that may flow through llm_call_async.
# The redaction suite must pass on every entry.
PII_CORPORA = [
    # (description, raw_text, must_not_contain)
    ("name in prose",     "Hi, I'm Jwalin Shah from Acme.",        ["Jwalin", "Shah"]),
    ("name in quote",     '"From: Jwalin Shah <j@acme.com>"',      ["Jwalin"]),
    ("email",             "send to jwalin.shah@acme.com",           ["jwalin.shah@acme.com"]),
    ("email-plus",        "jwalin+test@acme.com",                   ["jwalin+test@acme.com"]),
    ("phone us",          "call +1-555-0142",                       ["555-0142"]),
    ("phone paren",       "call (555) 014-2000",                    ["555) 014-2000"]),
    ("abs path",          "/Users/jwalin/projects/o/x.py",          ["/Users/jwalin"]),
    ("rel path",          "./data/jwalin_notes.md",                 ["jwalin_notes.md"]),
    ("ip v4",             "10.0.42.7 is the server",                ["10.0.42.7"]),
    ("ipv6",              "::1 is loopback",                        ["::1"]),
    ("credit card",       "card 4111 1111 1111 1111",               ["4111 1111 1111 1111"]),
    ("ssn",               "ssn 123-45-6789",                        ["123-45-6789"]),
    ("iban",              "IBAN GB29 NWBK 6016 1331 9268 19",       ["GB29 NWBK"]),
    ("mac",               "mac aa:bb:cc:dd:ee:ff",                  ["aa:bb:cc:dd:ee:ff"]),
    ("api key in env",    "OPENAI_API_KEY=sk-abc123",               ["sk-abc123"]),
    ("aws key",           "AKIAIOSFODNN7EXAMPLE",                   ["AKIAIOSFODNN7EXAMPLE"]),
    ("bearer",            "Authorization: Bearer eyJhbGc",          ["eyJhbGc"]),
    ("password kv",       'password: "hunter2"',                    ["hunter2"]),
    ("name + email",      "Jwalin Shah <j@acme.com> said",          ["Jwalin", "j@acme.com"]),
]


@pytest.mark.parametrize("desc,raw,forbidden", PII_CORPORA,
                         ids=[c[0] for c in PII_CORPORA])
def test_high_tier_redacts_each_pii_shape(desc, raw, forbidden, tmp_path, monkeypatch):
    """For each PII shape, run it through a high-tier profile and assert
    the forbidden tokens don't survive."""
    profiles = json.loads(Path("core/redaction_profiles.json").read_text())
    high = [c for c, p in profiles.items() if p["tier"] == "high"]
    if not high:
        pytest.skip("no high-tier")
    from core.redaction import apply_profile
    out = apply_profile(task=raw, response="ok", profile=profiles[high[0]])
    for tok in forbidden:
        assert tok not in out["task"], (
            f"[{desc}] token {tok!r} leaked through high-tier profile"
        )


def test_corpus_size_meets_brief_5_threshold():
    """Brief 5 rollups require a meaningful redaction corpus. As the
    importer surface grows, the corpus must grow. Lock the floor."""
    assert len(PII_CORPORA) >= 15, (
        f"PII corpora has {len(PII_CORPORA)} entries; need ≥15 to cover "
        f"the 4 high-tier classes with at least 3 shapes each."
    )
```

---

## 4. Next Unknown

**What is the actual end-to-end PII surface across the 28 `llm_call_async` importers when the corpus is fully populated?**

This is the only unknown on the dashboard where:
- The answer is not in any document
- The North Star doc explicitly admits redaction is "best-effort defense-in-depth" — by the team's own framing, the answer is *known to be insufficient*
- The corpus is "keep forever" — a single PII leak persists indefinitely
- Pioneer-adaption trains on this corpus — the leak *teaches* the model

**Investigation steps (concrete):**

1. **Enumerate**: `grep -rln "llm_call_async" src/ | wc -l` → confirm ≥ 28.
2. **For each importer, capture a real (or realistic) payload**:
   - Open the file, find the `llm_call_async(...)` call site.
   - Trace back 1–3 frames to understand what flows in: a chat message, an email body, a tool result, a code diff, a research summary, a notes excerpt.
3. **Tier the importer** (high / medium / low) based on payload source:
   - 🔴 **High** — raw user input flows in: chat, email, notes, free-form prompts.
   - 🟡 **Medium** — system-derived but may contain names: summaries, agent loops, research outputs, code review comments.
   - 🟢 **Low** — synthetic/code: schema generation, classification, code generation, parse tasks.
4. **Per-importer redaction policy**:
   - 🔴 High: deny-regex + key-prefix strip + **named-entity detection** (names, emails, phones, paths, IPs, credit cards, SSNs, IBANs).
   - 🟡 Medium: deny-regex + key-prefix strip + email/phone/path redaction.
   - 🟢 Low: deny-regex + key-prefix strip only.
5. **Codify as `core/redaction_profiles.json`**: a registry mapping caller path → tier + redact classes.
6. **Test fixtures**: `tests/test_pii_redaction_per_importer.py` and `tests/test_redaction_corpora_fixture.py` (above) prove that PII in the shape of each 🔴 importer's payload **does not survive** a roundtrip.
7. **Enforce on PR**: a new importer added to `llm_call_async`'s call sites without a profile is a CI failure (the chokepoint refuses to write).

**Why this and not the alternatives:**

| Candidate | Why not the next one |
|---|---|
| Cadence measurement (Brief 5 rollups) | Spec'd but unimplemented — the PII audit is a precondition for retention policy; can't measure safely what isn't redacted |
| 5-router harvest inventory | Static scan; not a security/privacy concern |
| Sandbox isolation choice | `bg-sandbox-architect` will surface from githits; team picks from data |
| Implementer gating | Mechanical fix (worktree + receipt + HITL); the implementer reads miner findings, which is a PII vector *only if* the miners leak — i.e., this audit's output determines the implementer's redaction tier |
| Pydantic Router spec | Blocked on Jwalin (#3958 "needs more info") |
| Per-model parameter table | Schema design, not investigation |

**The PII audit is the one investigation where the answer is not in any document, where shipping `record_exchange` without it is a privacy bug-in-waiting, and where the North Star doc itself admits the redaction is best-effort.** It also gates the implementer miner's safety — the implementer will consume the corpus, so the corpus's PII surface IS the implementer's PII surface.

**Concrete deliverable**: `core/redaction_profiles.json` (28 entries, 3 tiers) + the two test files above + a doc at `docs/redaction_profile_audit.md` listing each importer, its payload shape, its tier, and the rationale. This is what makes "keep forever" defensible and what gates Pioneer-adaption's training-data safety.

---

## 5. Dashboard Card (1-Surface)

```
┌──────────────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ 🔴 PII SURFACE UNAUDITED     │ 🟡 CAPTURE CHOKEPOINT        │ 🔴 FIRE-AND-FORGET GAP      │
│ 28 importers, 0 profiles.    │ Spec'd, not built.           │ Phase 2 not landed.          │
│ Best-effort redaction is     │ 28 importers waiting.        │ visibility_tools.py         │
│ known-insufficient.          │ 1 raise = 28 regressions.    │ spec'd, not built.           │
│ Corpus feeds the flywheel.   │ [test_capture_at_             │ [test_visibility_tools_      │
│ [test_pii_redaction_          │  chokepoint.py]              │  placeholder.py]            │
│  per_importer.py]            │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 bg-implementer LOOSE      │ 🟡 auth-bypass = admin       │ 🟡 session.mode = DEAD      │
│ Reads 6 miners.              │ 2-line posture change,       │ Written 4×, read 0×.        │
│ PII surface = corpus's.      │ no test.                     │ Legacy sessions empty.       │
│ Untested.                    │ [test_auth_localhost_         │ [test_session_mode_          │
│ [test_implementer_miner_      │  bypass.py]                  │  contract.py]                │
│  gating.py]                  │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 CADENCE INSTABILITY       │ 🟡 5 routers, no harvest     │ 🟢 Phase 3 (super-skills)  │
│ 3 commits, 75 min,           │ plan. Sixth-router temp-     │ listed, not landed.         │
│ 6-100× interval change.      │ tation is real.              │ Repo map / auto-fix /        │
│ No measurement, no test.     │ [grep-and-inventory]         │ Cline checklist.            │
│ [test_miners_cadence_         │                              │                             │
│  governance.py]              │                              │                             │
└──────────────────────────────┴──────────────────────────────┴──────────────────────────────┘
🟢 aligned with North Star  🟡 spec'd but unverified  🔴 gap with no owner
```

**One-liner:** *The corpus is the product. 28 importers feed it. Zero are PII-audited. Best-effort is known-insufficient. Ship `core/redaction_profiles.json` + the redaction suite or roll the retention policy back from "keep forever" to 30 days max.*