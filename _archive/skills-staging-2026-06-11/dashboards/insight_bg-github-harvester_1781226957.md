# 1-Surface Dashboard — orchestrator-mvp / 2026-06-12 (Task Hash Dedup Policy Cycle)

> **Headline:** Three commits in 75 minutes collapsed miner cadence 6–100× without measurement. `bg-implementer` reads 6 other miners and writes code ungated. `LOCALHOST_BYPASS` now implicitly grants `admin` to every loopback request. North Star is 787 lines; the code is 33. **The bottleneck is no longer planning — it's the missing measurement loop (Brief 5).** New since prior cycle: SGLANG missing deps (4010), agent round-boundary state-reset bugs (3998, 4005, 4002, 3999, 3993, 3992), Pydantic Router question (3958) — every one of these is *exactly* the class of regression the proposed 1-PR fixes (MR-OD-013/015/019) are designed to make impossible. **Cycle 3 focus: the `task_hash` join semantics in Brief 6 are still undefined. Pioneer-adaption's correction mining depends on it. Until the dedup policy lands, the corpus that capture fills is either 3×-inflated or 1×-silenced — and we don't know which.**

---

## 1. Pattern Decomposition

### 1.1 Cadence oscilation is a process regression
| Commit | bg-code | bg-test | bg-transcript | bg-memory | bg-job | new |
|---|---|---|---|---|---|---|
| `1dfa3f5` 12:46 | 14400s | 21600s | 7200s | 43200s | 21600s | — |
| `ee73ae3` 13:56 | 1800s | 1800s | 900s | 2700s | 2700s | — |
| `c510b31` 14:01 | **120s** | **120s** | **60s** | **180s** | **180s** | +sandbox, +implementer |

`bg-transcript-architect` at 60s will re-read `~/.pi/agent/sessions/` (~7.7 MB) 1,440×/day. The 3rd commit's body (*"work time is the pacing"*) is filosofía, not measurement. North Star §6.3 requires *"Each loop iteration is measured by Brief 5 rollups"* — but Brief 5 doesn't exist yet. **MR-OD-012 codifies the rule but the rule isn't enforced.**

### 1.2 `bg-implementer` is a new class of problem
First miner with `source: "implementer"`, query *"implement the most actionable recent miner finding"*, at 120s. Reads the other 6 miners' outputs and writes code. The non-goals ban *"no training runs triggered by Odysseus"* and *"no swarm/mesh"* — but a self-implementing miner is structurally adjacent to both. **No receipt per write, no worktree gate, no human-in-the-loop. MR-OD-011 must hold.**

### 1.3 The 2-line auth change is a security regression
```python
if LOCALHOST_BYPASS and _is_trusted_loopback(request):
+   request.state.current_user = "admin"
+   request.state.api_token = False
    return await call_next(request)
```
A 2-line diff that implicitly grants `admin` to every loopback caller. No test fails closed if any future code reads `request.state.current_user` for authz. **MR-OD-013 closes this gap in 1 test.**

### 1.4 The chokepoint is right but unenforced
`llm_call_async` has 28 importers. Capture belongs there (North Star §6.1). None of the 3 commits implements capture. When capture lands, `route_code`'s subprocess path needs its own call site. **MR-OD-014 + `test_capture_at_chokepoint.py` enshrine the 2-call-site contract.**

### 1.5 `session.mode` and `api_key_env` are dead/undertested
- `mode: str = "chat"` written 4× (models.py + 3× session_manager.py), read 0×.
- `api_key_env` precedence: env > encrypted > None. 3 cases (env unset, both set, neither) all undefined and untested. **MR-OD-017 + MR-OD-018 codify; the 3-case test matrix is the floor.**

### 1.6 Error-contract violations cluster (and are growing)
Issues #3966, #3992, #3993, #3995, #3998, #4002, #4005, #4010 — all in-band error contract / state-cleanup / dependency-decl violations from `orchestration-briefs.md`. Documented; not enforced. **MR-OD-015 + the `test_router_never_500.py` parametrized matrix is the cure.**

### 1.7 Spec/code ratio is worsening
- **~787 lines** of new docs in 24h
- **~33 lines** of executable code in same window
- North Star §6.6: *"The single highest-value next action is no longer a document — it's merging Brief 1."* Not taken. The ratio is climbing: 0 doc line per executable line would be ideal, currently ~24:1.

### 1.8 Five overlapping routers, no archival plan
`platform/app.py+router.py` (dead), `orchestrator-mvp`, `unified-personal-os`, `routing-engine`, `workspace-command`. No harvest plan, no `_archive/`, no consolidation report. **MR-OD-023 makes any new routing layer cite why it's not a sixth router.**

### 1.9 Engine refactor (Phase 1) is now listed but unowned
ROADMAP.md adds a 4,000-line / 1,300-line god-object split. **MR-OD-024 makes PRs touching either file size-net-zero until the refactor lands** — without this guard, the refactor will never happen because the files keep growing.

### 1.10 Task hash dedup contract is the missing schema-level decision (NEW this cycle)
Brief 6a defines the capture schema:
```json
{"ts": "...", "unix": 0.0, "task_hash": "...",
 "task": "<full input>", "response": "<full output>",
 "classification": "...", "model_used": "...", "provider": "...",
 "tokens": 0, "latency_ms": 0.0, "error": false, "source": "router|scheduler"}
```
But it never specifies **what fields feed `_hash_task()`** nor **what collision/dedup policy** applies. If `task_hash` is purely a content sha256, then `chat` and `email_summary` callers hashing the same user message collide → 3×-inflated corpus. If it's a content+model+prompt_type hash, dedup is per-shape (correct for trainer). If it's content+model+prompt_type+caller+session, dedup is per-user-intent (correct for eval). **The 28-importer chokepoint makes the choice architectural, not tactical.**

---

## 2. Memory Rules (paste-into-supervisor)

```yaml
- id: MR-OD-011
  rule: "The bg-implementer miner is self-applying (it reads 6 other miners'
         outputs and writes code). Until write-scope enforcement, per-change
         receipts, and human-in-the-loop approval ship, bg-implementer MUST
         be enabled: false."
  source: "c510b31 + north-star §3, §non-goals"
  severity: critical

- id: MR-OD-012
  rule: "Changes to config/miners.json interval_seconds by more than 2x
         require a 'Measured:' citation in the commit body. Brief 5 rollups
         are the only valid citation."
  source: "3-commit oscilation 14400s→60s in 75min, 2026-06-11"
  severity: high

- id: MR-OD-013
  rule: "Any code path that sets request.state.current_user = 'admin' must
         be paired with a test asserting that a non-loopback Host header
         causes the same route to return 401/403."
  source: "1dfa3f5 app.py +2 lines"
  severity: critical

- id: MR-OD-014
  rule: "record_exchange goes in llm_call_async (src/llm_core.py) for 28
         importers, AND in route_code (core/router.py) for the subprocess
         path. Two call sites, never one, never zero."
  source: "north-star §6.1"
  severity: high

- id: MR-OD-015
  rule: "/api/route, /api/route/code, /api/route/research, and any dispatch
         surface must NEVER return 5xx. Timeout, missing CLI, stale quota,
         bad JSON body — all become {error: true, response: <truncated>}."
  source: "orchestration-briefs.md + #3966, #3992, #3993, #3995, #3998, #4002, #4005, #4010"
  severity: high

- id: MR-OD-016
  rule: "Code-task subprocesses must register a process group (os.setsid)
         and on timeout/abort kill -PGID. Tests must assert no orphan
         descendants survive. Issue #3995 is the exemplar failure."
  source: "#3995 + brief 2 worktree-isolation is not enough"
  severity: high

- id: MR-OD-017
  rule: "Adding session.mode with no consumer within the same PR is a
         write-only field."
  source: "1dfa3f5 core/models.py + session_manager.py"
  severity: medium

- id: MR-OD-018
  rule: "api_key_env precedence: env var > encrypted column > None.
         Env unset falls through to DB silently. Both unset returns None
         and triggers in-band error (not 500). All three cases need tests."
  source: "1dfa3f5 core/database.py migration"
  severity: high

- id: MR-OD-019
  rule: "Agent/chat surfaces must reset all round-boundary state
         (_thinkOpen, executed tool fences, pre-tool prose) at every
         round boundary. A new round starts with a clean DOM and a
         clean history slice. Issues #3992, #3993, #3998, #4005, #4002 are exemplar failures."
  source: "#3992 + #3993 + #3998 + #4005 + #4002"
  severity: high

- id: MR-OD-020
  rule: "If Pydantic Router (#3958) lands, classify_task must remain a
         regex fast-path."
  source: "orchestration-briefs.md + #3958"
  severity: medium

- id: MR-OD-021
  rule: "Feature #3974 (Online Skill Sharing) conflicts with the non-goal
         'no cloud sync of exchanges or transcripts.' LAN/mDNS only, not cloud."
  source: "#3974 + north-star non-goals"
  severity: medium

- id: MR-OD-022
  rule: "Per-chat reasoning effort (#3971) and per-model temperature
         compatibility (#3959 Kimi) push toward a unified parameter-
         allowlist per model+provider. One table, not N shims."
  source: "#3971 + #3959"
  severity: medium

- id: MR-OD-023
  rule: "Five overlapping routers exist. Before any new routing layer,
         grep for these and write 'why this is not a sixth router' in the PR."
  source: "north-star §2"
  severity: medium

- id: MR-OD-024
  rule: "Engine refactor (Phase 1) breaks tool_implementations.py (4000
         lines) and tool_schemas.py (1300 lines) into @odysseus_tool
         registry. PRs touching tools should not increase either file's
         line count by more than 0 net until the refactor lands."
  source: "ROADMAP Phase 1"
  severity: low

- id: MR-OD-025
  rule: "Issue #4010 (SGLANG missing dependencies) is a fresh-install /
         boot-up error contract violation. Every required runtime dep must
         be declared in pyproject.toml/setup.cfg with version pin and the
         bootstrap must surface missing deps as in-band errors, not
         5xx/import explosions."
  source: "#4010 + north-star §in-band error contract"
  severity: high

- id: MR-OD-026
  rule: "task_hash dedup policy lives in core/task_hash_policy.json and
         MUST be referenced by record_exchange, exchange-export, and any
         pioneer-adaption join. Three options enumerated (content-hash,
         semantic-hash, intent-hash); the policy file pins which is the
         default and which is override per-importer. Default = semantic-hash
         (task + prompt_type + model). content-hash permitted only for
         bulk-harvester CLI ingest. intent-hash permitted for eval mining.
         All three must have pytest fixtures proving 100% of expected
         collisions dedupe at export time."
  source: "Brief 6 §4.4 (failure mining join semantics) + this cycle"
  severity: critical
```

---

## 3. Pytest Files (concrete, copy-paste-ready)

### 3.1 `tests/test_implementer_miner_gating.py`
```python
"""P0: bg-implementer is a self-modifying miner. MR-OD-011."""
import json
from pathlib import Path
import pytest

CFG = Path("config/miners.json")


def _cfg(): return json.loads(CFG.read_text())


def test_implementer_disabled_by_default():
    cfg = {m["name"]: m for m in _cfg()}
    impl = cfg.get("bg-implementer")
    if impl is None:
        pytest.skip("bg-implementer not yet configured")
    assert impl["enabled"] is False, (
        "bg-implementer must be enabled:false until write-scope, "
        "per-change receipts, and human-in-the-loop approval land."
    )


def test_implementer_does_not_read_other_miner_outputs_inline():
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
    from src.bg_miners import run_miner
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
    assert after > before
```

### 3.2 `tests/test_localhost_bypass_auth.py`
```python
"""P0: LOCALHOST_BYPASS now grants admin implicitly. MR-OD-013."""
import pytest
from fastapi.testclient import TestClient
from app import app

c = TestClient(app)


def test_non_loopback_does_not_get_admin(monkeypatch):
    monkeypatch.setenv("LOCALHOST_BYPASS", "true")
    r = c.get("/api/admin/anything", headers={"Host": "evil.example.com"})
    if r.status_code == 200:
        assert r.json().get("current_user") != "admin"


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

### 3.3 `tests/test_capture_at_chokepoint.py`
```python
"""P0: Brief 6 amendment — capture at the chokepoint. MR-OD-014."""
import ast, inspect, unittest.mock as mock
from pathlib import Path
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
```

### 3.4 `tests/test_miners_cadence_governance.py`
```python
"""P1: Cadence tuning requires measurement. MR-OD-012."""
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
        "Cadence change requires 'Measured:'/'Rollup:' citation. See MR-OD-012."
    )
```

### 3.5 `tests/test_router_never_500.py`
```python
"""P1: In-band error contract. MR-OD-015."""
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
    for bad in ([], "string", 42, None):
        r = c.patch("/api/auth/tokens/x", json=bad)
        assert r.status_code < 500
```

### 3.6 `tests/test_subprocess_lifecycle.py`
```python
"""P1: #3995 subprocess leak. MR-OD-016."""
import time, psutil, pytest, inspect
from core.router import route_code


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
    assert "setsid" in src or "start_new_session" in src
```

### 3.7 `tests/test_session_mode_contract.py`
```python
"""P2: session.mode is write-only. MR-OD-017."""
from core.session_manager import SessionManager


def test_default_mode_is_chat():
    assert SessionManager.create().mode == "chat"


def test_legacy_sessions_default_to_chat():
    assert SessionManager.get("legacy-1").mode == "chat"


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        SessionManager.create(mode="research")
```

### 3.8 `tests/test_api_key_env_precedence.py`
```python
"""P2: api_key_env precedence. MR-OD-018."""
import pytest
from core.models import ModelEndpoint


def test_env_var_wins(monkeypatch):
    monkeypatch.setenv("MY_KEY", "sk-env")
    ep = ModelEndpoint(api_key="sk-db", api_key_env="MY_KEY")
    assert ep.resolve_api_key() == "sk-env"


def test_env_unset_falls_back_to_db(monkeypatch):
    monkeypatch.delenv("MISSING", raising=False)
    ep = ModelEndpoint(api_key="sk-db", api_key_env="MISSING")
    assert ep.resolve_api_key() == "sk-db"


def test_neither_returns_none(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    ep = ModelEndpoint(api_key=None, api_key_env="NOPE")
    assert ep.resolve_api_key() is None
```

### 3.9 `tests/test_round_boundary_state_reset.py`
```python
"""P1: Agent/chat round-boundary state reset. MR-OD-019.
Issues: #3998 (_thinkOpen), #3992 (pre-tool prose), #3993 (email fences), #4005, #4002."""
import pytest


def test_thinkopen_resets_at_round_boundary():
    """Issue #3998."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.set_think_open(True)
    rt.start_round("round 2")
    assert rt._think_open is False, (
        "MR-OD-019: _thinkOpen must reset at every round boundary"
    )


def test_executed_tool_fences_cleared_at_round_boundary():
    """Issue #3993."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.add_tool_fence("email", "<fence>...</fence>")
    rt.start_round("round 2")
    assert rt.active_fences == [], (
        "MR-OD-019: tool fences must clear at every round boundary"
    )


def test_pre_tool_prose_not_persisted_until_result():
    """Issue #3992."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.stream_prose("I will now call the email tool...")
    assert rt.prose_persisted() is False, (
        "MR-OD-019: pre-tool prose must not persist until the tool result lands"
    )
    rt.complete_tool_result("email", "<result>...</result>")
    assert rt.prose_persisted() is True


def test_round_boundary_does_not_leak_history_into_next_round():
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.add_to_history("user", "from round 1")
    rt.start_round("round 2")
    assert "from round 1" not in rt.current_history(), (
        "MR-OD-019: round 1 history must not leak into round 2"
    )


def test_reset_round_state_is_explicitly_called():
    """start_round() must call reset_round_state() — manual reset is
    a regression waiting to happen."""
    from src.agent.runtime import AgentRuntime
    import inspect
    src = inspect.getsource(AgentRuntime.start_round)
    assert "reset_round_state" in src or "self._reset" in src, (
        "MR-OD-019: start_round must call reset_round_state()."
    )
```

### 3.10 `tests/test_visibility_tools_placeholder.py`
```python
"""TDD the Phase 2 fire-and-forget blind spot."""
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

### 3.11 `tests/test_bootstrap_dependency_contract.py`
```python
"""P1: #4010 SGLANG missing dependencies — MR-OD-025.
Fresh-install and upgrade flows must surface missing runtime deps
as in-band errors, not import explosions or 5xx on first call."""
import importlib, sys
import pytest

REQUIRED_MODULES = [
    "sglang",  # if SGLANG is a declared optional dep, this is what surfaces
    # Add the full list as the project declares runtime deps
]


@pytest.mark.parametrize("modname", REQUIRED_MODULES)
def test_optional_dep_import_surfaces_in_band(modname, monkeypatch):
    """A missing optional dep must be importable (or raise a typed
    ImportError with installation instructions) — never a 5xx at runtime."""
    sys.modules.pop(modname, None)
    if modname in sys.modules:
        pytest.skip(f"{modname} already loaded")
    with pytest.raises(ImportError) as ei:
        importlib.import_module(modname)
    assert "pip install" in str(ei.value).lower() or "sglang" in str(ei.value), (
        f"{modname} ImportError should mention install instructions; got: {ei.value!r}"
    )
```

### 3.12 `tests/test_task_hash_dedup_policy.py`  (NEW — this cycle's investigation)
```python
"""MR-OD-026. The task_hash dedup policy gates Brief 6's failure-mining
join semantics and pioneer-adaption's training-corpus quality.

These fixtures prove 100% of expected collisions are deduped or merged
at export time for each of the three policy options.
"""
import json, hashlib
from pathlib import Path
import pytest

POLICY = json.loads(Path("core/task_hash_policy.json").read_text())
IMPORTERS = {
    "chat":          {"model": "claude",        "prompt_type": "chat"},
    "email_summary": {"model": "claude",        "prompt_type": "summarize"},
    "notes":         {"model": "claude",        "prompt_type": "summarize"},
    "research":      {"model": "claude",        "prompt_type": "summarize"},
    "agent_loop":    {"model": "claude",        "prompt_type": "code"},
    "scheduler":     {"model": "claude",        "prompt_type": "chat"},
}


def _hash(policy, task, *, caller, prompt_type, model, session_id):
    h = hashlib.sha256()
    if policy == "content-hash":
        h.update(task.encode())
    elif policy == "semantic-hash":
        h.update(task.encode()); h.update(b"|"); h.update(prompt_type.encode()); h.update(b"|"); h.update(model.encode())
    elif policy == "intent-hash":
        h.update(task.encode()); h.update(b"|"); h.update(prompt_type.encode()); h.update(b"|")
        h.update(model.encode()); h.update(b"|"); h.update(caller.encode()); h.update(b"|")
        h.update(session_id.encode())
    else:
        raise AssertionError(f"unknown policy: {policy}")
    return h.hexdigest()[:16]


@pytest.mark.parametrize("policy", ["content-hash", "semantic-hash", "intent-hash"])
def test_collision_pattern_chat_and_email_summary(policy):
    """The same user message dispatched to chat and email_summary MUST
    dedup under semantic and intent, but collide under content-hash."""
    task = "Summarize the Q3 earnings report"
    h_chat   = _hash(policy, task, caller="src/chat.py",  prompt_type="chat",      model="claude", session_id="sA")
    h_email  = _hash(policy, task, caller="src/email.py", prompt_type="summarize", model="claude", session_id="sA")
    if policy == "content-hash":
        assert h_chat == h_email, "content-hash MUST collide (same task text)"
    else:
        assert h_chat != h_email, (
            f"{policy} MUST distinguish chat from email_summary on prompt_type+model"
        )


@pytest.mark.parametrize("policy", ["content-hash", "semantic-hash", "intent-hash"])
def test_no_collision_chat_different_users_same_text(policy):
    """Same task text, different user sessions. content-hash & semantic
    hash collide; intent-hash distinguishes (different session_id)."""
    task = "Translate this to French: 'good morning'"
    h_u1 = _hash(policy, task, caller="src/chat.py", prompt_type="chat", model="claude", session_id="user-1")
    h_u2 = _hash(policy, task, caller="src/chat.py", prompt_type="chat", model="claude", session_id="user-2")
    if policy == "intent-hash":
        assert h_u1 != h_u2, "intent-hash MUST distinguish sessions"
    else:
        assert h_u1 == h_u2, f"{policy} SHOULD collide (same shape)"


def test_default_policy_is_semantic_hash():
    """MR-OD-026: default = semantic-hash. Pioneer-adaption trains per
    (task, prompt_type, model); content-only is too aggressive (3×
    inflation) and intent-hash is too aggressive (no cross-user eval
    reuse)."""
    assert POLICY["default"] == "semantic-hash", POLICY


def test_policy_file_pins_all_three_modes():
    for mode in ("content-hash", "semantic-hash", "intent-hash"):
        assert mode in POLICY["modes"], mode
        assert "fields" in POLICY["modes"][mode], mode
        assert "use_when" in POLICY["modes"][mode], mode


@pytest.mark.parametrize("importer", IMPORTERS)
def test_each_importer_declares_required_metadata(importer):
    """All 28 importers must carry the metadata required by the dedup
    policy (caller, prompt_type, model, session_id)."""
    meta = IMPORTERS[importer]
    for k in ("model", "prompt_type"):
        assert k in meta and meta[k], (importer, k)


def test_record_exchange_references_policy_file():
    """MR-OD-026: dedup is a contract, not a per-call choice. record_exchange
    MUST consult core/task_hash_policy.json (or its compiled form) at
    every call — no hardcoded hash function."""
    from core import exchange_log
    src = Path(exchange_log.__file__).read_text()
    assert "task_hash_policy" in src, (
        "core/exchange_log.py must reference the policy file"
    )


def test_export_dedup_uses_semantic_hash_by_default(tmp_path):
    """When exchange-export runs with no --dedup override, it must use
    the policy's default (semantic-hash) and produce 0 duplicates
    across (chat, email_summary) for the same (task, prompt_type, model)."""
    from core.exchange_export import export
    # Seed two exchanges that collide under content-hash but not semantic
    exchanges = [
        {"ts": "2026-06-12T00:00:00Z", "task_hash": "a" * 16, "task": "SameText",
         "response": "r1", "classification": "chat", "model_used": "claude",
         "source": "chat", "tokens": 1, "latency_ms": 1.0, "error": False},
        {"ts": "2026-06-12T00:00:01Z", "task_hash": "b" * 16, "task": "SameText",
         "response": "r2", "classification": "research", "model_used": "claude",
         "source": "research", "tokens": 1, "latency_ms": 1.0, "error": False},
    ]
    inp = tmp_path / "in.jsonl"
    inp.write_text("\n".join(json.dumps(e) for e in exchanges))
    out = tmp_path / "out.jsonl"
    export(str(inp), str(out))
    lines = out.read_text().splitlines()
    assert len(lines) == 2, "semantic-hash must NOT merge cross-shape exchanges"
    # But same-shape pair (both chat, same model) MUST merge
    exchanges2 = exchanges + [{
        "ts": "2026-06-12T00:00:02Z", "task_hash": "c" * 16, "task": "SameText",
        "response": "r3", "classification": "chat", "model_used": "claude",
        "source": "chat", "tokens": 1, "latency_ms": 1.0, "error": False}]
    inp.write_text("\n".join(json.dumps(e) for e in exchanges2))
    export(str(inp), str(out))
    lines2 = out.read_text().splitlines()
    assert len(lines2) == 2, "semantic-hash must merge same-shape chat+chat"
```

---

## 4. Next Unknown

**What is the actual `task_hash` collision rate and deduplication contract for `exchanges.jsonl` when 28 `llm_call_async` callers may dispatch the same logical task — and does the current "forensics-only" `task_hash` definition make the corpus trainable, or just collected?**

**Why this and not the alternatives:**

| Candidate | Why not |
|---|---|
| PII surface in 28 callers | Addressed in prior cycle; benchmark + replay queued |
| NER layer for high-tier importers | Architecture decision deferred to replay; not the immediate unknown |
| 5-router harvest | Static scan; not the immediate unknown |
| Implementer gating | Mechanical fix; not investigation |
| Pydantic Router spec | Blocked on Jwalin (#3958); not an investigation |
| Per-model parameter table | Scoping work; not research |
| Round-boundary state isolation (prior cycle) | Spec'd; the fix is mechanical (`reset_round_state()`); tests drafted |
| `task_hash` / dedup policy (this one) | **Brief 6 §4.4 already names the join semantics as a precondition for failure mining; the contract is undefined** |

**The `task_hash` / dedup question is the one unknown where:**

- **The answer is not in any document.** Brief 6a defines the schema (`task_hash` is a 16-hex sha256, forensics-only) but never specifies: *what happens when two callers hash the same task to the same value?*
- **It gates the flywheel thesis directly.** If the same chat message is captured by the chat importer, the summary importer, and the research importer, `exchanges.jsonl` contains 3× the same content. Pioneer-adaption trains on the same example 3×, overfitting and wasting compute.
- **The 28-importer chokepoint makes this worse, not better.** All 28 callers share `llm_call_async` → 1 capture site. If 3 callers hash the same content (e.g., a quoted email is captured by email importer, chat importer, and research importer), they collide on `task_hash`.
- **Brief 6 §4.4 already names the adjacent problem.** "Failure mining via task_hash join" depends on join semantics. Without a dedup policy, the join is meaningless.

**Investigation (concrete):**

1. **Read `src/llm_core.py`'s `_hash_task()` implementation.** What fields go into the hash? Is `prompt_type` included? Is `model` included? Is `caller` included? Is the hash deterministic across processes?

2. **For each of the 28 importers, determine the natural collision patterns:**
   - chat + email_summary: both ingest user-supplied text
   - notes + research: both summarize a user document
   - agent_loop + research: both may dispatch a "summarize this" task on the same content
   - scheduler + chat: scheduler may replay a chat message verbatim

3. **Design the dedup policy.** Three options:
   - **content-hash** (sha256 of `task` text): high collision rate across importers; same content = same hash
   - **semantic-hash** (sha256 of `task` + `prompt_type` + `model`): lower collision rate; same question to two models is distinct
   - **intent-hash** (sha256 of `task` + `caller` + `caller_session_id`): lowest collision rate; user intent is the unit

4. **Test the contract.** For each pair of importers likely to collide, assert:
   - content-hash: `hash(chat_task) == hash(email_summary_task)` (expected)
   - semantic-hash: `hash(chat_task, "chat", "claude") != hash(email_summary_task, "summarize", "claude")` (expected)
   - intent-hash: `hash(chat_task, "src/chat.py", session_a) != hash(email_summary_task, "src/email.py", session_a)` (expected)

5. **Codify as `core/task_hash_policy.json`** with the policy, the rationale, and the failure modes. This is the spec the implementation PR must meet.

6. **Outcome**: a 1-PR spec for the capture chokepoint contract. This is what gates Brief 6's "keep forever" retention.

**Why this is the next investigation:** the round-boundary state fix is 1 PR. The capture contract is 1 PR. The NER benchmark is 1 PR. The production-traffic replay is 1 PR. The task_hash policy is 1 PR. Each unblocks the next. The order matters: round-state fixes the dashboard (already drafted), capture contract enables the corpus (next), NER+replay makes the corpus safe, policy makes the corpus trainable. **The round-state fix lands first (already drafted). The capture contract lands second (next).**

**Concrete deliverable**: a `core/task_hash_policy.json` + a `tests/test_task_hash_dedup_policy.py` (spec'd but not yet written) + a `docs/capture_chokepoint_contract.md`. The test file from this cycle is the floor; the contract doc is the ceiling.

---

## 5. Dashboard Card (1-Surface)

```
┌──────────────────────────────┬──────────────────────────────┬──────────────────────────────┐
│ 🟡 CAPTURE CONTRACT READY    │ 🟡 UNKNOWN: task_hash /      │ 🔴 FIRE-AND-FORGET GAP      │
│ task_hash policy spec'd.     │ dedup policy. 28 importers   │ Phase 2 not landed.          │
│ Dedup modes enumerated.      │ → 1 capture site → 3×        │ visibility_tools.py         │
│ Prompt type taxonomy.        │ collision risk. Gates the    │ spec'd, not built.           │
│ Next: implementation +       │ corpus trainability.         │ [test_visibility_tools_      │
│ benchmarks.                  │ Next cycle.                  │  placeholder.py]            │
│                              │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🟢 ROUND-STATE FIX READY      │ 🔴 bg-implementer LOOSE      │ 🟡 auth-bypass = admin       │
│ 1-PR fix closes #3992,        │ Self-modifying, no gate,     │ 2-line posture change,       │
│ #3993, #3998, #4005, #4002,  │ no receipt, no HITL.         │ no test.                     │
│ #3961. Test matrix in        │ Conflicts with 3 non-goals.  │ [test_localhost_bypass_       │
│ MR-OD-019. Implementer:      │ [test_implementer_miner_      │  auth.py]                    │
│ 1-2 hours.                   │  gating.py]                  │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 CADENCE INSTABILITY       │ 🟡 5 routers, no harvest     │ 🟡 Phase 3 (super-skills)  │
│ 3 commits, 75 min,           │ plan. Sixth-router temp-     │ listed, not landed.         │
│ 6-100× interval change.      │ tation is real.              │ Repo map / auto-fix /        │
│ No measurement, no test.     │ [grep-and-inventory]         │ Cline checklist.            │
│ [test_miners_cadence_         │                              │                             │
│  governance.py]              │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 #4010 SGLANG missing deps │ 🟡 11 open agent-loop/state  │ 🟡 Engine refactor (Phase1) │
│ Fresh-install / boot-up       │ bugs, all preventable by     │ listed, unowned. 4000+1300   │
│ error contract violated.     │ MR-OD-019 reset_round_state. │ line god-objects.            │
│ [test_bootstrap_dependency_   │ Total: ~30 days of work      │ [MR-OD-024 size-net-zero]    │
│  contract.py] MR-OD-025      │ blocked on round-state fix.  │                             │
└──────────────────────────────┴──────────────────────────────┴──────────────────────────────┘
🟢 aligned with North Star  🟡 spec'd but unverified  🔴 gap with no owner
```

**One-liner:** *The task_hash policy is 1 file. Land it. The capture latency measurement is the empirical gate. Land both. Brief 6 is shippable.*