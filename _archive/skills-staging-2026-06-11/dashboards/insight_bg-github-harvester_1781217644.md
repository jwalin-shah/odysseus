<think>
The user wants me to analyze the recent commits and GitHub issues for the orchestrator-mvp project, decompose patterns/errors/insights, write specific pytest files or Memory Rules, and identify the next Unknown. This is the same research mission as before with the same data.

Let me think carefully about what to provide. The user wants:
1. Pattern decomposition
2. Specific Pytest files or Memory Rules
3. Next Unknown to investigate
4. Report for 1-Surface dashboard

The data I have shows:
- 3 recent commits in ~75 minutes (12:46, 13:56, 14:01) all touching miner cadence
- Initial commit: 7200-43200s intervals (hours)
- Second commit: 1800-2700s (30-45 min) - "aggressive"
- Third commit: 60-180s (1-3 min) - "continuous mode", adds 2 new miners (sandbox-architect, implementer)
- The third commit also doesn't end with a newline
- Commit 1dfa3f5 added: config-driven miners, agent_histories source, session.mode field, api_key_env column, LOCALHOST_BYPASS now grants admin
- Two new docs: odysseus-north-star.md (280 lines) and orchestration-briefs.md (507 lines)
- ROADMAP.md updates: Engine Refactor Phase 1 (god files), Task Visibility Phase 2, Advanced Agent Super-Skills Phase 3
- 21 GitHub issues covering: error contract violations, subprocess lifecycle, model compatibility, test bloat, UI bugs

Let me decompose patterns:

**Pattern 1: Cadence Instability** - 3 commits in 75min oscillating cadence 6-100x. The "M3 is free" commit message reveals philosophy-driven tuning not measurement-driven.

**Pattern 2: The Implementer Miner is dangerous** - bg-implementer with `source: "implementer"` is the first self-modifying miner. The north-star doc says "no training runs triggered by Odysseus" and "no swarm/mesh" — but a miner that reads findings and writes code is adjacent to both.

**Pattern 3: Auth-bypass now grants admin implicitly** - The `request.state.current_user = "admin"` line means any future code that reads request.state for authz will silently grant admin from any local port. No test exists.

**Pattern 4: llm_call_async is the right capture chokepoint, but unenforced** - The north-star §6.1 nails the architecture. But the diffs haven't implemented capture at all - it's a doc, not code.

**Pattern 5: Session mode = dead field** - Written in 4 places, read in 0 places. Pure migration cost with no consumer.

**Pattern 6: api_key_env precedence is undocumented and untested** - Three cases undefined: both set, env unset, both unset. The migration just adds the column.

**Pattern 7: The "fire-and-forget" gap is real** - Phase 2 work is documented but not started. With 7 miners firing every 60-180s, the firehose is on but no visibility tools exist.

**Pattern 8: Issue cluster - error contract violations** - #3992, #3993, #3995, #3966, #3965 are all violations of the in-band error contract from orchestration-briefs.md.

**Pattern 9: The spec-rich / code-poor tension** - 787 lines of new docs (north-star + briefs) but actual implementation is just cadence tuning. The "honest stop" line in north-star §6.6 says execution is the constraint - this is consistent with that, but also reveals the team writes better plans than code.

**Pattern 10: Five overlapping routers** - North-star §2 explicitly names them. This is a meta-architectural problem: "the failure mode on this Mac is not missing capability — it's starting a sixth router."

**Abandoned refactors:**
- CSS cleanup (in roadmap for multiple commits)
- tour-core.js helper (in roadmap for multiple commits)
- tool_implementations.py split (4000 lines) - just added to roadmap, not started
- chariot-router-go - explicitly parked
- 5 archived routers - no harvest plan
- Modal/window positioning cleanup - in roadmap, not touched

**Regressions:**
- Cadence instability (3 commits, 4 hours)
- Auth-bypass admin grant (no test, security posture change)
- session.mode = dead data
- 5 error contract violations in the issues

**Next Unknown:** I should think about what would have the highest leverage.

Options:
1. What's the actual signal quality of miner returns at different cadences? - measurement problem
2. What's the actual shape of task_scheduler.py completion events? - needed for visibility_tools.py
3. What ideas from the 5 archived routers are worth harvesting? - architecture
4. What's the actual PII surface of the 28 llm_call_async callers? - privacy/security
5. Is the implementer miner actually safe? - safety
6. What's the actual failure rate of subprocesses (the #3995 issue)? - reliability
7. What's in the pioneer-adaption datasets that Adaption expects? - needed for the export

The cadence measurement question is the highest leverage because:
- It's a measurement problem blocking multiple decisions
- The team is shipping cadence changes 6-100x without data
- The flywheel thesis depends on it
- It's the only one that requires external investigation (the others can be answered by reading code)

Wait, I should also think about the implementer miner since it was just added and is a self-modifying system. That's a significant safety concern. The user just shipped a self-applying miner with no gating.

Let me think about which is MORE important: cadence measurement or implementer safety.

The implementer is the first miner with a write capability. It reads its own findings and writes code. That's an unbounded blast radius. The cadence question is about quality. The implementer is about safety.

Actually, the implementer might be the higher priority because:
- It was just shipped
- It has no test
- It has no receipt
- It has no human-in-the-loop
- It violates the spirit of the non-goals ("no training runs triggered by Odysseus")
- It could be writing to ANY path right now

But the user said this is for the 1-Surface dashboard. The dashboard needs actionable signals, not "go investigate."

Let me think about what's most useful. I'll structure the response as:
1. Pattern decomposition (10 insights)
2. Pytest files to add (concrete)
3. Memory rules (concrete)
4. Next unknown

For the Next Unknown, I think cadence measurement is actually the most leveraged, BUT the implementer miner safety is more urgent. The dashboard should show BOTH.

Actually, let me re-read the task: "Identify the next 'Unknown' we should investigate."

I should pick ONE. Let me pick the highest-leverage one.

The cadence question is blocking multiple decisions. The implementer question is blocking one decision (gate it or remove it).

The cadence question wins. Without measurement, the next 5 commits will keep oscillating. The implementer question can be answered with code (add a test, add a gating hook) without investigation.

Let me write the report.

Actually wait, the user said "We just finished a research pass" and "TASK: 1. Decompose... 2. Write... 3. Identify..."

So they want a full report. Let me write it.

I should be concrete and specific. The dashboard needs signals it can act on.

Let me structure:

# Synthesis Report — 2026-06-11 PM

## 1. Pattern Decomposition

### 1.1 Cadence oscillation
[the 3-commit story]

### 1.2 Implementer miner = first self-modifying miner
[the safety concern]

### 1.3 Auth-bypass now grants admin implicitly
[the security concern]

### 1.4 The chokepoint is correct but unenforced
[the gap between doc and code]

### 1.5 Session mode = dead field
[data with no consumer]

### 1.6 api_key_env precedence is undocumented
[3 cases undefined]

### 1.7 Fire-and-forget gap, now urgent
[7 miners, no visibility tools]

### 1.8 Five overlapping routers
[meta-architectural concern]

### 1.9 Error contract violations cluster
[#3992, #3993, #3995, #3966, #3965]

### 1.10 Spec-rich / code-poor tension
[787 lines of docs, no capture implementation]

## 2. Regressions & Abandoned Refactors

| Type | Item | Evidence |
|---|---|---|
| Regression | Cadence instability | 3 commits in 75min, 6-100x range |
| Regression | Auth-bypass admin | 1dfa3f56 app.py diff, no test |
| Regression | Session.mode = dead data | 4 writers, 0 readers |
| Regression | Error contract | 5 issues |
| Abandoned | CSS cleanup | Roadmap, multiple commits untouched |
| Abandoned | tour-core.js | Roadmap, untouched |
| Abandoned | tool_implementations split | Just added to roadmap, not started |
| Abandoned | chariot-router-go | Explicitly parked |
| Abandoned | 5 archived routers | No harvest plan |

## 3. Memory Rules to Add

[concrete rules]

## 4. Pytest Files to Write

[concrete files]

## 5. Next Unknown

[the cadence measurement question]

Let me write this out now.

Actually, I realize I need to be careful about format. The user wants something usable for the 1-Surface dashboard. Let me make this scannable and actionable.

Let me think about the pytest files more carefully. I should write actual working code, not stubs.

For test_miner_cadence_governance.py:
- Test that intervals are within bounds
- Test that the commit message includes a measurement citation when cadence changes

For test_auth_localhost_bypass.py:
- Test that non-loopback requests don't get admin

For test_session_mode_contract.py:
- Test that legacy sessions default to "chat"
- Test that mode persists

For test_api_key_env_precedence.py:
- Test env > db > none

For test_capture_at_chokepoint.py (Brief 6 prep):
- Test that llm_call_async eventually calls record_exchange
- Test that route_code also calls record_exchange

For test_router_never_500.py:
- Test all dispatch surfaces never 5xx

For test_visibility_tools_placeholder.py:
- TDD Phase 2 work

For test_pydantic_router_compat.py:
- Test that Pydantic Router doesn't replace regex-first

Memory rules should be specific, actionable, and sourced.

Let me write the report now.

I'll aim for comprehensive but scannable. The 1-Surface dashboard needs to display this as cards/panels.

One more thing - I should look at issue #3992 and #3993 carefully:
- #3992: "Agent persists pre-tool prose before the real tool result" - this is a state-leak bug in the chat rendering
- #3993: "Live chat leaves executed email tool fences visible until reload" - same pattern, UI state not cleared
- #3995: "stopping a local Windows cookbook download leaves orphaned hf/python processes that deadlock every retry on the HF cache locks" - subprocess lifecycle, especially on Windows (different signals)

These all point to the same root cause: state machine bugs at the boundaries (chat render, subprocess cleanup, error contract).

#3992 and #3993 are both chat UI bugs. They suggest the chat render pipeline has a state-cleanup gap. This is a new pattern: the "1-Surface" rendering layer is leaking state across operations.

Let me add this as a pattern.

For #3995 - "orphaned hf/python processes" - this is the same risk Brief 2 (worktree isolation) doesn't solve. Worktrees isolate FILESYSTEM but not PROCESSES. The north-star doc should mention process group cleanup as part of Brief 2.

OK let me write the report.
</think>

# 1-Surface Synthesis — orchestrator-mvp / 2026-06-11 PM cycle

## 1. Pattern Decomposition

### 1.1 Cadence oscillation (3 commits in 75 min)
The `interval_seconds` field walked 14400s → 1800s → 60–180s in three commits citing zero measurements. Commit `c510b31`'s body ("work time is the pacing") is a philosophy, not a metric. The 60s `bg-transcript-architect` will re-read the same `~/.pi/agent/sessions/` JSONL roughly 1440×/day.

### 1.2 The implementer miner = first self-modifying miner
`bg-implementer` (`source: "implementer"`) reads recent miner findings and writes code. The North Star's non-goals explicitly ban "no training runs triggered by Odysseus" and "no swarm/mesh." A miner that reads its own findings and emits diffs is adjacent to both. **No receipt per emitted change, no write-scope enforcement, no human-in-the-loop hook, no test asserting any of the above.**

### 1.3 LOCALHOST_BYPASS now grants admin implicitly
`1dfa3f56` adds `request.state.current_user = "admin"` + `api_token = False` on the bypass branch. The comment warns about network-exposed deployments, but no test fails closed if a future change reads `request.state.current_user` for authz. A 2-line diff ships a security posture change.

### 1.4 The 28-callers chokepoint is right but unenforced
North Star §6.1 nails the architecture: capture goes in `llm_call_async`, not the router. None of the three commits implements capture. The doc is the spec, not the build. When capture lands, `route_code`'s subprocess path will need its own call site (Brief 6a) — currently a known gap, not addressed.

### 1.5 `session.mode` = dead field with migration cost
Written in 4 places (`core/models.py`, 3× in `core/session_manager.py`), read in 0. The next PR that adds a mode consumer will discover empty data for legacy sessions. No backfill.

### 1.6 `api_key_env` precedence is undefined in 3 cases
The docstring says "takes precedence over `api_key`" but never defines: (a) `api_key_env` set, env var unset at request time → silent fail? 500? in-band? (b) both populated → "env wins" claimed, untested. (c) migration doesn't validate existing rows.

### 1.7 Chat-UI state leaks (issues #3992, #3993, #3961)
Three of the 21 open issues describe the same shape: agent/chat surfaces leave stale state in the live UI (pre-tool prose, executed email fences, utility model not invoked for memory extraction). The "1-Surface" layer has a state-cleanup gap, distinct from the router contract.

### 1.8 Subprocess lifecycle (#3995) ≠ worktree isolation (Brief 2)
Worktrees isolate filesystem, not processes. The Windows cookbook download leaves orphaned `hf`/`python` processes that deadlock HF cache locks — Brief 2 will not catch this. `kill -9` on the parent + process-group reap is not in any spec.

### 1.9 Spec-rich / code-poor
~787 lines of new docs (`odysseus-north-star.md` + `orchestration-briefs.md`) in 24h; actual implementation this cycle is a 7-miner config + 1 column add + 2 auth lines. The North Star §6.6 "honest stop" acknowledges this — but the dashboard needs to show the ratio trending.

### 1.10 Five overlapping routers (meta)
North Star §2 names them: `platform/app.py+router.py`, `orchestrator-mvp`, `unified-personal-os`, `routing-engine`, `workspace-command`. No harvest plan, no archival move. The "fifth router risk" is the single most repeated warning in the corpus.

---

## 2. Regressions & Abandoned Refactors

| # | Type | Item | Evidence | Severity |
|---|---|---|---|---|
| R1 | **Regression** | Cadence instability | 3 commits, 6–100× range, no metric | 🟠 high — blocks Brief 5 |
| R2 | **Regression** | Auth-bypass = admin | `1dfa3f56` 2-line diff, no test | 🔴 critical — security posture |
| R3 | **Regression** | `session.mode` = dead data | 4 writers, 0 readers | 🟡 med — migration rot |
| R4 | **Regression** | Error-contract violations | #3992, #3993, #3995, #3966, #3965 | 🔴 critical — router contract |
| R5 | **Regression** | Subprocess lifecycle | #3995 (orphaned hf/python) | 🟠 high — Brief 2 blind |
| R6 | **Regression** | Implementer miner unguarded | `c510b31`, no write-scope, no receipt | 🔴 critical — self-modification |
| R7 | Abandoned | `tool_implementations.py` split (4000 lines) | Just added to ROADMAP, not started | 🟡 med — god-file spread |
| R8 | Abandoned | `chariot-router-go` | "Parked, do not integrate now" — no archival | 🟢 low — explicitly deferred |
| R9 | Abandoned | 5 archived routers | No harvest plan | 🟠 high — sixth-router risk |
| R10 | Abandoned | CSS cleanup, tour-core.js | In ROADMAP across multiple commits | 🟢 low — cosmetic |
| R11 | Abandoned | Pydantic Router (#3958) | "needs more info" | 🟡 med — pending spec |
| R12 | Abandoned | Online Skill Sharing (#3974) | Conflicts with non-goal "no cloud sync" | 🟠 high — needs rejection |

---

## 3. Pytest files to add (concrete, copy-pasteable)

### 3.1 `tests/test_miners_cadence_governance.py`
```python
"""Lock the cadence tuning loop. Cadence changes without measurement are a
process regression. Source: synthesis 2026-06-11 PM, R1."""
import json, re, subprocess
from pathlib import Path
import pytest

REPO = Path(__file__).resolve().parents[1]
CFG = REPO / "config" / "miners.json"
MIN_S, MAX_S = 30, 86_400
ALLOWED = {"name", "query", "interval_seconds", "source", "enabled"}

def _cfg():
    return json.loads(CFG.read_text())

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
            "transcript re-reads MB-scale JSONL; if it cycles faster than "
            "githits it is over-cycling the same source files"
        )

def test_cadence_change_cites_measurement():
    """If config/miners.json changed in HEAD, the commit body must cite a
    measurement. Prevents vibes-cadence. See R1."""
    msg = subprocess.check_output(
        ["git", "log", "-1", "--format=%b", "--", "config/miners.json"],
        cwd=REPO, text=True
    )
    diff = subprocess.run(
        ["git", "diff", "--quiet", "HEAD~1", "--", "config/miners.json"],
        cwd=REPO
    )
    if diff.returncode == 0:
        pytest.skip("no diff against HEAD~1")
    assert re.search(r"(?i)(measured|rollup|brief[- ]?5|baseline)", msg), (
        "Cadence change in config/miners.json must cite measurement "
        "(Measured:/Rollup:/Brief-5/Baseline) in the commit body"
    )
```

### 3.2 `tests/test_auth_localhost_bypass.py`
```python
"""LOCALHOST_BYPASS implies admin. Any code path that reads request.state
authorization must be tested against a non-loopback request. Source: R2."""
import os, pytest
from fastapi.testclient import TestClient
from app import app

c = TestClient(app)

@pytest.mark.parametrize("bad", [{}, [], "string", 42, None])
def test_admin_endpoint_rejects_when_no_auth(monkeypatch, bad):
    monkeypatch.setenv("LOCALHOST_BYPASS", "false")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    r = c.get("/api/admin/anything", json=bad)
    assert r.status_code in (401, 302, 303, 307), r.status_code

def test_non_loopback_host_does_not_get_admin(monkeypatch):
    monkeypatch.setenv("LOCALHOST_BYPASS", "true")
    r = c.get("/api/admin/anything", headers={"Host": "evil.example.com"})
    if r.status_code == 200:
        assert r.json().get("current_user") != "admin", (
            "Non-loopback host inherited admin from LOCALHOST_BYPASS"
        )
```

### 3.3 `tests/test_session_mode_contract.py`
```python
"""session.mode = 'chat' is the only mode with consumers today. New modes
need a consumer in the same PR or the field is dead data. Source: R3."""
from core.session_manager import SessionManager

def test_mode_persists_round_trip(tmp_db):
    s = SessionManager.create(mode="research")
    s.save()
    assert SessionManager.get(s.id).mode == "research"

def test_legacy_session_defaults_to_chat(tmp_db):
    """Pre-migration rows have no mode column; reads must default to 'chat'."""
    row = tmp_db.execute(
        "INSERT INTO sessions (id, owner, message_count) VALUES (?,?,?)",
        ("legacy-1", "admin", 0)
    )
    assert SessionManager.get("legacy-1").mode == "chat"
```

### 3.4 `tests/test_api_key_env_precedence.py`
```python
"""Codify the precedence env > encrypted > None. Three cases otherwise
undefined. Source: §1.6."""
import pytest
from core.models import ModelEndpoint  # adjust

@pytest.fixture
def ep(): return ModelEndpoint(name="x", api_key=None, api_key_env=None)

def test_env_var_wins(monkeypatch, ep):
    monkeypatch.setenv("MY_KEY", "sk-env")
    ep.api_key = "sk-db"
    ep.api_key_env = "MY_KEY"
    assert ep.resolve_api_key() == "sk-env"

def test_env_unset_falls_back_to_db(monkeypatch, ep):
    monkeypatch.delenv("MISSING", raising=False)
    ep.api_key = "sk-db"
    ep.api_key_env = "MISSING"
    assert ep.resolve_api_key() == "sk-db"

def test_neither_returns_none_and_never_500s(monkeypatch, ep):
    monkeypatch.delenv("NOPE", raising=False)
    ep.api_key = None
    ep.api_key_env = "NOPE"
    assert ep.resolve_api_key() is None
    # And: the dispatch that uses this endpoint returns in-band error,
    # not 500. Tested separately in test_router_never_500.py.
```

### 3.5 `tests/test_implementer_miner_gating.py`
```python
"""bg-implementer is a self-modifying miner. It must be gated by write-scope
enforcement, emit a receipt per change, and refuse to touch files outside
an isolated worktree. Source: R6."""
import os, pytest, json
from pathlib import Path
from src.bg_miners import run_miner  # adjust

def test_implementer_never_writes_outside_worktree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ODYSSEUS_WORKTREE", str(tmp_path / "wt"))
    # Pre-seed a "finding" the implementer would consume
    (tmp_path / "wt").mkdir()
    run_miner("bg-implementer")
    writes = [p for p in tmp_path.rglob("*") if p.is_file()]
    for w in writes:
        assert w.is_relative_to(tmp_path / "wt"), f"out-of-worktree write: {w}"

def test_implementer_emits_receipt(tmp_path, monkeypatch):
    receipts = []
    monkeypatch.setattr("core.orchestration_trace.record_trace",
                        lambda **kw: receipts.append(kw))
    run_miner("bg-implementer")
    assert any(r.get("source") == "miner:bg-implementer" for r in receipts)

def test_implementer_requires_human_token_for_non_worktree_targets(tmp_path):
    """If the finding names a path outside the worktree, the miner must
    refuse without ODYSSEUS_APPROVAL_TOKEN in env."""
    os.environ.pop("ODYSSEUS_APPROVAL_TOKEN", None)
    with pytest.raises(PermissionError):
        run_miner("bg-implementer", finding_path="/etc/hosts")
```

### 3.6 `tests/test_capture_at_chokepoint.py`
```python
"""Brief 6 amendment: capture fires in llm_call_async, not just the router.
llm_call_async has 28 importers. This test fails if capture is bolted onto
the router alone. Source: §1.4."""
import ast, inspect
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]

def test_llm_core_calls_record_exchange():
    src = (REPO / "src" / "llm_core.py").read_text()
    assert "record_exchange" in src, (
        "src/llm_core.py does not call record_exchange. "
        "Brief 6 amendment requires capture at the chokepoint (28 importers)."
    )

def test_route_code_subprocess_path_also_captures():
    src = (REPO / "core" / "router.py").read_text()
    assert "record_exchange" in src, (
        "core/router.py route_code subprocess path bypasses llm_call_async "
        "and must call record_exchange separately"
    )

def test_record_exchange_never_raises(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_EXCHANGE_DIR", "/dev/full/exchanges")
    from core.exchange_log import record_exchange
    # must not raise even if writing fails
    record_exchange(task="x", response="y")

def test_kill_switch_disables_writes(monkeypatch):
    monkeypatch.setenv("ODYSSEUS_NO_CAPTURE", "1")
    from core.exchange_log import record_exchange
    import unittest.mock as mock
    with mock.patch("builtins.open", side_effect=AssertionError("written")):
        record_exchange(task="x", response="y")
```

### 3.7 `tests/test_router_never_500.py`
```python
"""In-band error contract: dispatch surfaces must never 5xx. Source: R4."""
import pytest
from fastapi.testclient import TestClient
from app import app
c = TestClient(app)

DISPATCH = [
    ("post", "/api/route", {"task": "hello"}),
    ("post", "/api/route", {}),
    ("post", "/api/route", {"task": "x" * 1_000_000}),
    ("post", "/api/route/code", {"task": "ls"}),
]

@pytest.mark.parametrize("method,path,body", DISPATCH)
def test_dispatch_never_5xx(method, path, body):
    r = getattr(c, method)(path, json=body)
    assert r.status_code < 500, (path, body, r.status_code, r.text[:300])
    if r.status_code == 200 and not body.get("task"):
        assert r.json().get("error") is True
```

### 3.8 `tests/test_visibility_tools_placeholder.py`
```python
"""TDD Phase 2 (fire-and-forget blind spot). Currently FAILS — that's the
point. Source: R-ROADMAP-Phase-2, §1.7."""
import pytest

async def test_get_research_report_returns_recent_miner_findings():
    from src.visibility_tools import get_research_report
    r = await get_research_report(window_seconds=600)
    assert r.findings, "no miner findings surfaced in last 10 min"
    assert all(f.source.startswith("miner:") for f in r.findings)

async def test_get_shell_job_status_links_to_active_session():
    from src.visibility_tools import get_shell_job_status
    s = await get_shell_job_status(job_id="latest")
    assert s.session_id  # auto-injected into the calling session
```

### 3.9 `tests/test_subprocess_lifecycle.py`
```python
"""Subprocesses spawned for code tasks must not leak. Source: R5, #3995."""
import subprocess, time, pytest, psutil
from core.router import route_code  # adjust

def test_route_code_reaps_descendants_on_timeout(monkeypatch, tmp_path):
    before = {p.pid for p in psutil.process_iter()
              if "python" in (p.name() or "").lower()}
    with pytest.raises(Exception):
        route_code(task="sleep 60", cwd=tmp_path, timeout=2)
    time.sleep(2)
    after = {p.pid for p in psutil.process_iter()
             if "python" in (p.name() or "").lower()}
    assert not (after - before), "orphaned python pids after timeout"
```

### 3.10 `tests/test_pydantic_router_compat.py`
```python
"""Pydantic Router (#3958) must wrap, not replace, the regex-first
classifier. Source: orchestration-briefs.md, §1.4 of synthesis."""
import pytest
from core.router import classify_task  # adjust

def test_regex_first_does_not_call_llm_for_clear_code(monkeypatch):
    called = []
    monkeypatch.setattr("core.router._cheap_llm_classify",
                        lambda *a, **k: called.append(1) or "code")
    assert classify_task("Write a Python function to parse JSON") == "code"
    assert not called

def test_async_tiebreak_only_on_ambiguous(monkeypatch):
    called = []
    monkeypatch.setattr("core.router._cheap_llm_classify",
                        lambda *a, **k: called.append(1) or "chat")
    monkeypatch.setattr("core.router._is_ambiguous", lambda t: "maybe" in t)
    classify_task("hello there")
    classify_task("maybe do something")
    assert len(called) == 1
```

---

## 4. Memory Rules to add to supervisor

```yaml
- id: MR-OD-001
  rule: "Cadence changes to config/miners.json require a 'Measured:' or 'Rollup:'
         line in the commit body. Without it the commit is a process regression
         and must not merge."
  source: "3-commit oscillation 2026-06-11, 14400s→60s in 75min"

- id: MR-OD-002
  rule: "In-band error contract: /api/route and any dispatch surface must NEVER
         return 5xx. Timeout, missing CLI, stale quota, bad JSON body all
         become {error: true, response: <truncated>}. Tested by
         test_router_never_500.py."
  source: "orchestration-briefs.md + issues #3966, #3992, #3995"

- id: MR-OD-003
  rule: "Capture site = llm_call_async (28 importers) PLUS route_code subprocess
         path. Both call sites updated together. Drift between them = corpus gaps."
  source: "odysseus-north-star.md §6.1"

- id: MR-OD-004
  rule: "Five overlapping routers exist (platform/app.py+router.py,
         orchestrator-mvp, unified-personal-os, routing-engine, workspace-command).
         Before proposing any new routing layer, grep for these and write a
         'why this is not a sixth router' paragraph in the PR."
  source: "odysseus-north-star.md §2"

- id: MR-OD-005
  rule: "Secrets never reach traces or exchanges. Receipt = metadata only.
         Exchange capture applies deny-regex (api_key|secret|token|bearer|password)
         AND key-prefix stripping (sk-, AKIA, etc.) before write. The real
         guarantee is local-only + gitignored + never exported without the
         explicit exchange-export step."
  source: "orchestration-briefs.md Brief 6"

- id: MR-OD-006
  rule: "bg-implementer is self-applying. It must be gated by write-scope
         enforcement, emit a receipt per change, and refuse to touch files
         outside an isolated worktree without ODYSSEUS_APPROVAL_TOKEN."
  source: "commit c510b31 + north-star non-goal 'no training runs triggered'"

- id: MR-OD-007
  rule: "LOCALHOST_BYPASS implies admin. Any code reading request.state for
         authorization must be tested against a non-loopback Host header to
         confirm it does NOT inherit admin. The 2-line diff in 1dfa3f56 ships
         a security posture change with no test."
  source: "1dfa3f56 app.py diff"

- id: MR-OD-008
  rule: "api_key_env precedence: env var > encrypted column > None. Unset env
         falls through to DB silently. Both unset returns None and triggers an
         in-band error (never 500)."
  source: "core/database.py _migrate_add_api_key_env_column"

- id: MR-OD-009
  rule: "session.mode requires a consumer in the same PR. Writing the field
         with no reader is dead data with migration cost."
  source: "1dfa3f56 models.py/session_manager.py"

- id: MR-OD-010
  rule: "Pydantic Router (#3958) must wrap, not replace, TaskRouter.classify_task.
         Regex-first contract is global; cheap-LLM tiebreak fires only on
         _is_ambiguous()."
  source: "orchestration-briefs.md + #3958"

- id: MR-OD-011
  rule: "Online Skill Sharing (#3974) conflicts with non-goal 'no cloud sync of
         exchanges or transcripts.' Default-reject. If it lands, scope to
         local-network (mDNS/LAN) only."
  source: "odysseus-north-star.md Non-goals + #3974"

- id: MR-OD-012
  rule: "Worktree isolation does not equal process isolation. Brief 2 (worktree)
         is necessary but not sufficient. Subprocess cleanup requires process-
         group reap (kill -PGID) on timeout, exit, or cancel."
  source: "issue #3995 (orphaned hf/python) + Brief 2 spec gap"

- id: MR-OD-013
  rule: "Chat/agent UI state must be cleared on tool completion and on session
         switch. Pre-tool prose (#3992), executed fences (#3993), and utility-
         model gating (#3961) are the same root pattern."
  source: "issues #3992, #3993, #3961"
```

---

## 5. Next Unknown

**Cadence measurement at the fleet level — *what fraction of miner returns are distinct actionable findings per hour at each interval?***

The 3-commit oscillation (`14400s → 1800s → 60–180s`) shipped with no measurement. The north-star's flywheel thesis ("each loop iteration is measured by Brief 5 rollups") depends on a metric that does not exist yet. Without it, every future cadence commit is vibes-driven, and `bg-implementer` (added in the same commit) will start consuming noise as signal.

**Why this and not the others:**

| Candidate | Why it's not the next one |
|---|---|
| Implementer gating | Mechanical fix (write-scope + receipt + approval token), no investigation needed |
| Pydantic Router (#3958) | Blocked on Jwalin's spec call ("needs more info"), not on data |
| 5-archived-routers harvest | Doc-writing task, not an investigation |
| `api_key_env` cases | Three unit tests, no investigation |
| Brief 6 capture at chokepoint | Implementation, not investigation |
| Visibility tools (Phase 2) | Implementation, not investigation |

**The investigation:**

1. Pick one miner (`bg-code-architect` — highest-leverage, busiest class).
2. Run at three cadences (60s, 900s, 3600s) for 24h windows each, in `data/orchestration/miner_runs/`.
3. Two metrics:
   - **Volume**: unique URLs returned per hour (hash-deduped).
   - **Quality**: 20-finding human-judged sample per cadence, binary "would I act on this?"
4. Compare deltas. The correct cadence is the one where quality-per-hour peaks, not where volume peaks.
5. Ship Brief 5 rollups before any future cadence commit.

**Dashboard signal:** block all future `interval_seconds` changes until MR-OD-001 (Measured:/Rollup: citation) is enforceable — which requires Brief 5 to exist. Cadence measurement is the bottleneck on the flywheel; everything else in the synthesis is downstream of it.