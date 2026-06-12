# 1-Surface Dashboard — orchestrator-mvp / 2026-06-11

> **Headline:** Two P0 regressions shipped in 75 minutes. `bg-implementer` reads 6 other miners and writes code ungated. `LOCALHOST_BYPASS` now implicitly grants `admin` to every loopback request. The measurement loop (Brief 5) that would catch this is not built. The corpus chokepoint (28 callers in `llm_call_async`) is spec'd in 787 lines of docs and **zero call sites**.

---

## 1. Pattern Decomposition

### 1.1 Cadence oscillation is a process regression
| Commit | bg-code | bg-test | bg-transcript | bg-memory | bg-job | new |
|---|---|---|---|---|---|---|
| `1dfa3f5` 12:46 | 14400s | 21600s | 7200s | 43200s | 21600s | — |
| `ee73ae3` 13:56 | 1800s | 1800s | 900s | 2700s | 2700s | — |
| `c510b31` 14:01 | **120s** | **120s** | **60s** | **180s** | **180s** | +sandbox, +implementer |

`bg-transcript-architect` at 60s will re-read the same `~/.pi/agent/sessions/` (~7.7 MB) JSONL 1,440×/day. The third commit's body (*"work time is the pacing"*) is philosophy, not measurement. The north-star doc itself demands *"Each loop iteration is measured by Brief 5 rollups"* — but Brief 5 doesn't exist yet. **This is tuning-by-vibes on a chokepoint that's supposed to feed the flywheel.**

### 1.2 The `bg-implementer` is a new class of problem
First miner with `source: "implementer"`, query *"implement the most actionable recent miner finding"*, at 120s. It reads the other 6 miners' outputs and writes code. The non-goals ban *"no training runs triggered by Odysseus"* and *"no swarm/mesh"* — but a miner that auto-implements its own findings is structurally adjacent to both. **No receipt per emitted change, no write-scope enforcement, no human-in-the-loop, no test.**

### 1.3 The 2-line auth change is a security regression
```python
if LOCALHOST_BYPASS and _is_trusted_loopback(request):
+   request.state.current_user = "admin"
+   request.state.api_token = False
    return await call_next(request)
```
No test fails closed if any future code reads `request.state.current_user` for authz and silently inherits admin. The comment acknowledges the risk; the diff ships it without a defensive test.

### 1.4 The chokepoint insight is correct but unenforced
`llm_call_async` is imported by **28 files** — chat, scheduler tasks, research, notes, email, summaries, agent loops. The Brief 6 amendment is right: capture goes at the chokepoint. None of the three commits implements capture. When `record_exchange` lands, `route_code`'s subprocess path needs its own call site — currently a known gap.

### 1.5 `session.mode` and `api_key_env` are dead/undertested
- `mode: str = "chat"` written 4× (models.py + 3× session_manager.py), read 0×. No backfill.
- `api_key_env` precedence: env > encrypted > None. 3 cases (env unset, both set, neither) all undefined and untested.

### 1.6 Error-contract violations are clustering
Issues #3992, #3993, #3995, #3966, #3965 — all in-band error contract violations from `orchestration-briefs.md`. Documented; not enforced.

### 1.7 Spec/code ratio
- **~787 lines** of new docs in 24h (north-star 280 + briefs 507)
- **~33 lines** of executable code in same window
- North Star §6.6 says: *"The single highest-value next action is no longer a document — it's merging Brief 1."* Not taken.

### 1.8 Five overlapping routers, no archival plan
`platform/app.py+router.py` (dead), `orchestrator-mvp`, `unified-personal-os`, `routing-engine`, `workspace-command`. No harvest plan.

---

## 2. Memory Rules (paste-into-supervisor)

```yaml
# MR-OD-011: bg-implementer must be disabled by default
- id: MR-OD-011
  rule: "The bg-implementer miner is self-applying (it reads 6 other miners'
         outputs and writes code). Until write-scope enforcement, per-change
         receipts, and human-in-the-loop approval ship, bg-implementer MUST
         be enabled: false. This extends the non-goal 'no training runs
         triggered by Odysseus' to 'no code changes triggered by Odysseus
         without explicit per-action approval'."
  source: "c510b31 + north-star §3, §non-goals"
  severity: critical

# MR-OD-012: Cadence tuning governance
- id: MR-OD-012
  rule: "Changes to config/miners.json interval_seconds by more than 2x
         require a 'Measured:' citation in the commit body. Brief 5 rollups
         are the only valid citation. Without measurement, cadence tuning
         is vibes and the changelog should say so."
  source: "3-commit oscillation 2026-06-11"
  severity: high

# MR-OD-013: Auth context for loopback bypass
- id: MR-OD-013
  rule: "Any code path that sets request.state.current_user = 'admin' must
         be paired with a test asserting that a non-loopback Host header
         causes the same route to return 401/403. The bypass defense is
         _is_trusted_loopback; if the check fails closed, admin should NOT
         be granted."
  source: "1dfa3f5 app.py +2 lines"
  severity: critical

# MR-OD-014: Capture at the chokepoint
- id: MR-OD-014
  rule: "record_exchange goes in llm_call_async (src/llm_core.py) for 28
         importers, AND in route_code (core/router.py) for the subprocess
         path. Two call sites, never one, never zero."
  source: "north-star §6.1"
  severity: high

# MR-OD-015: Error contract
- id: MR-OD-015
  rule: "/api/route, /api/route/code, /api/route/research, and any dispatch
         surface must NEVER return 5xx. Timeout, missing CLI, stale quota,
         bad JSON body — all become {error: true, response: <truncated>}."
  source: "orchestration-briefs.md + #3966, #3992, #3993, #3995, #3965"
  severity: high

# MR-OD-016: Subprocess lifecycle
- id: MR-OD-016
  rule: "Code-task subprocesses must register a process group (os.setsid)
         and on timeout/abort kill -PGID. Tests must assert no orphan
         descendants survive. Issue #3995 is the exemplar failure."
  source: "#3995 + brief 2 worktree-isolation is not enough"
  severity: high

# MR-OD-017: session.mode requires a consumer
- id: MR-OD-017
  rule: "Adding session.mode with no consumer within the same PR is a
         write-only field. Either remove the field or add a reader. The
         mode value 'chat' is the only currently valid value — reject
         others until a reader is added."
  source: "1dfa3f5 core/models.py + session_manager.py"
  severity: medium

# MR-OD-018: api_key_env precedence
- id: MR-OD-018
  rule: "api_key_env precedence: env var > encrypted column > None.
         Env unset falls through to DB silently. Both unset returns None
         and triggers in-band error (not 500). All three cases need tests."
  source: "1dfa3f5 core/database.py migration"
  severity: high

# MR-OD-019: Pydantic Router wraps, does not replace
- id: MR-OD-019
  rule: "If Pydantic Router (#3958) lands, classify_task must remain a
         regex fast-path. Pydantic wraps the result; it does not call LLMs
         on the routing target."
  source: "orchestration-briefs.md + #3958"
  severity: medium

# MR-OD-020: Skill sharing default-reject
- id: MR-OD-020
  rule: "Feature #3974 (Online Skill Sharing) conflicts with the non-goal
         'no cloud sync.' If it lands, it must be LAN/mDNS only, not
         cloud. Default-reject; require an explicit 'no cloud' clause
         in the PR body."
  source: "#3974 + north-star non-goals"
  severity: medium

# MR-OD-021: Per-model parameter allowlist
- id: MR-OD-021
  rule: "Per-chat reasoning effort (#3971) and per-model temperature
         compatibility (#3959 Kimi) push the router toward a unified
         parameter-allowlist per model+provider. One table, not N
         provider shims."
  source: "#3971 + #3959"
  severity: medium

# MR-OD-022: Five-router harvest
- id: MR-OD-022
  rule: "Five overlapping routers exist (platform/app.py+router.py,
         orchestrator-mvp, unified-personal-os, routing-engine,
         workspace-command). Before any new routing layer, grep for
         these and write 'why this is not a sixth router' in the PR.
         Move dead routers to _archive/."
  source: "north-star §2"
  severity: medium

# MR-OD-023: Engine refactor gates
- id: MR-OD-023
  rule: "Engine refactor (Phase 1) breaks tool_implementations.py (4000
         lines) and tool_schemas.py (1300 lines) into @odysseus_tool
         registry. PRs touching tools should not increase either file's
         line count by more than 0 net until the refactor lands."
  source: "ROADMAP Phase 1"
  severity: low

# MR-OD-024: Corpus durability
- id: MR-OD-024
  rule: "data/orchestration/ must be in backup_routes export OR explicitly
         Time-Machine-covered. A flywheel that dies with the disk is not
         a flywheel."
  source: "north-star §6.5"
  severity: medium
```

---

## 3. Pytest Files (copy-paste-ready)

### 3.1 `tests/test_implementer_miner_gating.py`
```python
"""P0: bg-implementer is a self-modifying miner. MR-OD-011.
Disable by default until write-scope, receipts, and HITL ship.
"""
import json
from pathlib import Path
import pytest

CFG = Path("config/miners.json")


def _cfg():
    return json.loads(CFG.read_text())


def test_implementer_disabled_by_default():
    cfg = {m["name"]: m for m in _cfg()}
    impl = cfg.get("bg-implementer")
    if impl is None:
        pytest.skip("bg-implementer not yet configured")
    assert impl["enabled"] is False, (
        "bg-implementer must be enabled:false until write-scope, "
        "per-change receipts, and human-in-the-loop approval land. "
        "See MR-OD-011 and north-star non-goals."
    )


def test_implementer_does_not_read_other_miner_outputs_inline():
    """The implementer's prompt must not include other miners' raw outputs
    without a content-hash dedup layer. Structural guard against feedback
    loop where the same finding is 'implemented' twice."""
    cfg = {m["name"]: m for m in _cfg()}
    impl = cfg.get("bg-implementer")
    if impl is None or not impl.get("enabled"):
        pytest.skip("not enabled")
    assert "dedup_key" in impl or "content_hash_field" in impl, (
        "bg-implementer with enabled:true must declare a content-hash "
        "dedup key to prevent the same finding from being applied twice."
    )


def test_implementer_writes_only_to_worktree(monkeypatch, tmp_path):
    cfg = {m["name"]: m for m in _cfg()}
    impl = cfg.get("bg-implementer")
    if impl is None or not impl.get("enabled"):
        pytest.skip("not enabled")
    monkeypatch.setenv("ODYSSEUS_WORKTREE", str(tmp_path))
    from src.bg_miners import run_miner  # adjust import
    run_miner("bg-implementer", query=impl["query"])
    leaks = [p for p in tmp_path.rglob("*") if p.is_file()
             and not str(p.resolve()).startswith(str(tmp_path.resolve()))]
    assert not leaks, f"bg-implementer wrote outside worktree: {leaks}"


def test_implementer_emits_receipt():
    cfg = {m["name"]: m for m in _cfg()}
    impl = cfg.get("bg-implementer")
    if impl is None or not impl.get("enabled"):
        pytest.skip("not enabled")
    from src.bg_miners import run_miner
    from core.orchestration_trace import get_recent_receipts
    before = len(get_recent_receipts(source="miner:bg-implementer"))
    run_miner("bg-implementer", query=impl["query"])
    after = len(get_recent_receipts(source="miner:bg-implementer"))
    assert after > before, "bg-implementer must emit a receipt per write"
```

### 3.2 `tests/test_localhost_bypass_auth.py`
```python
"""P0: LOCALHOST_BYPASS now grants admin implicitly. MR-OD-013.
A non-loopback Host header must NOT inherit admin.
"""
import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LOCALHOST_BYPASS", "true")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    return TestClient(app)


def test_loopback_host_gets_admin(client):
    resp = client.get("/api/whoami", headers={"Host": "127.0.0.1:8000"})
    assert resp.status_code == 200
    assert resp.json().get("current_user") == "admin"


def test_non_loopback_host_rejected(client):
    """A non-loopback Host must NOT inherit admin. If _is_trusted_loopback
    fails closed, the request either returns 401/403 or proceeds without
    admin identity — never with admin."""
    resp = client.get("/api/whoami", headers={"Host": "evil.example.com"})
    if resp.status_code == 200:
        body = resp.json()
        assert body.get("current_user") != "admin", (
            "Non-loopback request was granted admin via LOCALHOST_BYPASS"
        )


def test_admin_endpoint_rejects_non_loopback(monkeypatch):
    monkeypatch.setenv("LOCALHOST_BYPASS", "true")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    c = TestClient(app)
    resp = c.get(
        "/api/admin/anything-protected",
        headers={"Host": "evil.example.com"},
    )
    assert resp.status_code in (401, 403, 302, 303, 307), (
        f"admin route accepted non-loopback: {resp.status_code}"
    )


def test_bypass_disabled_admin_route_requires_auth(monkeypatch):
    monkeypatch.setenv("LOCALHOST_BYPASS", "false")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    c = TestClient(app)
    resp = c.get("/api/admin/anything-protected")
    assert resp.status_code in (401, 302, 303, 307)
```

### 3.3 `tests/test_capture_invariants.py`
```python
"""P0: record_exchange at the chokepoint. MR-OD-014.
Two call sites: llm_call_async (28 importers) and route_code (subprocess).
"""
import ast
import inspect
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]


def _calls_record_exchange(src: str) -> bool:
    return "record_exchange" in src


def test_chokepoint_calls_record_exchange():
    from src import llm_core
    src = inspect.getsource(llm_core.llm_call_async)
    assert _calls_record_exchange(src), (
        "src/llm_core.llm_call_async must call record_exchange — 28 "
        "importers depend on this chokepoint. North Star §6.1."
    )


def test_route_code_subprocess_also_captures():
    from core import router
    src = inspect.getsource(router.route_code)
    assert _calls_record_exchange(src), (
        "core/router.route_code must call record_exchange — subprocess "
        "path bypasses llm_call_async"
    )


def test_record_exchange_never_raises_on_unwritable_dir(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", "/dev/full/cannot_write")
    from core.exchange_log import record_exchange
    record_exchange(
        task="hi", response="ok", classification="chat",
        model_used="t", provider="t", tokens=1, latency_ms=1.0,
    )  # must not raise


def test_kill_switch_env_disables_capture(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_NO_CAPTURE", "1")
    from core.exchange_log import record_exchange
    import unittest.mock as mock
    with mock.patch("builtins.open", side_effect=AssertionError("written")):
        record_exchange(task="x", response="y")


def test_per_request_optout(monkeypatch):
    from core.exchange_log import record_exchange
    import unittest.mock as mock
    with mock.patch("builtins.open", side_effect=AssertionError("written")):
        record_exchange(task="x", response="y", capture=False)


def test_secret_shapes_redacted():
    from core.exchange_log import record_exchange
    import json
    out = record_exchange(
        task="my key is sk-abc123def456",
        response="AKIAIOSFODNN7EXAMPLE bearer: foo",
    )
    payload = json.dumps(out)
    assert "sk-abc123" not in payload
    assert "AKIAIOSFODNN7EXAMPLE" not in payload


def test_capture_joins_to_receipt_via_task_hash(monkeypatch, tmp_path):
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", str(tmp_path))
    from core.exchange_log import record_exchange
    from core.orchestration_trace import record_trace
    th = "deadbeef" * 4
    record_trace(task_hash=th, classification="chat", model="t",
                 provider="t", tokens=1, latency_ms=1.0)
    record_exchange(task_hash=th, task="x", response="y",
                    classification="chat", model_used="t", provider="t",
                    tokens=1, latency_ms=1.0)
    assert (tmp_path / "exchanges").exists() or any(tmp_path.glob("*.jsonl"))
```

### 3.4 `tests/test_miners_cadence_governance.py`
```python
"""P1: Cadence tuning requires measurement. MR-OD-012.
"""
import json
import re
import subprocess
from pathlib import Path
import pytest

CFG = Path("config/miners.json")
REPO = Path(__file__).resolve().parents[1]


def test_intervals_within_bounds():
    cfg = json.loads(CFG.read_text())
    for m in cfg:
        assert 30 <= m["interval_seconds"] <= 86400, (
            f"{m['name']} interval {m['interval_seconds']}s outside [30, 86400]"
        )


def test_miner_names_unique():
    cfg = json.loads(CFG.read_text())
    names = [m["name"] for m in cfg]
    assert len(names) == len(set(names))


def test_cadence_change_cites_measurement():
    """If config/miners.json was modified in HEAD, the commit body must
    cite a measurement. Vibes-cadence is a process regression."""
    diff = subprocess.run(
        ["git", "diff", "--stat", "HEAD~1", "config/miners.json"],
        cwd=REPO, capture_output=True, text=True,
    )
    if "miners.json" not in diff.stdout:
        pytest.skip("no diff against HEAD~1")
    body = subprocess.check_output(
        ["git", "log", "-1", "--format=%b"], cwd=REPO, text=True,
    )
    assert re.search(r"(?i)(measured|rollup|brief[- ]?5|baseline)", body), (
        "config/miners.json changed but commit body lacks a 'Measured:' "
        "citation. See MR-OD-012."
    )
```

### 3.5 `tests/test_router_never_500.py`
```python
"""P1: In-band error contract — dispatch surfaces must NEVER 5xx. MR-OD-015.
"""
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
        assert r.json().get("error") is True, (
            "200/ok for invalid body — must be in-band error"
        )
```

### 3.6 `tests/test_subprocess_lifecycle.py`
```python
"""P1: Subprocess cleanup. Issue #3995 exemplar.
"""
import time
import psutil
import pytest
import inspect

from core.router import route_code


def _python_pids():
    return {p.pid for p in psutil.process_iter(["name"])
            if "python" in (p.info.get("name") or "").lower()}


def test_route_code_reaps_descendants_on_timeout(tmp_path, monkeypatch):
    before = _python_pids()
    with pytest.raises(Exception):
        route_code(task="python3 -c 'import time; time.sleep(60)'",
                   cwd=tmp_path, timeout=2)
    time.sleep(2)
    leaked = _python_pids() - before
    assert not leaked, f"orphaned python pids after timeout: {leaked}"


def test_subprocess_uses_process_group():
    from core import router
    src = inspect.getsource(router)
    assert "setsid" in src or "start_new_session" in src, (
        "subprocess path must use setsid/start_new_session for clean teardown"
    )
```

### 3.7 `tests/test_session_mode_contract.py`
```python
"""P2: session.mode is write-only. MR-OD-017.
"""
from core.session_manager import SessionManager


def test_default_mode_is_chat():
    s = SessionManager.create()
    assert s.mode == "chat"


def test_legacy_sessions_default_to_chat():
    """Pre-migration rows have no mode column; reads must default to 'chat'."""
    s = SessionManager.get("legacy-1")
    assert s.mode == "chat"


def test_mode_round_trip():
    s = SessionManager.create(mode="chat")
    s.save()
    assert SessionManager.get(s.id).mode == "chat"


def test_invalid_mode_rejected():
    """Until a consumer reads mode, only 'chat' is valid. Reject 'research',
    'code', etc. to prevent dead-data proliferation."""
    with pytest.raises(ValueError):
        SessionManager.create(mode="research")
```

### 3.8 `tests/test_api_key_env_precedence.py`
```python
"""P2: api_key_env precedence. MR-OD-018.
"""
import pytest
from core.database import ModelEndpoint


@pytest.fixture
def make_ep():
    def _make(api_key=None, api_key_env=None):
        ep = ModelEndpoint(name="t", api_key=api_key, api_key_env=api_key_env)
        return ep
    return _make


def test_env_var_takes_precedence(monkeypatch, make_ep):
    monkeypatch.setenv("MY_KEY", "sk-env")
    ep = make_ep(api_key="sk-from-db", api_key_env="MY_KEY")
    assert ep.resolve_api_key() == "sk-env"


def test_env_unset_falls_back_to_db(monkeypatch, make_ep):
    monkeypatch.delenv("MISSING", raising=False)
    ep = make_ep(api_key="sk-from-db", api_key_env="MISSING")
    assert ep.resolve_api_key() == "sk-from-db"


def test_neither_returns_none_and_never_500s(monkeypatch, make_ep):
    monkeypatch.delenv("NOPE", raising=False)
    ep = make_ep(api_key=None, api_key_env="NOPE")
    assert ep.resolve_api_key() is None
    from fastapi.testclient import TestClient
    from app import app
    c = TestClient(app)
    r = c.post("/api/route", json={"task": "x"}, headers={"X-Endpoint-Id": "t"})
    assert r.status_code < 500
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

### 3.10 `tests/test_pydantic_router_compat.py`
```python
"""MR-OD-019: Pydantic Router (#3958) must wrap, not replace,
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

---

## 4. Next Unknown

**What is the actual production-traffic NER fallback rate and per-importer-category latency distribution under the layered architecture, when replayed against 7 days of real-shape chat traffic?**

**Why this and not the alternatives:**

| Candidate | Why not the next one |
|---|---|
| Cadence measurement (Brief 5 rollups) | Spec'd in north-star; needs Brief 5 — an implementation task, not an investigation |
| 5-router harvest inventory | Static `ls ~/projects` and a 1-page table; no investigation needed |
| Sandbox isolation choice | `bg-sandbox-architect` will surface candidates from githits; team picks from data |
| Implementer gating design | Mechanical fix (worktree + receipt + HITL + dedup); not investigation |
| Pydantic Router spec | Blocked on Jwalin (#3958 "needs more info"); not an investigation |
| Per-model parameter table | Scoping work; schema design; not research |
| PII surface in 28 callers | Addressed in prior cycle (MR-OD-014, tests drafted) |
| NER layer for high-tier importers | Addressed in prior cycle (MR-OD-018); the *decision* is made, the *validation* is the unknown |
| `task_hash` dedup policy | Spec'd in north-star; needs a `core/task_hash_policy.json` to exist before capture lands — this is implementation, not investigation |

**The production-traffic replay is the one unknown where:**

- **The answer is not in any document.** The benchmark suite (MR-OD-018) tests against 21 synthetic fixtures. Real chat is different. The team does not know what the *actual* fallback rate will be in production.
- **The decision is irreversible at scale.** Switching from layered to pure NER (or vice versa) later means re-processing the entire `exchanges/` corpus, re-validating every captured exchange, and re-running the eval suite in pioneer-adaption. The architecture must be right *before* capture ships.
- **The cost of getting it wrong is not symmetric.** If layered's fallback rate turns out to be 80% in production, the layered architecture provides no latency benefit and we're paying the engineering cost of two layers. If pure NER turns out to be too slow, every chat message adds 50ms. Both are reversible, but the rollback is non-trivial.
- **The fallback rate also drives the circuit-breaker trip frequency (MR-OD-023).** A 70% fallback rate means the circuit breaker trips frequently, regex-only mode is in effect most of the time, and the redaction floor is back to "credentials only" — defeating the entire tier-aware redaction design.

**Investigation (concrete):**

1. **Replay 7 days of real-shape chat traffic** through the layered architecture in dry-run mode. Use:
   - `~/.pi/agent/sessions/` (7.7 MB JSONL) — most representative of "agent loop" shape
   - `~/.codex/sessions/` (12 MB JSONL) — most representative of "code/CLI" shape
   - `~/.claude/projects/` (492 KB) — most representative of "chat" shape
2. **Measure**:
   - Fallback rate per importer category (chat vs email vs notes vs summaries vs research vs agent loops)
   - Per-call latency distribution (p50, p95, p99) stratified by importer category and payload size
   - Circuit-breaker trip events
   - False-positive rate (over-redaction, especially of code)
3. **Stratify by payload size**: short prompts (<200 chars) vs long chat histories (4000+ chars). Long payloads stress NER.
4. **Stratify by language**: English-only? Multi-lingual? (The regex-and-skeleton layer may mis-tag non-English names.)
5. **Decision matrix**:
   - If fallback < 30%: ship layered, monitor.
   - If 30% < fallback < 70%: layered is fine, but document the cost-of-complexity.
   - If fallback > 70%: ship pure NER (assuming it passes the budget).
   - If neither: roll retention back to 30 days and revisit.
6. **Outcome**: a `docs/redaction_production_fallback_report.md` with the data, the stratification, and the final architecture call. This is what locks the decision.

**Why this gates everything:** the benchmark says "what's possible on synthetic." The production-traffic replay says "what's true in practice." If they disagree, the benchmark was wrong and the architecture must change. This is the **last step before** Brief 6 can land with "keep forever" retention.

**The single most important question the dashboard can ask right now:** *what is the actual NER fallback rate when the layered architecture is replayed against real-shape traffic, and does that rate exceed the 70% threshold that makes the layered architecture pointless?* The answer is empirical and cannot be derived from docs.

---

## 5. Dashboard Card (1-Surface)

```
┌──────────────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ 🔴 CADENCE INSTABILITY       │ 🟡 CAPTURE CHOKEPOINT        │ 🔴 FIRE-AND-FORGET GAP      │
│ 3 commits, 75 min,           │ Spec'd, not built.           │ Phase 2 not landed.          │
│ 6-100× interval change.      │ 28 importers waiting.        │ visibility_tools.py         │
│ No measurement, no test.     │ 1 raise = 28 regressions.    │ spec'd, not built.           │
│ [test_miners_cadence_         │ [test_capture_invariants.py]  │ [test_visibility_tools_      │
│  governance.py]              │                              │  placeholder.py]            │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 bg-implementer LOOSE      │ 🟡 auth-bypass = admin       │ 🟡 session.mode = DEAD      │
│ Self-modifying, no gate,     │ 2-line posture change,       │ Written 4×, read 0×.        │
│ no receipt, no HITL.         │ no test.                     │ Legacy sessions empty.       │
│ Conflicts with 3 non-goals.  │ [test_localhost_bypass_       │ [test_session_mode_          │
│ [test_implementer_miner_      │  auth.py]                    │  contract.py]                │
│  gating.py]                  │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 UNKNOWN: production       │ 🟡 5 routers, no harvest     │ 🟡 Phase 3 (super-skills)  │
│ NER fallback rate on real    │ plan. Sixth-router temp-     │ listed, not landed.         │
│ chat traffic. Benchmark is   │ tation is real.              │ Repo map / auto-fix /        │
│ synthetic; production will   │ [grep-and-inventory]         │ Cline checklist.            │
│ differ. MR-OD-018 + 023      │                              │                             │
│ gate the ship decision.      │                              │                             │
└──────────────────────────────┴──────────────────────────────┴──────────────────────────────┘
🟢 aligned with North Star  🟡 spec'd but unverified  🔴 gap with no owner
```

**One-liner:** *Two P0 regressions shipped in 75 minutes without tests. The measurement loop (Brief 5) is the missing primitive. The NER fallback rate on production traffic is the unknown that decides whether we ship layered, switch to pure NER, or roll retention back from "keep forever" to 30 days — and it's the next hour's work.*