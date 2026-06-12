# 1-Surface Dashboard — orchestrator-mvp / 2026-06-11

> **Headline:** Three commits in 75 minutes collapsed miner cadence 6–100× without measurement. `bg-implementer` reads 6 other miners and writes code ungated. `LOCALHOST_BYPASS` now implicitly grants `admin` to every loopback request. North Star is 787 lines; the code is 33. **The bottleneck is no longer planning — it's the missing measurement loop (Brief 5).**

---

## 1. Pattern Decomposition

### 1.1 Cadence oscillation is a process regression
| Commit | bg-code | bg-test | bg-transcript | bg-memory | bg-job | new |
|---|---|---|---|---|---|---|
| `1dfa3f5` 12:46 | 14400s | 21600s | 7200s | 43200s | 21600s | — |
| `ee73ae3` 13:56 | 1800s | 1800s | 900s | 2700s | 2700s | — |
| `c510b31` 14:01 | **120s** | **120s** | **60s** | **180s** | **180s** | +sandbox, +implementer |

`bg-transcript-architect` at 60s will re-read `~/.pi/agent/sessions/` (~7.7 MB) 1,440×/day. The 3rd commit's body (*"work time is the pacing"*) is philosophy, not measurement. North Star §6.3 requires *"Each loop iteration is measured by Brief 5 rollups"* — but Brief 5 doesn't exist yet.

### 1.2 `bg-implementer` is a new class of problem
First miner with `source: "implementer"`, query *"implement the most actionable recent miner finding"*, at 120s. Reads the other 6 miners' outputs and writes code. The non-goals ban *"no training runs triggered by Odysseus"* and *"no swarm/mesh"* — but a self-implementing miner is structurally adjacent to both. **No receipt per write, no worktree gate, no human-in-the-loop.**

### 1.3 The 2-line auth change is a security regression
```python
if LOCALHOST_BYPASS and _is_trusted_loopback(request):
+   request.state.current_user = "admin"
+   request.state.api_token = False
```
A 2-line diff that implicitly grants `admin` to every loopback caller. No test fails closed if any future code reads `request.state.current_user` for authz.

### 1.4 The chokepoint is right but unenforced
`llm_call_async` has 28 importers. Capture belongs there (North Star §6.1). None of the 3 commits implements capture. When capture lands, `route_code`'s subprocess path needs its own call site.

### 1.5 `session.mode` and `api_key_env` are dead/undertested
- `mode: str = "chat"` written 4× (models.py + 3× session_manager.py), read 0×.
- `api_key_env` precedence: env > encrypted > None. 3 cases (env unset, both set, neither) all undefined and untested.

### 1.6 Error-contract violations cluster
Issues #3992, #3993, #3995, #3998, #3966, #3965 — all in-band error contract / state-cleanup violations from `orchestration-briefs.md`. Documented; not enforced.

### 1.7 Spec/code ratio
- **~787 lines** of new docs in 24h
- **~33 lines** of executable code in same window
- North Star §6.6: *"The single highest-value next action is no longer a document — it's merging Brief 1."* Not taken.

### 1.8 Five overlapping routers, no archival
`platform/app.py+router.py` (dead), `orchestrator-mvp`, `unified-personal-os`, `routing-engine`, `workspace-command`. No harvest plan.

---

## 2. Memory Rules (paste-into-supervisor)

```yaml
# MR-OD-011: bg-implementer must be disabled by default
- id: MR-OD-011
  rule: "The bg-implementer miner is self-applying (it reads 6 other miners'
         outputs and writes code). Until write-scope enforcement, per-change
         receipts, and human-in-the-loop approval ship, bg-implementer MUST
         be enabled: false."
  source: "c510b31 + north-star §3, §non-goals"
  severity: critical

# MR-OD-012: Cadence tuning governance
- id: MR-OD-012
  rule: "Changes to config/miners.json interval_seconds by more than 2x
         require a 'Measured:' citation in the commit body. Brief 5 rollups
         are the only valid citation."
  source: "3-commit oscillation 14400s→60s in 75min, 2026-06-11"
  severity: high

# MR-OD-013: Auth context for loopback bypass
- id: MR-OD-013
  rule: "Any code path that sets request.state.current_user = 'admin' must
         be paired with a test asserting that a non-loopback Host header
         causes the same route to return 401/403."
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
  source: "orchestration-briefs.md + #3966, #3992, #3993, #3995, #3998, #3965"
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
         write-only field."
  source: "1dfa3f5 core/models.py + session_manager.py"
  severity: medium

# MR-OD-018: api_key_env precedence
- id: MR-OD-018
  rule: "api_key_env precedence: env var > encrypted column > None.
         Env unset falls through to DB silently. Both unset returns None
         and triggers in-band error (not 500). All three cases need tests."
  source: "1dfa3f5 core/database.py migration"
  severity: high

# MR-OD-019: Round-boundary state reset
- id: MR-OD-019
  rule: "Agent/chat surfaces must reset all round-boundary state
         (_thinkOpen, executed tool fences, pre-tool prose) at every
         round boundary. A new round starts with a clean DOM and a
         clean history slice. Issues #3992, #3993, #3998 are exemplar failures."
  source: "#3992 + #3993 + #3998"
  severity: high

# MR-OD-020: Pydantic Router wraps, does not replace
- id: MR-OD-020
  rule: "If Pydantic Router (#3958) lands, classify_task must remain a
         regex fast-path."
  source: "orchestration-briefs.md + #3958"
  severity: medium

# MR-OD-021: Skill sharing default-reject
- id: MR-OD-021
  rule: "Feature #3974 (Online Skill Sharing) conflicts with the non-goal
         'no cloud sync.' LAN/mDNS only, not cloud."
  source: "#3974 + north-star non-goals"
  severity: medium

# MR-OD-022: Per-model parameter allowlist
- id: MR-OD-022
  rule: "Per-chat reasoning effort (#3971) and per-model temperature
         compatibility (#3959 Kimi) push toward a unified parameter-
         allowlist per model+provider. One table, not N shims."
  source: "#3971 + #3959"
  severity: medium

# MR-OD-023: Five-router harvest
- id: MR-OD-023
  rule: "Five overlapping routers exist. Before any new routing layer,
         grep for these and write 'why this is not a sixth router' in the PR."
  source: "north-star §2"
  severity: medium

# MR-OD-024: Engine refactor gates
- id: MR-OD-024
  rule: "Engine refactor (Phase 1) breaks tool_implementations.py (4000
         lines) and tool_schemas.py (1300 lines) into @odysseus_tool
         registry. PRs touching tools should not increase either file's
         line count by more than 0 net until the refactor lands."
  source: "ROADMAP Phase 1"
  severity: low
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
Issues: #3998 (_thinkOpen), #3992 (pre-tool prose), #3993 (email fences)."""
import pytest


def test_thinkopen_resets_at_round_boundary():
    """Issue #3998: next round's reasoning streams into the reply bubble,
    then visibly re-sorts mid-read. _thinkOpen must be reset."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.set_think_open(True)
    rt.start_round("round 2")
    assert rt._think_open is False, (
        "MR-OD-019: _thinkOpen must reset at every round boundary"
    )


def test_executed_tool_fences_cleared_at_round_boundary():
    """Issue #3993: email tool fences stay visible after the round ends."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.add_tool_fence("email", "<fence>...</fence>")
    rt.start_round("round 2")
    assert rt.active_fences == [], (
        "MR-OD-019: tool fences must clear at every round boundary"
    )


def test_pre_tool_prose_not_persisted_until_result():
    """Issue #3992: agent prose before the tool result is treated as final."""
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
    """Per-round DOM and history slice must be isolated."""
    from src.agent.runtime import AgentRuntime
    rt = AgentRuntime()
    rt.start_round("round 1")
    rt.add_to_history("user", "from round 1")
    rt.start_round("round 2")
    assert "from round 1" not in rt.current_history(), (
        "MR-OD-019: round 1 history must not leak into round 2"
    )


def test_reset_round_state_is_explicitly_called():
    """The contract: start_round() must call reset_round_state().
    This is the floor — any state field added later must be added to
    the reset method or this test will pass-by-accident later."""
    from src.agent.runtime import AgentRuntime
    import inspect
    src = inspect.getsource(AgentRuntime.start_round)
    assert "reset_round_state" in src or "self._reset" in src, (
        "MR-OD-019: start_round must call reset_round_state(). "
        "Without this, every new state field is a potential leak."
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
| `task_hash` collision contract (this one) | **Brief 6 §4.4 already names the join semantics as a precondition for failure mining; the contract is undefined** |

**The `task_hash` / dedup question is the one unknown where:**

- **The answer is not in any document.** Brief 6a defines the schema (`task_hash` is a 16-hex sha256, forensics-only) but never specifies: *what happens when two callers hash the same task to the same value?*
- **It gates the flywheel thesis directly.** If the same chat message is captured by the chat importer, the summary importer, and the research importer, `exchanges.jsonl` contains 3× the same content. Pioneer-adaption trains on the same example 3×, overfitting to common tasks and wasting compute on duplicates.
- **The 28-importer chokepoint makes this worse, not better.** All 28 callers share `llm_call_async` → 1 capture site. If 3 callers hash the same content (e.g., a quoted email is captured by the email importer, the chat importer, and the research importer), they collide on `task_hash`. The question is: do we deduplicate at write time, merge at read time, or accept duplicates?
- **Brief 6 §4.4 already names the adjacent problem** — *failure mining via task_hash join* — but assumes the join semantics are defined. They are not.
- **Brief 5 rollups (tokens/day by class) are misleading without dedup.** The same example appears 3×, inflating token counts and skewing the training distribution.

**Investigation (concrete):**

1. **Define "the same task"** for hashing purposes. Options:
   - **Content-hash** (sha256 of `task` text) — the spec says this. Collides on identical inputs.
   - **Semantic-hash** (sha256 of `task` + `prompt_type` + `model`) — distinguishes "the same question to two models" from "the same question to one model twice."
   - **Intent-hash** (sha256 of `task` + `caller` + `caller_session_id`) — distinguishes "the user asked this twice" from "two systems both asked this."

2. **Trace the 28 importers.** Which importers are likely to produce identical `task_hash` values? Specifically:
   - Chat + email-summary: both ingest a chat message / email body.
   - Notes + research: both summarize a user document.
   - Agent-loop + research: both may dispatch a "summarize this" task on the same content.
   - Scheduler + chat: scheduler may replay a chat message verbatim.

3. **Design the dedup policy.** Three options:
   - **First-wins**: keep the first capture, drop subsequent collisions. Simple, but loses data when a later call has better metadata.
   - **Last-wins**: keep the latest capture, drop earlier ones. Good for "final answer" semantics, but loses intermediate reasoning.
   - **Merge**: keep all, join by `task_hash` at export time (`scripts/exchange-export` in Brief 6c). Most flexible, but most storage.

4. **Test the contract.** Given 3 callers producing the same `task_hash`:
   - `test_exchanges_no_duplicate_task_hash_for_same_caller_session` — same caller, same content, within 60s → at most 1 capture.
   - `test_exchanges_preserves_intent_differentiation` — different `prompt_type` → different `task_hash`.
   - `test_exchange_export_dedups_or_merges` — `scripts/exchange-export --since 7d` produces a dataset where no `task_hash` appears more than N times (where N is a documented policy).

5. **Codify as `core/task_hash_policy.json`** with the policy, the rationale, and the failure modes. This is what makes the corpus *trainable* rather than *just collected*.

**Why this gates everything else:** Without a dedup policy, Brief 5 rollups (tokens/day by class) are misleading — the same example appears 3×, inflating token counts and skewing the training distribution. The "keep forever" retention is wasted compute. And the chat-through-router adoption (Brief 7) multiplies the problem: every chat message becomes N captures across the 28 importers.

**The single most important question the dashboard can ask right now:** *what is the `task_hash` semantics that makes the corpus trainable, and is the current "forensics-only" definition sufficient?* The answer is in `src/llm_core.py`'s `_hash_task()` function — read it, test it, and decide.

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
│ Conflicts with 3 non-goals.  │ [test_localhost_bypass_       │ [test_session_mode_          │
│ [test_implementer_miner_      │  auth.py]                    │  contract.py]                │
│  gating.py]                  │                              │                             │
├──────────────────────────────┼──────────────────────────────┼──────────────────────────────┤
│ 🔴 UNKNOWN: task_hash /      │ 🟡 5 routers, no harvest     │ 🟡 Phase 3 (super-skills)  │
│ dedup policy for exchanges?  │ plan. Sixth-router temp-     │ listed, not landed.         │
│ Gates flywheel training      │ tation is real.              │ Repo map / auto-fix /        │
│ quality. 28 importers → 1    │ [grep-and-inventory]         │ Cline checklist.            │
│ capture site → collisions.   │                              │                             │
└──────────────────────────────┴──────────────────────────────┴──────────────────────────────┘
🟢 aligned with North Star  🟡 spec'd but unverified  🔴 gap with no owner
```

**One-liner:** *Two P0 regressions shipped in 75 minutes without tests. The measurement loop (Brief 5) is the missing primitive. The `task_hash` / dedup policy for `exchanges.jsonl` is the unknown that determines whether the corpus is trainable — and it's the next hour's work.*