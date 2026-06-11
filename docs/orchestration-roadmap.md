# Orchestration Roadmap — payoff, setup, and what comes after

> Companion to `docs/orchestration-briefs.md` (implementation briefs 1–6)
> and `docs/odysseus-north-star.md` (Mac-wide synthesis, Brief 6 spec, the
> Pioneer flywheel) and `~/projects/platform/ORCHESTRATION.md` (canonical
> architecture).
> This doc answers: what do we actually GET, how do we run the build, and
> what unlocks afterwards. Written 2026-06-10.

---

## 1. What the five briefs buy you (immediate, concrete)

Once Briefs 1–5 land you have **one HTTP contract** — `POST /api/route` —
that anything on this Mac can call, and behind it:

| Capability | Payoff |
|---|---|
| Quota-aware routing | Every task goes to the cheapest *available* backend (ca/cb/cp for code, Gemini for research, MiniMax for chat). You stop burning Claude quota on "what's the weather" and stop hitting exhausted providers. |
| In-band error contract | Callers never handle 500s or exceptions. Scripts, LaunchAgents, and cron jobs can call it blind and always get parseable JSON. |
| Receipts (traces.jsonl) | Every dispatch is evidence: what ran, where, cost-in-tokens, latency, success/failure. "What did my agents do this week and what did it cost" becomes a 5-second query instead of guesswork. |
| Non-blocking code runs | Fire a code task, get `run_id` in <1s, poll status. The server never hangs 300s on a subprocess. Code runs happen in throwaway worktrees, never in the live repo. |
| Brain-grounded briefs | Sub-agents get clean, deterministic task briefs (goal/constraints/files/acceptance + KB summaries) instead of inherited chat sludge. Cheaper prompts, more reproducible runs, no accidental context leaks. |
| agent-audit | Deterministic snapshots + diffs of traffic, success rate, latency, quota, git drift. You can see degradation *between* two points in time without trusting anyone's summary. |
| Retention | Data growth is bounded (30-day raw) while history is permanent (daily rollups). The system never becomes a disk-hygiene problem. |

**The honest framing:** this is a personal routing + observability layer.
Its ceiling is "my compute is spent well and I can prove it." It is not a
product, not a swarm, not autonomy. That ceiling is the right one for now.

---

## 2. Setup / execution plan (how the build actually runs)

### Sequencing & parallelism

```
Brief 1 (wire-up)  ──► Brief 2 (async code) ──► Brief 3 (task briefs)
        │
        ├──► Brief 4 (agent-audit)     } 4, 5, 6 parallel after 1,
        ├──► Brief 5 (retention)       } disjoint write scopes
        └──► Brief 6 (exchange capture + harvester + Pioneer export)
```

- Briefs 1→2→3 are a strict chain (2 needs the mounted router + scheduler
  handle; 3 needs 2's code path).
- Briefs 4 and 5 only need live traces; they touch disjoint files and can
  run as parallel bounded workers.

### Workpacks (one per brief — the briefs already contain the contract)

Each worker gets, per the operating contract:

| Element | Source |
|---|---|
| Outcome | The brief's "Acceptance criteria" section |
| Owned files | The brief's "Exact files" table — no writes outside it |
| Validation | `pytest tests/test_router.py tests/test_orchestration_trace.py -q` PLUS the brief's new named test file |
| Stop condition | All listed tests green, or 2 failed validation cycles → stop and report (no thrashing) |
| Kill criteria | Worker touches files outside its table, weakens an existing test, or adds a second async surface → kill, review, restart |
| Evidence | Test output + `git diff --stat` + (for 1/2) a curl transcript showing the in-band contract and a receipt landing |

Worker settings: bounded mode, Sonnet as implementer (these are
spec-complete briefs — no architecture decisions left), one worktree per
brief off `hygiene/20260608`. Review each diff before merge; Brief 1 touches
your dirty `app.py`, so that merge is hands-on by design.

### Rough effort

| Brief | Size | Risk |
|---|---|---|
| 1 Wire-up | Small (~1 session) | Low — but the route-collision removal must be verified by the new wireup test, not eyeballs |
| 2 Async code | Largest (~2–3 sessions) | Medium — scheduler integration + worktree lifecycle; the test list is the guardrail |
| 3 Task briefs | Small-medium | Low — pure function + optional request fields |
| 4 agent-audit | Medium | Low — read-only by construction |
| 5 Retention | Medium | Medium — the receipt-before-delete invariant and shared lock are the two things to review hard |

### Definition of done for the whole phase

All five briefs merged, 70 baseline tests + ~35 new tests green, server
restarts clean under the LaunchAgent, and **a real receipt from a real task
in traces.jsonl** — not a test fixture.

---

## 3. Adoption — the part that decides whether any of this was worth it

**This is the weak spot in the plan as it stands, so naming it explicitly:**
if nothing calls `POST /api/route`, the traces stay empty, `agent-audit
diff` has nothing to diff, and the `propose` stage never unlocks (it's
gated on 14 days of history). The build succeeds and the system is dead
weight. Tracing infrastructure only pays for itself when traffic flows
through it.

So the phase immediately after the briefs is **routing real traffic**, in
this order (cheapest surface first, per the iterate-on-CLI-before-UI rule):

1. **`ody route "<task>"`** — add a subcommand to the existing ody CLI that
   POSTs to `/api/route` and pretty-prints the in-band response (and polls
   the run status URL for code tasks). One small script; instantly makes the
   router your default "just do this" entry point from any terminal.
2. **Scheduler tasks** — point existing recurring LLM tasks that are really
   classification-shaped work (summaries, research digests) through the
   router action instead of direct model calls, so they hit the cheap path
   and get receipted.
3. **Other scripts/LaunchAgents** — anything in `scripts/odysseus-*` that
   currently shells out to a model directly migrates to the one endpoint,
   one at a time, only when touched for other reasons. No big-bang rewrite.

Target: **~2 weeks of organic traffic** (a handful of dispatches a day is
enough — fixed-cardinality stats don't need volume). That's the clock that
starts the Phase-2 unlock.

---

## 4. Phase 2 — what the data unlocks (~2 weeks after adoption)

These are *earned* by traces, not buildable now. Do not start them early.

| Unlock | What it is | Why it needs data |
|---|---|---|
| `agent-audit propose` (un-stub) | LLM reads snapshots + rollups and proposes routing-policy changes (CLI priority reorder, timeout tuning, classification pattern fixes) as a **reviewed diff, never auto-applied** | Proposals from <14 days of data are noise; the stub's guard enforces this |
| Classification feedback loop | Cross trace `classification` vs outcome (`error`, latency, tokens): are "chat"-classified tasks failing in ways that suggest they were code? Tighten the regexes from evidence, not vibes | Needs real misclassifications to find |
| Cost-per-class baselines | From rollups: tokens/day by classification × model. This is the number that tells you whether routing is actually saving quota vs. just adding a hop | Needs rollup history (Brief 5 output) |
| Quota-degradation policy | Today: skip exhausted providers. With data: pre-emptively shift load when a provider's weekly remaining trends toward a threshold | Needs trend, i.e., history |
| Replay/eval harness | Re-run a sample of captured exchanges against alternate backends to A/B routing choices. ~~Privacy decision pending~~ → **decided**: Brief 6 captures full I/O (local-only, gitignored, redacted), so the corpus exists | Needs Brief 6 traffic |
| **Pioneer flywheel** | `exchange-export` feeds `pioneer-adaption/inbox/` → datasets → evals → a Jwalin-tuned model candidate → new entry in the router's `_CLI_PRIORITY`. The router improves from its own traffic. Full diagram: north-star §3 | Needs weeks of corpus; export is always human-triggered |
| Chat-through-router (Brief 7) | Opt-in: odysseus chat UI messages dispatch via `POST /api/route` — adoption becomes the default path, not a habit change. Spec: north-star §6.2 | Needs 2 weeks of stable Brief 1–6 runtime first |
| Golden eval gate | ~50 curated exchanges → `pioneer-adaption/evals/odysseus_golden.v0.json`; no routing-policy change merges without passing it. Spec: north-star §6.3 | Needs corpus to curate from |
| Failure mining | `exchange-export --corrections`: error receipt + later success on same `task_hash` = automatic correction pair for Adaption. Spec: north-star §6.4 | Needs failures + retries in corpus |

Note: Brief 6 capture point amended (north-star §6.1) — capture lives in
`llm_call_async` (28 call sites flow through it), not just the router, so
the corpus fills from existing chat/scheduler/research traffic on day one.
Also: corpus durability (backup of `data/orchestration/`) per §6.5.

Phase-2 cadence: run `agent-audit collect` daily (add it as a second
housekeeping action — one line, same pattern as retention), review the
weekly diff yourself for the first two weeks, *then* decide if `propose` is
worth implementing or the manual diff is already enough. It's allowed for
the answer to be "the diff is enough" — that's a win, not a failure.

---

## 5. Phase 3 — optional, only if Phase 2 proves value

Listed so they're parked, not so they're promised:

- **Thin UI**: a single status page over `/api/orchestration/stats` +
  rollups. Only after the CLI contract has proven useful (contract-first
  rule). The existing odysseus web UI can host it as one more tab.
- **Auth on POST /api/route**: required *only if* the endpoint is ever
  exposed beyond localhost. Bundled with test-fixture updates per Brief 1's
  D1 ruling.
- **Multi-repo code routing**: `req.repo` (Brief 2) generalized with an
  allowlist of repos the router may create worktrees in. The allowlist is a
  safety boundary — grill it before widening.
- **Cross-system rollup export**: feed daily rollups into the platform
  command-center JSON so Atlas sees orchestration health alongside
  everything else. Cheap, high-leverage, but pointless before there's data.

## Explicit non-goals (unchanged, restating so scope can't creep)

No swarm/mesh. No second async surface. No auto-applied policy changes. No
building on the platform repo's dead app.py/router.py. No dashboard before
the CLI proves the contract. No raw-conversation capture in traces without
an explicit privacy decision.

---

## 6. End state — what you personally have afterwards

After Phase 1 + adoption + Phase 2, the steady state is:

1. **One verb for delegation.** `ody route "fix the failing test in X"`
   from any terminal — classified, quota-routed, worktree-isolated,
   receipted, non-blocking. You stop thinking about which model/CLI to use
   for throwaway tasks; the router's choice is auditable when you care.
2. **An evidence trail instead of vibes.** "What ran, what did it cost,
   what failed, what changed since last week" — answered from receipts and
   deterministic diffs, which is exactly the done-means-evidence posture
   from the operating contract, now applied to the agents themselves.
3. **A cost-control loop.** Cheapest-capable routing now; data-driven
   policy tuning (reviewed, never auto-applied) once history exists.
   Measurable in tokens/day by class — a real number, not a vanity metric.
4. **A safe substrate for more automation.** Bounded one-off scheduler
   runs + worktrees + briefs composed from the KB means future recurring
   agents (nightly hygiene runs, digest generation, audit collection) are
   one `ScheduledTask` row away — inheriting timeouts, receipts, retention,
   and stop semantics for free instead of each one reinventing them.
5. **A clean off-ramp.** Because everything is receipted and bounded, you
   can also conclude "the router doesn't earn its keep" from its own data
   and delete it cheaply. A system that can prove its own uselessness is
   the only kind worth building speculatively.

The single biggest risk is #3 in section 3: building it and not routing
traffic through it. The build plan is solid; the adoption step is the one
that needs your actual habit change. Decide now what your first recurring
routed task will be — that decision matters more than any brief.
