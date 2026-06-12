# 1-Surface Synthesis — orchestrator-mvp / 2026-06-11

> **Headline:** Three commits in 75 minutes collapsed miner cadence 6–100× without measurement, a self-applying `bg-implementer` miner shipped ungated, and a 2-line auth change implicitly granted `admin` on any loopback request — all with no test coverage. The North Star doc is 787 lines; the code is 33. The bottleneck is no longer planning; it's the missing measurement loop that Brief 5 was supposed to provide.

---

## 1. Pattern Decomposition

### 1.1 Cadence instability as a process regression
| Commit | bg-code | bg-test | bg-transcript | bg-memory | bg-job | new |
|---|---|---|---|---|---|---|
| `1dfa3f5` (12:46) | 14400s | 21600s | 7200s | 43200s | 21600s | — |
| `ee73ae3` (13:56) | 1800s | 1800s | 900s | 2700s | 2700s | — |
| `c510b31` (14:01) | 120s | 120s | 60s | 180s | 180s | +sandbox, +implementer |

`bg-transcript-architect` at 60s will re-read the same `~/.pi/agent/sessions/` (~7.7 MB JSONL) 1,440×/day. The third commit's message ("work time is the pacing") is philosophy, not measurement.

### 1.2 The `bg-implementer` is a new class of problem
First miner with `source: "implementer"`, query "implement the most actionable recent miner finding", at 120s cadence. It reads the other 6 miners' findings and writes code. The North Star's non-goals explicitly ban *"no training runs triggered by Odysseus"* and *"no swarm/mesh"* — but a miner that auto-implements its own findings is structurally adjacent to both. **No receipt per emitted change, no write-scope enforcement, no human-in-the-loop, no test asserting any of the above.**

### 1.3 The 2-line auth change is a regression
```python
if LOCALHOST_BYPASS and _is_trusted_loopback(request):
+   request.state.current_user = "admin"
+   request.state.api_token = False
    return await call_next(request)
```
No test fails closed if a future reader of `request.state.current_user` for authz silently inherits admin. A posture change shipped as a diff.

### 1.4 The chokepoint insight is correct but unenforced
`llm_call_async` has 28 importers. Capture belongs there (North Star §6.1). None of the three commits implements capture. The doc is the spec; the build is missing. When capture lands, `route_code`'s subprocess path needs its own call site — currently a known gap, not addressed.

### 1.5 `session.mode` = dead data with migration cost
Written in 4 places (`core/models.py` + 3× `core/session_manager.py`), read in 0. The next PR that adds a mode consumer will discover empty data for legacy sessions. No backfill.

### 1.6 `api_key_env` precedence is undefined
Docstring says "takes precedence over `api_key`" but never defines:
- Env var unset → silent fall-through to DB? 500? In-band? **Untested.**
- Both populated → "env wins" claimed, **untested**.
- Neither → `None` flows into HTTP client (likely leaks via stack trace).
- Migration doesn't backfill or validate existing rows.

### 1.7 Five overlapping routers, no harvest plan
`platform/app.py+router.py` (dead), `orchestrator-mvp`, `unified-personal-os`, `routing-engine`, `workspace-command`. Every one was "the unified thing" once. The "fifth router risk" is the single most repeated warning in the corpus; no defense against it.

### 1.8 Error-contract violations are clustering
#3992, #3993, #3995, #3966, #3965 — all in-band error contract violations from `orchestration-briefs.md`. The contract is documented; the tests are not enforcing it.

---

## 2. Memory Rules

```yaml
- id: MR-OD-001
  rule: "Cadence changes to config/miners.json require a 'Measured:' or 'Rollup:'
         line in the commit body. Block merge otherwise."
  source: "3-commit oscillation 12:46→14:01 on 2026-06-11"

- id: MR-OD-002
  rule: "In-band error contract: /api/route NEVER 500. Bad body, timeout,
         missing CLI, stale quota → {error: true, response: <truncated>}."
  source: "orchestration-briefs.md + issues #3966, #3992, #3995"

- id: MR-OD-003
  rule: "Capture lives at the chokepoint (llm_call_async), not the router.
         28 importers > 1 importer for corpus coverage. route_code subprocess
         path needs its own call site — both move together."
  source: "odysseus-north-star.md §6.1"

- id: MR-OD-004
  rule: "Five overlapping routers exist. Before proposing a new router, grep
         for TaskRouter + the 4 names and write a 'why this is not a sixth
         router' paragraph in the PR."
  source: "odysseus-north-star.md §2"

- id: MR-OD-005
  rule: "bg-implementer is self-applying. Disabled by default. When enabled,
         must be gated by write-scope, emit a receipt per change, require
         human-in-the-loop for non-worktree paths."
  source: "c510b31 + North Star non-goal 'no training runs triggered'"

- id: MR-OD-006
  rule: "LOCALHOST_BYPASS implies admin. Any code reading request.state for
         authorization MUST be tested against a non-loopback Host header."
  source: "1dfa3f5 app.py diff"

- id: MR-OD-007
  rule: "session.mode requires a consumer in the same PR. Writing the field
         with no reader is dead data with migration cost."
  source: "1dfa3f5 models.py/session_manager.py"

- id: MR-OD-008
  rule: "api_key_env precedence: env > encrypted > None. Unset env falls
         through silently to DB. Neither → None + in-band error (never 500)."
  source: "core/database.py migration + docstring"

- id: MR-OD-009
  rule: "Pydantic Router (#3958) must wrap, not replace, classify_task."
  source: "orchestration-briefs.md + #3958"

- id: MR-OD-010
  rule: "Online Skill Sharing (#3974) conflicts with non-goal 'no cloud sync
         of exchanges or transcripts.' Default-reject or LAN/mDNS only."
  source: "North Star Non-goals + #3974"
```

---

## 3. Pytest files to add

### 3.1 `tests/test_miners_cadence_governance.py`
```python
"""Lock the cadence tuning loop. Cadence changes without a measurement
citation are a process regression. Source: synthesis 2026-06-11 PM."""
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
        assert t["interval_seconds"] >= c["interval_seconds"], (
            "transcript re-reads MB-scale JSONL; tighter than githits = over-cycling"
        )

def test_cadence_change_cites_measurement():
    """Fails CI if config/miners.json changed in HEAD without a
    'Measured:'/'Rollup:' line in the commit body. Prevents vibes-cadence."""
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
    ("post", "/api/route",       {"task": "hello"}),
    ("post", "/api/route",       {}),
    ("post", "/api/route",       {"task": "x" * 1_000_000}),
    ("post", "/api/route/code",  {"task": "ls"}),
    ("post", "/api/route/research", {"task": "x"}),
]

@pytest.mark.parametrize("method,path,body", DISPATCH)
def test_dispatch_never_5xx(method, path, body):
    r = getattr(c, method)(path, json=body)
    assert r.status_code < 500, f"{method} {path} → {r.status_code}: {r.text[:300]}"
    if r.status_code == 200 and not body.get("task"):
        assert r.json().get("error") is True, "200/ok for invalid body"

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
    # And the dispatch that uses it returns in-band error, not 500.
```

### 3.7 `tests/test_subprocess_lifecycle.py`
```python
"""#3995: stopping a download left orphaned hf/python processes. Worktree
isolation is not enough — need process-group reap."""
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
    assert s.session_id  # auto-injected into the calling session
```

---

## 4. Next Unknown

**Cadence measurement at the fleet level — what is the actual signal quality of `bg-code-architect` at the three different cadences (14400s vs 1800s vs 120s), measured as *distinct actionable findings per hour* — not polls per hour?**

This is the only unknown on the dashboard where:
- The answer is not in any document
- Shipping the next miner-tuning commit before answering it is wasted work
- The north-star explicitly requires it (*"Each loop iteration is measured by Brief 5 rollups, not vibes"*)
- 3 commits in 75 minutes prove the team is currently tuning blind

**Investigation:**
1. Pick `bg-code-architect` (highest-leverage, busiest class).
2. Run at three cadences (60s, 900s, 3600s) for 24h windows each.
3. Metrics: unique URLs mined/hour, AND a 20-sample human-judged "would I have acted on this?" per cadence.
4. Lock the cadence-finding that wins, codify in `tests/test_miners_cadence_baseline.py`.
5. **Block all future `interval_seconds` changes** until the baseline lands and MR-OD-001 is enforceable.

---

## 5. Dashboard Card

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