# Orchestration Implementation Briefs (PLAN — Sonnet implements)

> Companion to `~/projects/platform/ORCHESTRATION.md` (canonical). Ground truth
> re-verified 2026-06-10: repo `~/projects/odysseus`, branch `hygiene/20260608`.
> Baseline: `tests/test_router.py` 55/55 + `tests/test_orchestration_trace.py`
> 15/15 — **all green**. These two suites are the validation gate for EVERY
> brief below: they must stay green after each brief lands, no exceptions.

## Global contracts (apply to all briefs)

**In-band error contract** (the router contract — never violate):

```json
{"response": str, "model_used": str, "tokens": int,
 "classification": "code|research|chat", "provider": str, "error": true?}
```

- `POST /api/route` NEVER returns 500. Dispatch failures, timeouts, missing
  CLIs, stale quota → `error: true` in-band, message in `response`
  (truncated 500 chars in trace receipts).
- Classification stays **regex-first** (`TaskRouter.classify_task`);
  cheap-LLM tie-break (`classify_task_async`, `utility` endpoint) fires only
  on `_is_ambiguous()` — never the routing target itself. No brief changes
  this.
- Every dispatch writes exactly one JSONL receipt via
  `core.orchestration_trace.record_trace(...)` (which never raises).
- Code-task subprocesses: 300 s timeout (`_CODE_TIMEOUT`), run in worktrees
  (Brief 2), keys via Infisical / CLI keychain — never printed, never in env
  dumps, never in traces.
- No swarm/mesh. One scheduler (`src/task_scheduler.TaskScheduler`), one
  trace file family (`data/orchestration/`).

**Validation gate (run after every brief):**

```bash
cd ~/projects/odysseus && source venv/bin/activate
PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest \
  tests/test_router.py tests/test_orchestration_trace.py -q
```

---

## Brief 1 — Wire-up: mount the traced router in app.py

### Critical pre-existing conflict (MUST resolve, not work around)

`app.py:727-728` already mounts `routes/route_dispatch.py`
(`setup_route_dispatch()`), which registers a **competing** `POST /api/route`:

- requires auth, raises `HTTPException(401)` / `HTTPException(422)` —
  violates the in-band contract;
- writes **no trace receipt**;
- Starlette matches routes in registration order → if the orchestration
  router is appended after it, the traced endpoint is silently dead.
  Server starts, tests stay green, zero receipts. This is the failure mode
  that would fake "done".

### Decision (made here, implement as written)

`routes/orchestration_routes.py` owns `POST /api/route` (per
ORCHESTRATION.md). `route_dispatch.py` keeps only `GET /api/route/status`
(quota + CLI summary — useful, no overlap).

### Exact changes

| File | Change |
|---|---|
| `app.py` (dirty file — this brief owns the edit) | Replace lines 727-728 (`from routes.route_dispatch import setup_route_dispatch` / `app.include_router(setup_route_dispatch())`) with: import + mount of `setup_orchestration_routes()` from `routes.orchestration_routes`, THEN mount `setup_route_dispatch()` after it. Mount order matters: orchestration first. |
| `routes/route_dispatch.py` | Delete the `@router.post("")` handler (`route_task`) and the now-unused `RouteRequest`/`RouteResponse` models. Keep `GET /status`. Update module docstring. |
| `routes/orchestration_routes.py` | No change required for acceptance. Optional auth: see D1 below. |

```python
# app.py — replacement block (place where route_dispatch is mounted today)
from routes.orchestration_routes import setup_orchestration_routes
app.include_router(setup_orchestration_routes())   # POST /api/route (traced) + /api/orchestration/*
from routes.route_dispatch import setup_route_dispatch
app.include_router(setup_route_dispatch())          # GET /api/route/status only
```

### Decision D1 — auth on POST /api/route

The traced endpoint is currently unauthenticated; `test_orchestration_trace.py`
exercises it without credentials. The app runs as a local LaunchAgent
(`com.odysseus.ui`). **Phase-1 ruling: ship unauthenticated, localhost-only**,
and record this as a known gap in the brief's PR description. If auth is added
later it must use `src.auth_helpers.get_current_user` AND the test fixtures
must be updated in the same commit — adding auth without touching tests will
break the validation gate (that's the gate doing its job, not a test problem).

### Error contract / failure modes

- `TaskRouter` construction failure (lazy init) → caught by the existing
  `except Exception` in `route()` → in-band `error: true`. Verify, don't assume.
- Trace dir unwritable → `record_trace` sets `_write_error` on the receipt and
  the request still succeeds (observability never breaks the request).
- Double-mount regression: if both POST handlers ever coexist again, the
  first registered wins silently. The new test below pins this.

### Acceptance criteria

1. Server starts: `python3 -B -c "import app"` succeeds (or LaunchAgent
   restart clean in logs).
2. `curl -s -X POST localhost:<port>/api/route -H 'content-type: application/json' -d '{"task":"hi","type":"chat"}'`
   returns the in-band contract (all five keys present).
3. A new line lands in `data/orchestration/traces.jsonl` for that call.
4. `GET /api/route/status` still works (route_dispatch survivor).
5. Invalid type (`"type":"bogus"`) → 422 from pydantic `Literal` validation
   (request-shape errors are NOT in-band; only dispatch errors are).

### Pytest list (definition of done)

- `tests/test_router.py` — all 55, unchanged, green.
- `tests/test_orchestration_trace.py` — all 15, unchanged, green.
- **New** `tests/test_orchestration_wireup.py`:
  - `test_app_mounts_traced_route` — build the real app's route table (or a
    TestClient against `app.app`), assert exactly ONE `POST /api/route` route
    exists and its endpoint function is `orchestration_routes.route`.
  - `test_post_route_writes_receipt` — TestClient POST → assert one new JSONL
    line with matching `task_hash`.
  - `test_route_dispatch_post_removed` — assert `routes.route_dispatch` has no
    POST route; `GET /api/route/status` returns 200-shape.
  - `test_route_status_survives` — status endpoint returns `providers` +
    `cli_binaries` keys.

---

## Brief 2 — Async code route via the EXISTING task_scheduler

### Problem

`TaskRouter.route_code` blocks the HTTP request up to 300 s
(`asyncio.to_thread(subprocess.run, ..., timeout=300)`). Code tasks must
return `< 1 s` with a run handle. **Reuse `TaskScheduler` — do not build a
second async surface** (no new queue, no new poller, no job table).

### Mechanism (decided)

One-off `ScheduledTask` + the scheduler's existing run lifecycle
(`TaskRun` rows, `run_task_now`, `stop_task`, notifications — all free):

1. Register a builtin action **`route_code`** (follow the existing action
   dispatch signature in `src/builtin_actions.py` / `_execute_action` in
   `src/task_scheduler.py:1004`). The action body: build prompt (Brief 3),
   call `TaskRouter().route_code(prompt, cwd=worktree)` synchronously inside
   the scheduler's executor, write the trace receipt with
   `source="scheduler"`, return the result text.
2. In `routes/orchestration_routes.py::route`: after classification, if
   `classification == "code"` and `req.sync is not True`:
   - create `ScheduledTask(id=uuid, schedule="once", task_type="action",
     action="route_code", prompt=<brief text>, owner=<user or None>,
     status="active", name="route: <first 60 chars>")`, commit;
   - `await task_scheduler.run_task_now(task_id)`;
   - return immediately (in-band, NOT an error):

```json
{"response": "accepted", "model_used": "pending", "tokens": 0,
 "classification": "code", "provider": "scheduler",
 "run_id": "<task_id>", "status_url": "/api/orchestration/runs/<task_id>"}
```

3. New endpoint `GET /api/orchestration/runs/{run_id}` in
   `orchestration_routes.py`: look up the one-off task's newest `TaskRun`
   (model: `core/database.py:605`); map to
   `{run_id, status: "running|success|error", response, model_used, tokens,
   started_at, finished_at}`. Unknown id → 404 (resource semantics, not
   dispatch semantics).

`run_id` == the one-off task's id (one-off task ⇔ exactly one run). Do not
invent a parallel id space.

### Worktrees (constraint, not optional)

- `TaskRouter.route_code` gains `cwd: Optional[str] = None` (default None =
  current behavior, keeps the 55 router tests untouched).
- The `route_code` action creates the run dir **before** spawning:
  - request names a repo (`req.repo`, optional) → `git worktree add
    data/orchestration/worktrees/<run_id> <head>` in that repo;
  - no repo → plain scratch dir `data/orchestration/worktrees/<run_id>`.
  - **Never** run the CLI subprocess in the live server CWD.
- Cleanup: `git worktree remove --force` / `rmtree` on completion; orphans
  older than 24 h reaped by the retention job (Brief 5).
- Keys: CLI binaries (`ca`/`cb`/`cp`) use their own keychain/Infisical-backed
  auth. Pass through `os.environ` as today; never inject literal keys, never
  log env.

### Scheduler wiring detail

`task_scheduler` is constructed in `app.py:627`.
`setup_orchestration_routes()` currently takes only `task_router`; extend its
signature to `setup_orchestration_routes(task_router=None, task_scheduler=None)`
and pass the instance at mount time (Brief 1's block becomes
`setup_orchestration_routes(task_scheduler=task_scheduler)` — move the mount
below line 627 or hoist the scheduler construction; implementer's choice,
state it in the PR). If `task_scheduler is None` (tests, degraded boot), code
tasks fall back to the current synchronous path — degraded, not broken.

### Error contract / failure modes

- 300 s timeout inside the action → `route_code` already returns
  `{error: true, response: "Task timed out after 300s"}` → stored on the
  `TaskRun` → status endpoint surfaces `status: "error"` + in-band body.
  **Never an exception, never a 500.**
- Worktree creation fails (dirty repo, bad ref, disk) → action returns
  in-band `error: true` with the git stderr (truncated); no subprocess spawned.
- Server restart mid-run → scheduler marks the run per its existing restart
  semantics (see `tests/test_scheduler_restart_doublefire.py`); status
  endpoint reports `error`, receipt written by a startup sweep is OUT of
  scope — document as known gap.
- DB write fails on task creation → in-band `error: true` from the POST
  (this one IS a dispatch failure).
- Trace receipt for async runs is written at **completion** (inside the
  action), with real latency and tokens; the fast-ACK POST itself is NOT
  separately traced (one dispatch = one receipt).

### Acceptance criteria

1. `POST /api/route` with a code task returns in `< 1 s` with `run_id`.
2. `GET /api/orchestration/runs/{run_id}` transitions
   running → success|error.
3. Completed run has exactly one receipt in `traces.jsonl`
   (`source: "scheduler"`, real latency).
4. Timeout path (`_CODE_TIMEOUT` monkeypatched to 1 s, fake CLI sleeping 5 s)
   → status `error`, body `error: true`, no exception in logs.
5. Worktree dir created before spawn, removed after completion.
6. chat/research tasks: behavior unchanged (synchronous, traced inline).

### Pytest list

- Gate: `tests/test_router.py` (55) + `tests/test_orchestration_trace.py`
  (15) green — `route_code(cwd=None)` default keeps them untouched.
- **New** `tests/test_async_code_route.py`:
  - `test_code_post_returns_fast_with_run_id` (fake scheduler, assert <1 s
    wall and response shape)
  - `test_run_status_lifecycle` (seed TaskRun rows, assert mapping
    running/success/error)
  - `test_run_status_unknown_id_404`
  - `test_timeout_is_inband_error` (monkeypatched timeout + sleeping stub CLI)
  - `test_completed_run_writes_receipt` (assert one line, `source=scheduler`)
  - `test_worktree_created_and_cleaned` (tmp git repo fixture)
  - `test_no_scheduler_falls_back_sync`
  - `test_chat_research_still_sync`

---

## Brief 3 — Brain-context task briefs (delegation prompts)

### Problem

Sub-agent prompts must be composed from **knowledge-base facts** — goal,
constraints, file paths, acceptance criteria — never raw conversation
history. Sub-agents see summaries only. (Cold-start rule from
ORCHESTRATION.md §Sharpening 4: autospawned sessions inherit nothing.)

### Exact files

| File | Change |
|---|---|
| `core/task_brief.py` (new) | `compose_brief(...)` — pure function, no I/O beyond brain reads |
| `src/brain_engine.py` | No changes. Consume `get_recent_entries(days)` / `get_cached_context_prefix()` (read-only). |
| `routes/orchestration_routes.py` / `route_code` action | Code path builds the subprocess prompt via `compose_brief`, not the raw task string, when structured fields are supplied. |

### Spec

```python
def compose_brief(
    *, goal: str,                      # required, one sentence
    constraints: list[str] = (),       # explicit dos/don'ts
    files: list[str] = (),             # exact paths the sub-agent may touch
    acceptance: list[str] = (),        # checkable criteria
    brain_days: int = 7,               # fact window
    max_chars: int = 8_000,
) -> str
```

- Output: deterministic markdown — `## Goal`, `## Constraints`, `## Files in
  scope`, `## Acceptance criteria`, `## Background facts` (from
  `brain_engine.get_recent_entries(brain_days)`, each entry rendered as its
  stored **summary line only** — never full entry bodies, never chat logs).
- Hard cap `max_chars`: truncate background facts first (oldest dropped
  first), never goal/constraints/acceptance. If goal+constraints+acceptance
  alone exceed the cap → `ValueError` (caller bug, fail loud).
- Zero conversation access: the function signature makes this structural —
  there is no `messages`/`history` parameter and none may be added.
- `RouteRequest` gains optional fields `goal`, `constraints`, `files`,
  `acceptance` (all optional; absent → legacy raw-task behavior unchanged).

### Error contract / failure modes

- Brain store empty/missing → `## Background facts\n(none)` — brief still
  valid; never raises.
- Brain file lock contention (`_FileLock`) → bounded wait; on failure, facts
  section degrades to `(unavailable)` and a `logger.warning` — composing a
  brief must never block a dispatch.
- Secrets: render entry summaries only; entries are user-authored brain
  dumps, but still pass through a deny-regex for obvious token shapes
  (`(?i)(api[_-]?key|secret|token)\s*[:=]\s*\S+` → redact match).

### Acceptance criteria

1. Same inputs + same brain state → byte-identical brief (deterministic).
2. Brief contains all four structured sections and only summary-level facts.
3. Cap enforced; structured sections never truncated.
4. Code dispatch with structured fields runs the CLI with the composed brief
   as the prompt; without them, behavior is byte-identical to today.

### Pytest list

- Gate suites green (no changes to router/trace internals).
- **New** `tests/test_task_brief.py`:
  - `test_deterministic_output`
  - `test_sections_present_and_ordered`
  - `test_truncates_facts_not_contract` (oversized facts, intact goal/AC)
  - `test_oversized_contract_raises`
  - `test_empty_brain_ok`
  - `test_no_history_parameter` (signature introspection — guards the
    structural rule)
  - `test_secret_shapes_redacted`
  - `test_route_request_fields_optional_backcompat`

---

## Brief 4 — `scripts/agent-audit` (collect / diff / propose-stub)

### Exact files

| File | Change |
|---|---|
| `scripts/agent-audit` (new, executable, `#!/usr/bin/env python3`) | CLI with `collect`, `diff`, `propose` subcommands (argparse) |
| `data/orchestration/audit/` (new dir, runtime) | snapshots + diffs land here |

Read-only inputs — the script NEVER writes outside `data/orchestration/audit/`:

- `data/orchestration/traces.jsonl` (+ `rollups/` once Brief 5 lands)
- `~/projects/platform/systems/quota-core/data/quota-live.json`
- `git -C ~/projects/odysseus status --porcelain` + `rev-parse` (and
  `~/projects/platform` likewise) — porcelain only, deterministic.

### `collect`

Writes `audit/snapshot-<UTC YYYYMMDDTHHMMSSZ>.json`:

```json
{"schema": 1, "collected_at": "...", 
 "traces": {"count_24h": n, "count_7d": n, "success_rate_7d": x,
            "p50_ms_7d": x, "p95_ms_7d": x,
            "by_classification_model": [...]},   // reuse otrace.compute_stats()
 "quota": {"age_s": x, "providers": {name: {"status": s, "weekly_pct_remaining": r?}}},
 "git": {"odysseus": {"branch": b, "head": sha, "dirty": n, "untracked": n},
         "platform": {...}}}
```

Exit 0 on success; exit 1 with a one-line stderr reason if ANY source is
unreadable (partial snapshots are worse than none — they poison diffs).

### `diff`

- Loads the two newest snapshots (or `--from/--to` paths). Fewer than two →
  exit 1, message "need two snapshots".
- Emits **deterministic** markdown (same input pair → byte-identical output;
  the only timestamps are the two snapshot ids in the header) to stdout and
  `audit/diff-<from>-<to>.md`:
  sections for traffic delta, success-rate delta, latency delta, quota
  status changes, git drift (branch/head/dirty-count changes). No prose
  generation, no LLM, pure arithmetic + table rendering.

### `propose` — STUB ONLY

Per plan: do not implement until ~2 weeks of trace data exists. Stub prints
`propose: not implemented — requires >=14 days of trace history (have N days)`
(N computed from oldest trace) and exits 2. Hard guard: even when later
implemented, refuse with the same message when history < 14 days.

### Error contract / failure modes

- Missing traces file → `collect` fails (exit 1) — never fabricates zeros.
- Malformed JSONL lines → skipped (consistent with `read_traces`), count of
  skipped lines reported in the snapshot under `traces.malformed`.
- Snapshot schema bump → `diff` across schema versions exits 1 with both
  versions named.
- No secrets: quota file contains usage metadata only — assert no key named
  `*token*`/`*key*` is copied through; redact if present.

### Acceptance criteria

1. `scripts/agent-audit collect` produces a valid snapshot; second run
   produces a second one; both parse.
2. `scripts/agent-audit diff` over two snapshots is byte-deterministic on
   repeated invocation.
3. `propose` exits 2 with the not-implemented message.
4. Script is read-only outside `audit/` (verify with a before/after
   `git status --porcelain` in the test).

### Pytest list

- Gate suites green (script imports `core.orchestration_trace` read-only).
- **New** `tests/test_agent_audit.py` (invoke via `subprocess` on tmp dirs):
  - `test_collect_snapshot_schema`
  - `test_collect_fails_on_missing_source`
  - `test_collect_counts_malformed_lines`
  - `test_diff_deterministic`
  - `test_diff_needs_two_snapshots`
  - `test_propose_stub_exit2_under_14d`
  - `test_no_writes_outside_audit_dir`

---

## Brief 5 — Trace retention: 30-day raw JSONL, daily rollups forever

### Exact files

| File | Change |
|---|---|
| `core/trace_retention.py` (new) | `rollup_and_prune()` + helpers |
| `src/task_scheduler.py` | Add one entry to `HOUSEKEEPING_DEFAULTS` (~line 971 region): daily action task `orchestration_retention` |
| `src/builtin_actions.py` | Register `orchestration_retention` action → calls `rollup_and_prune()` |
| `core/orchestration_trace.py` | Export `_write_lock` access via a small public helper (`trace_write_lock()`) — retention must hold the SAME lock when rewriting the file. No other changes. |

### Spec

`rollup_and_prune(now=None)` — idempotent, safe to re-run:

1. **Rollup:** for each completed UTC day present in `traces.jsonl` that has
   no rollup yet, write `data/orchestration/rollups/YYYY-MM-DD.json`:
   `{schema:1, day, count, success_rate, p50_ms, p95_ms, tokens_total,
   by_classification_model:[...]}` (same bucketing as `_window_stats` —
   fixed cardinality, never task_hash). Write via temp file + `os.replace`.
   Existing rollup file → skip (never overwrite history).
2. **Prune:** only AFTER every affected day has a rollup on disk
   (receipt-before-delete): rewrite `traces.jsonl` keeping lines with
   `unix >= now - 30*86400`, under `trace_write_lock()`, via temp +
   `os.replace` in the same directory (atomic on APFS). Malformed lines
   within the retained window are KEPT (pruning must not be lossier than
   reading).
3. **Worktree reaping** (from Brief 2): remove
   `data/orchestration/worktrees/*` older than 24 h.

Scheduling: daily housekeeping task, owner-less/system, follows the existing
`HOUSEKEEPING_DEFAULTS` + `ensure_defaults` pattern. `run_task_now` works for
manual trigger; the action returns a one-line summary
(`"rolled up 3 day(s), pruned 1,204 line(s), reaped 0 worktree(s)"`) so
TaskRun rows are self-evidencing.

### Error contract / failure modes

- Rollup write fails → abort BEFORE pruning; raw data is never deleted
  without its rollup existing on disk (data-preservation invariant).
- Concurrent `record_trace` during rewrite → safe: both hold the same lock;
  receipts written after the snapshot read but before `os.replace` must not
  be lost — implementation: read + filter + replace all under the lock
  (file is ≤30 days of receipts; lock hold time is milliseconds).
- Clock skew / future timestamps → lines with `unix > now + 86400` kept and
  counted in the summary as `suspect`.
- Empty/missing traces file → no-op success.
- Crash between rollup and prune → next run skips existing rollups and
  prunes; idempotent by construction.

### Acceptance criteria

1. After a run over synthetic 45-day data: rollup files exist for every
   completed day; `traces.jsonl` contains only the last 30 days; counts in
   rollups + retained raw == original total.
2. Re-running immediately is a no-op (same rollups, same file size).
3. Rollup-write failure (read-only rollups dir) → raw file untouched.
4. `compute_stats()` (24 h/7 d) unaffected — windows live inside the 30-day
   raw retention.
5. Housekeeping task visible in `GET /api/tasks` and runnable via
   `POST /api/tasks/{id}/run`.

### Pytest list

- Gate suites green — especially `tests/test_orchestration_trace.py`
  concurrent-write atomicity, which now also guards the shared lock.
- **New** `tests/test_trace_retention.py`:
  - `test_rollup_per_completed_day`
  - `test_prune_keeps_30_days_exact_boundary`
  - `test_receipt_before_delete_invariant` (failing rollup ⇒ no prune)
  - `test_idempotent_rerun`
  - `test_concurrent_record_trace_during_prune_no_loss` (threads)
  - `test_malformed_lines_in_window_kept`
  - `test_future_timestamps_kept_flagged`
  - `test_existing_rollup_never_overwritten`
  - `test_worktree_reap_older_24h`

---

## Sequencing & ownership

| # | Brief | Depends on | New files | Touched in-flight files |
|---|---|---|---|---|
| 1 | Wire-up | — | `tests/test_orchestration_wireup.py` | `app.py` (owned edit), `routes/route_dispatch.py` |
| 2 | Async code route | 1 | `tests/test_async_code_route.py` | `routes/orchestration_routes.py`, `core/router.py` (cwd arg), `src/builtin_actions.py`, `app.py` (pass scheduler) |
| 3 | Task briefs | 2 | `core/task_brief.py`, `tests/test_task_brief.py` | `routes/orchestration_routes.py` (optional fields) |
| 4 | agent-audit | 1 (live traces) | `scripts/agent-audit`, `tests/test_agent_audit.py` | none |
| 5 | Retention | 1 | `core/trace_retention.py`, `tests/test_trace_retention.py` | `src/task_scheduler.py` (one HOUSEKEEPING entry), `src/builtin_actions.py`, `core/orchestration_trace.py` (lock export) |
| 6 | Exchange capture + harvester + export | 1 (parallel to 4/5) | `core/exchange_log.py`, `scripts/transcript-harvest`, `scripts/exchange-export`, `tests/test_exchange_log.py`, `tests/test_transcript_harvest.py`, `tests/test_exchange_export.py` | `core/router.py` (capture call sites), `.gitignore`, Brief 5's retention job (gzip step) |

**Brief 6 is specced in `docs/odysseus-north-star.md` §4** (exchange
capture: full I/O corpus at `data/orchestration/exchanges/`, ON by default,
secret-redacted, gitignored; harvester normalizes `~/.codex/sessions`,
`~/.pi/agent/sessions`, `~/.claude/projects`, opencode logs into the same
schema; export bridge writes ONLY to `pioneer-adaption/inbox/`). Same global
contracts apply: capture never raises, never changes router return values,
gate suites stay green.

Out of scope everywhere: MCP servers, swarm/mesh topologies, auth overhaul,
the platform repo's dead `app.py`/`router.py` copies (do not read, do not
build on), `propose` implementation (blocked on 14 days of trace history).
