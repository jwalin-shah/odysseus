# 1-Surface Dashboard — orchestrator-mvp / 2026-06-11

> **Headline:** The 3-commit cadence oscillation in 75 minutes is the loudest signal in the corpus. Everything else (auth bypass, implementer miner, session.mode, api_key_env) is downstream of one root cause: **the team is shipping without a measurement loop**. Brief 5 is the missing primitive.

---

## 1. Pattern Decomposition

### 1.1 Cadence oscillation is a process regression
| Commit | bg-code | bg-test | bg-transcript | bg-memory | bg-job | new miners |
|---|---|---|---|---|---|---|
| `1dfa3f5` 12:46 | 14400s | 21600s | 7200s | 43200s | 21600s | — |
| `ee73ae3` 13:56 | 1800s | 1800s | 900s | 2700s | 2700s | — |
| `c510b31` 14:01 | **120s** | **120s** | **60s** | **180s** | **180s** | +sandbox, +implementer |

`bg-transcript-architect` at 60s will re-read `~/.pi/agent/sessions/` (~7.7 MB) 1,440×/day. The third commit's body (*"work time is the pacing"*) is philosophy, not measurement. The north-star doc itself demands *"Each loop iteration is measured by Brief 5 rollups"* — but Brief 5 doesn't exist yet. **This is tuning-by-vibes on a chokepoint that's supposed to feed the flywheel.**

### 1.2 The `bg-implementer` is a new class of problem
First miner with `source: "implementer"`, query *"implement the most actionable recent miner finding"*, at 120s. It reads the other 6 miners' outputs and writes code. The non-goals ban *"no training runs triggered by Odysseus"* and *"no swarm/mesh"* — but a miner that auto-implements its own findings is structurally adjacent to both. **No receipt per emitted change, no write-scope enforcement, no human-in-the-loop, no test.**

### 1.3 The 2-line auth change is a security posture change shipped as a diff
```python
if LOCALHOST_BYPASS and _is_trusted_loopback(request):
+   request.state.current_user = "admin"
+   request.state.api_token = False
    return await call_next(request)
```
No test fails closed if any future code reads `request.state.current_user` for authz and silently inherits admin. The comment warns about network-exposed deployments but provides no defensive test.

### 1.4 `llm_call_async` is the chokepoint, capture is not built
The doc is correct (§6.1) — `llm_call_async` is imported by **28 files**. The Brief 6 capture call sites don't exist yet. The chokepoint will be a 28-importer regression point the day capture lands: one raise in `record_exchange` = 28 callers lose inference.

### 1.5 `session.mode` and `api_key_env` are dead/undertested
- `mode: str = "chat"` written in 4 places, read in 0. No backfill.
- `api_key_env` precedence: env > encrypted > None — but 3 cases (env unset, both set, neither) are all undefined and untested.

### 1.6 Error-contract violations are clustering
Issues #3992, #3993, #3995, #3966, #3965 — all in-band error contract violations from `orchestration-briefs.md`. The contract is documented; the tests don't enforce it.

### 1.7 Spec/code ratio
- ~787 lines of new docs (`odysseus-north-star.md` 280 + `orchestration-briefs.md` 507) in 24h
- ~33 lines of executable code in same window
- North Star §6.6 acknowledges this: *"The single highest-value next action is no longer a document — it's merging Brief 1."*

---

## 2. Memory Rules

```yaml
- id: MR-OD-001
  rule: "Cadence changes to config/miners.json require a 'Measured:' or 'Rollup:'
         line in the commit body. Block merge otherwise."
  source: "3-commit oscillation 14400s→60s in 75min, 2026-06-11"
  severity: high

- id: MR-OD-002
  rule: "In-band error contract: /api/route and any dispatch surface must
         NEVER return 5xx. Bad body, timeout, missing CLI, stale quota →
         {error: true, response: <truncated>}."
  source: "orchestration-briefs.md + issues #3966, #3992, #3995"
  severity: critical

- id: MR-OD-003
  rule: "Capture site = llm_call_async (28 importers) PLUS route_code subprocess
         path. Both call sites updated together. Drift = corpus gaps."
  source: "odysseus-north-star.md §6.1"
  severity: high

- id: MR-OD-004
  rule: "bg-implementer must be disabled by default. When enabled, every write
         must be inside a git worktree, emit a receipt with pre/post diff hash,
         and require a human-in-the-loop approval token."
  source: "c510b31 new miner + North Star non-goals"
  severity: critical

- id: MR-OD-005
  rule: "LOCALHOST_BYPASS implies admin. Any code path setting
         request.state.current_user = 'admin' must be paired with a test
         asserting a non-loopback request returns 401/403, never 200."
  source: "1dfa3f5 app.py diff"
  severity: critical

- id: MR-OD-006
  rule: "session.mode requires a consumer in the same PR. Adding the field
         with no reader is dead data with migration cost."
  source: "1dfa3f5 models.py/session_manager.py"
  severity: medium

- id: MR-OD-007
  rule: "api_key_env precedence: env var > encrypted column > None. Unset env
         falls through silently to DB. Both unset returns None and triggers an
         in-band error (never 500). All three cases need tests."
  source: "core/database.py _migrate_add_api_key_env_column"
  severity: high

- id: MR-OD-008
  rule: "Five overlapping routers exist. Before proposing a new router, grep
         for these and write 'why this is not a sixth router' in the PR."
  source: "odysseus-north-star.md §2"
  severity: medium

- id: MR-OD-009
  rule: "Pydantic Router (#3958) must wrap, not replace, classify_task. The
         regex-first contract is global and non-negotiable."
  source: "orchestration-briefs.md + #3958"
  severity: medium

- id: MR-OD-010
  rule: "Online Skill Sharing (#3974) conflicts with non-goal 'no cloud sync
         of exchanges or transcripts.' Default-reject or LAN/mDNS only."
  source: "North Star non-goals + #3974"
  severity: medium
```

---

## 3. Pytest files to add

### 3.1 `tests/test_miners_cadence_governance.py`
```python
"""Lock the cadence tuning loop. Cadence changes without measurement are a
process regression. Source: synthesis 2026-06-11."""
import json, re, subprocess
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]
CFG = REPO / "config" / "miners.json"
MIN_S, MAX_S = 30, 86_400
ALLOWED = {"name", "query", "interval_seconds", "source", "enabled"}

def _cfg(): return json.loads(CFG.read_text())

def test_intervals_within_hard_bounds():
    for m in _cfg():
        assert MIN_S <= m["interval_seconds"] <= MAX_S, m["name"]

def test_miner_names_unique_and_fields_known():
    names = [m["name"] for m in _cfg()]
    assert len(names) == len(set(names))
    for m in _cfg():
        assert not (set(m) - ALLOWED), m["name"]

def test_transcript_miner_not_tighter_than_githits_default():
    cfg = {m["name"]: m for m in _cfg()}
    t = cfg.get("bg-transcript-architect")
    c = cfg.get("bg-code-architect")
    if t and c:
        assert t["interval_seconds"] >= c["interval_seconds"]

def test_cadence_change_cites_measurement():
    """Block vibes-cadence. If config/miners.json changed in HEAD, the
    commit body must cite a measurement (Measured:/Rollup:/Brief-5/Baseline).
    This is the MR-OD-001 enforcement gate."""
    diff = subprocess.run(
        ["git", "diff", "--stat", "HEAD~1", "--", "config/miners.json"],
        cwd=REPO, capture_output=True, text=True,
    )
    if "miners.json" not in diff.stdout:
        pytest.skip("no diff against HEAD~1")
    msg = subprocess.check_output(
        ["git", "log", "-1", "--format=%b", "--", "config/miners.json"],
        cwd=REPO, text=True,
    )
    assert re.search(r"(?i)(measured|rollup|brief[- ]?5|baseline)", msg), (
        "Cadence change requires 'Measured:'/'Rollup:' citation. See MR-OD-001."
    )
```

### 3.2 `tests/test_router_never_500.py`
```python
"""In-band error contract: dispatch surfaces must never 5xx."""
import pytest
from fastapi.testclient import TestClient
from app import app

c = TestClient(app)

DISPATCH = [
    ("post", "/api/route",          {"task": "hello"}),
    ("post", "/api/route",          {}),
    ("post", "/api/route",          {"task": "x" * 1_000_000}),
    ("post", "/api/route/code",     {"task": "ls"}),
    ("post", "/api/route/research", {"task": "x"}),
]

@pytest.mark.parametrize("method,path,body", DISPATCH)
def test_dispatch_never_5xx(method, path, body):
    r = getattr(c, method)(path, json=body)
    assert r.status_code < 500, f"{method} {path} → {r.status_code}: {r.text[:300]}"
    if r.status_code == 200 and not body.get("task"):
        assert r.json().get("error") is True

def test_api_token_patch_rejects_non_object():
    """#3966: PATCH must not 500 on non-object JSON body."""
    for bad in ([], "string", 42, None):
        r = c.patch("/api/auth/tokens/x", json=bad)
        assert r.status_code < 500
```

### 3.3 `tests/test_capture_at_chokepoint.py`
```python
"""Brief 6 amendment: capture in llm_call_async, not just the router.
28 importers > 1 importer."""
import ast
import inspect
from pathlib import Path
import unittest.mock as mock
import pytest

REPO = Path(__file__).resolve().parents[1]
LLM_CORE = REPO / "src" / "llm_core.py"
ROUTER = REPO / "core" / "router.py"


def test_chokepoint_calls_record_exchange():
    src = LLM_CORE.read_text()
    tree = ast.parse(src)
    found = any(
        isinstance(n, ast.Call) and (
            getattr(n.func, "id", "") == "record_exchange"
            or getattr(n.func, "attr", "") == "record_exchange"
        )
        for n in ast.walk(tree)
    )
    assert found, "src/llm_core.py must call record_exchange — Brief 6 amendment."


def test_router_subprocess_path_also_captures():
    assert "record_exchange" in ROUTER.read_text(), (
        "core/router.py route_code subprocess path must call record_exchange"
    )


def test_capture_never_raises(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", "/dev/full/exchanges")
    from core.exchange_log import record_exchange
    record_exchange(task="x", response="y", classification="chat",
                    model_used="t", provider="t", tokens=1, latency_ms=1.0)


def test_per_request_optout_skips_write(monkeypatch):
    from core.exchange_log import record_exchange
    with mock.patch("builtins.open", side_effect=AssertionError("written")):
        record_exchange(task="x", response="y", capture=False)


def test_kill_switch_env(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_NO_CAPTURE", "1")
    from core.exchange_log import record_exchange
    with mock.patch("builtins.open", side_effect=AssertionError("written")):
        record_exchange(task="x", response="y")
```

### 3.4 `tests/test_auth_localhost_bypass.py`
```python
"""LOCALHOST_BYPASS grants admin. Non-loopback must NOT inherit."""
import pytest
from fastapi.testclient import TestClient
from app import app

c = TestClient(app)


def test_non_loopback_does_not_get_admin(monkeypatch):
    monkeypatch.setenv("LOCALHOST_BYPASS", "true")
    r = c.get("/api/admin/anything", headers={"Host": "evil.example.com"})
    if r.status_code == 200:
        assert r.json().get("current_user") != "admin", (
            "Non-loopback request granted admin via LOCALHOST_BYPASS"
        )


def test_loopback_does_get_admin(monkeypatch):
    monkeypatch.setenv("LOCALHOST_BYPASS", "true")
    r = c.get("/api/whoami", headers={"Host": "127.0.0.1:8000"})
    assert r.status_code == 200
    assert r.json().get("current_user") == "admin"


def test_admin_endpoint_rejects_without_auth(monkeypatch):
    monkeypatch.setenv("LOCALHOST_BYPASS", "false")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    r = c.get("/api/admin/anything")
    assert r.status_code in (401, 302, 303, 307), r.status_code
```

### 3.5 `tests/test_implementer_miner_gating.py`
```python
"""bg-implementer is self-modifying. Must be gated by worktree + receipt +
HITL. Source: c510b31 + North Star non-goals."""
import json
from pathlib import Path
import pytest

CFG = Path("config/miners.json")


def _cfg(): return json.loads(CFG.read_text())


def test_implementer_disabled_by_default():
    cfg = {m["name"]: m for m in _cfg()}
    impl = cfg.get("bg-implementer")
    if impl is None:
        pytest.skip("bg-implementer not configured")
    assert impl["enabled"] is False, (
        "bg-implementer must be disabled until write-scope, receipt, and "
        "human-in-the-loop gating ship together."
    )


def test_implementer_writes_only_to_worktree():
    cfg = {m["name"]: m for m in _cfg()}
    impl = cfg.get("bg-implementer")
    if impl is None or not impl.get("enabled"):
        pytest.skip("not enabled")
    for p in impl.get("write_paths", []):
        assert ".worktrees/" in p or "/tmp/" in p, (
            f"implementer write path {p!r} is not a worktree or scratch dir"
        )
```

### 3.6 `tests/test_api_key_env_precedence.py`
```python
"""Codify the precedence env > encrypted > None. Three cases otherwise
undefined. Source: 1dfa3f5 database.py migration."""
import pytest
from core.models import ModelEndpoint
from core.endpoint_resolver import resolve_api_key  # adjust


def test_env_var_wins(monkeypatch):
    monkeypatch.setenv("MY_KEY", "sk-env")
    ep = ModelEndpoint(api_key="sk-db", api_key_env="MY_KEY")
    assert resolve_api_key(ep) == "sk-env"


def test_env_unset_falls_back_to_db(monkeypatch):
    monkeypatch.delenv("MISSING", raising=False)
    ep = ModelEndpoint(api_key="sk-db", api_key_env="MISSING")
    assert resolve_api_key(ep) == "sk-db"


def test_neither_returns_none(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    ep = ModelEndpoint(api_key=None, api_key_env="NOPE")
    assert resolve_api_key(ep) is None
```

### 3.7 `tests/test_subprocess_lifecycle.py`
```python
"""#3995: orphaned hf/python processes. Worktree isolation is not enough —
need process-group reap."""
import time
import psutil
import pytest
from core.router import route_code  # adjust


def test_route_code_reaps_descendants_on_timeout(tmp_path):
    before = {p.pid for p in psutil.process_iter(["name"])
              if "python" in (p.info.get("name") or "").lower()}
    with pytest.raises(Exception):
        route_code(task="sleep 60", cwd=tmp_path, timeout=2)
    time.sleep(2)
    after = {p.pid for p in psutil.process_iter(["name"])
             if "python" in (p.info.get("name") or "").lower()}
    assert not (after - before), f"orphaned python pids: {after - before}"


def test_subprocess_uses_process_group():
    from core import router
    src = inspect.getsource(router)
    assert "setsid" in src or "start_new_session" in src, (
        "subprocess path must use setsid/start_new_session for clean teardown"
    )
```

### 3.8 `tests/test_pydantic_router_compat.py`
```python
"""MR-OD-009: Pydantic Router (#3958) must wrap, not replace,
the regex-first classifier."""
import pytest
from core.router import classify_task


def test_regex_first_does_not_call_llm_for_clear_code(monkeypatch):
    called = []
    monkeypatch.setattr(
        "core.router._cheap_llm_classify",
        lambda *a, **k: called.append(1) or "code",
    )
    assert classify_task("Write a Python function to parse JSON") == "code"
    assert not called


def test_async_tiebreak_only_on_ambiguous(monkeypatch):
    called = []
    monkeypatch.setattr(
        "core.router._cheap_llm_classify",
        lambda *a, **k: called.append(1) or "chat",
    )
    monkeypatch.setattr("core.router._is_ambiguous", lambda t: "maybe" in t)
    classify_task("hello there")
    classify_task("maybe do something")
    assert len(called) == 1
```

### 3.9 `tests/test_visibility_tools_placeholder.py` (TDD Phase 2)
```python
"""TDD the Phase 2 fire-and-forget blind spot. Currently FAILS."""
import pytest


async def test_get_research_report_returns_recent_findings():
    from src.visibility_tools import get_research_report
    r = await get_research_report(window_seconds=600)
    assert r.findings
    assert all(f.source.startswith("miner:") for f in r.findings)


async def test_get_shell_job_status_links_to_active_session():
    from src.visibility_tools import get_shell_job_status
    s = await get_shell_job_status(job_id="latest")
    assert s.session_id
```

---

## 4. Next Unknown

**What is the actual signal quality of `bg-code-architect` at the three different cadences (14400s vs 1800s vs 120s), measured as distinct actionable findings per hour — not polls per hour?**

This is the only unknown on the dashboard where:
- The answer is not in any document
- Shipping the next miner-tuning commit before answering it is wasted work
- The north-star explicitly requires it (*"Each loop iteration is measured by Brief 5 rollups, not vibes"*)
- 3 commits in 75 minutes prove the team is currently tuning blind

**Investigation:**
1. Pick `bg-code-architect` (highest-leverage, busiest class).
2. Run at three cadences (60s, 900s, 3600s) for 24h windows each, instrumented to log `task_hash` per finding.
3. Metrics: unique URLs returned per hour, AND a 20-finding human-judged "would I have acted on this?" per cadence.
4. Lock the cadence-finding that wins, codify in `tests/test_miners_cadence_baseline.py`.
5. **Block all future `interval_seconds` changes** until the baseline lands and MR-OD-001 is enforceable.

**Why this and not the alternatives:**

| Candidate | Why not |
|---|---|
| Implementer gating design | Mechanical fix (worktree + receipt + HITL); no investigation needed |
| Pydantic Router (#3958) | "needs more info" — blocked on Jwalin's call |
| Five-router inventory | Static scan; one `ls ~/projects` |
| `api_key_env` 3-case tests | Three unit tests, no investigation |
| Brief 6 capture at chokepoint | Implementation, not investigation |
| Visibility tools (Phase 2) | Implementation, not investigation |

Cadence measurement is the **one unknown where the answer is not in any document** and where shipping the next miner-tuning commit before answering it is wasted work. It's the bottleneck on the flywheel; everything else is downstream of it.

---

## 5. Dashboard Card (1-Surface)

```
┌──────────────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ 🔴 CADENCE INSTABILITY       │ 🟡 CAPTURE CHOKEPOINT        │ 🔴 FIRE-AND-FORGET GAP      │
│ 3 commits, 75 min,           │ Spec'd, not built.           │ Phase 2 not landed.          │
│ 6-100× interval change.      │ 28 importers waiting.        │ visibility_tools.py         │
│ No measurement, no test.     │ 1 raise = 28 regressions.    │ spec'd, not built.           │
│ [test_miners_cadence_         │ [test_capture_at_             │ [test_visibility_tools_      │
│  governance.py]              │  chokepoint.py]              │  placeholder.py]            │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 bg-implementer LOOSE      │ 🟡 auth-bypass = admin       │ 🟡 session.mode = DEAD      │
│ Self-modifying, no gate,     │ 2-line posture change,       │ Written 4×, read 0×.        │
│ no receipt, no HITL.         │ no test.                     │ Legacy sessions empty.       │
│ Conflicts with 3 non-goals.  │ [test_auth_localhost_         │ [test_session_mode_          │
│ [test_implementer_miner_      │  bypass.py]                  │  contract.py]                │
│  gating.py]                  │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 UNKNOWN: miner signal     │ 🟡 PII surface in 28         │ 🟡 5 routers, no harvest     │
│ quality at 3 cadences?       │ callers? Regex is best-      │ plan. Sixth-router temp-    │
│ North-star says "no vibes"   │ effort. Need caller-shape    │ tation is real.              │
│ but no measure exists.       │ audit before Brief 6.        │ [grep-and-inventory]         │
└──────────────────────────────┴──────────────────────────────┴──────────────────────────────┘
🟢 aligned with North Star  🟡 spec'd but unverified  🔴 gap with no owner
```

**One-liner:** *The plan is done. The bottleneck is the missing measurement loop (Brief 5). Land the cadence-baseline test, land the capture-invariants test, archive the 5 routers, and stop tuning until you can measure.*