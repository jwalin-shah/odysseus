# Odysseus North Star — one front door, one corpus, one flywheel

> Synthesis of everything on this Mac (surveyed 2026-06-10) and the ruling on
> what Odysseus becomes. Companion to `docs/orchestration-briefs.md` (build
> plan) and `docs/orchestration-roadmap.md` (phases). Canonical architecture:
> `~/projects/platform/ORCHESTRATION.md`.

---

## 1. The direct answer: do we save input/output of each inference?

**Odysseus today: NO — by design.** `record_trace()` stores only
`task_hash` (16-hex sha256, forensics-only), classification, model, tokens,
latency, success/error. Receipts are metadata, not content.

**But the Mac already saves full transcripts everywhere else:**

| Store | Size | Content |
|---|---|---|
| `~/.codex/sessions/` | 12 MB | Full Codex session JSONL |
| `~/.pi/agent/sessions/` | 7.7 MB | Full pi session JSONL (incl. odysseus/platform work) |
| `~/.claude/projects/` | 492 KB | Claude Code transcripts |
| `~/.local/share/opencode/` | — | OpenCode storage |
| `agent-flight-recorder` `.afr/` | per-repo | Decisions, commands, evidence, SQLite |

So the raw material exists — it's just **fragmented across five formats with
no consumer**. memjuice already proved these JSONLs are parseable
("your agents are already writing memory to disk").

**Ruling: start saving I/O in Odysseus, deliberately (Brief 6 below).**
The privacy call from the roadmap is now made: this is a single-user,
localhost-only LaunchAgent on your own Mac. Capture ON by default,
local-only, gitignored, secret-redacted, never synced. The reason isn't
observability — receipts already cover that. The reason is §3.

---

## 2. What's actually on this Mac (survey, deduplicated)

**Keep — each has a distinct job:**

| Asset | Role in the end state |
|---|---|
| `odysseus` | **The product. The front door.** UI + API + scheduler + router + traces. Everything below feeds it or consumes from it. |
| `platform/systems/quota-core` | Live quota truth (`quota-live.json`, LaunchAgent-refreshed). Router input. |
| `pioneer-adaption` | **The flywheel.** Datasets → evals → model candidates → failures → corrected examples. Currently starved for data; §3 feeds it. |
| `memjuice` | Transcript→context codec. Its parsers are the blueprint for the harvester. |
| `agent-flight-recorder` | Deep per-repo debugging (decisions/evidence/HTML reports). Complements receipts; doesn't compete. |
| `pcr-core` | Safety gate (default-deny, receipt-before-return). Already wraps this very session. Stays the admission layer. |
| `knowledge-base` + odysseus `brain_engine` | Facts source for task briefs (Brief 3). |
| `chariot-router-go` | <20ms Go classifier. **Parked**: swap into `classify_task` hot path later IF latency ever matters. Don't integrate now. |
| `cmux`, `ody`, `ca/cb/cp`, `infisical`, `rtk/llm-tldr/tokenjuice` | Cockpit + workers + secrets + context tooling. Unchanged. |

**Archive / do not build on (this is the pushback):** you have at least
**five overlapping router/orchestrator attempts** — `platform/app.py` +
`router.py` (dead, already ruled), `orchestrator-mvp`, `unified-personal-os`
(itself a previous consolidation attempt), `routing-engine`,
`workspace-command`'s routing role, plus `quota-verified`/`quota-core-new`
duplicates. Every one of these was "the unified thing" once. The failure
mode on this Mac is not missing capability — it's **starting a sixth
router**. Odysseus wins by being the only one with a UI, a scheduler, a DB,
tests, and a LaunchAgent already running. Everything else gets harvested
for parts or moved to `_archive/`.

---

## 3. The flywheel — why saving I/O is the whole point

pioneer-adaption's README defines the loop: datasets → train/eval → record
failures → corrected examples → next version. Its first project is literally
**"Jwalin-style coding-agent compliance and task-handoff quality."** That
loop is currently hand-fed (a few KB of v0 JSONLs). Routed traffic is the
missing feedstock.

```
            ┌──────────────────────────────────────────────┐
            │                                              ▼
 you ──► POST /api/route ──► backend ──► response     exchanges.jsonl
            │                                (receipt +   (full I/O)
            ▼                                 in traces)       │
   CLI sessions (codex/pi/claude/opencode) ──► harvester ──────┤
                                                               ▼
                                              pioneer-adaption datasets
                                                               │
                                              evals ◄──────────┤
                                                               ▼
                                              Jwalin-tuned model candidate
                                                               │
            ┌──────────────────────────────────────────────────┘
            ▼
   router CLI priority list gains a new, cheaper, personal backend
```

**The router gets better from its own traffic.** That's the "more out of
Pioneer" — every inference you run becomes a training example for a model
that eventually slots into `_CLI_PRIORITY` as the cheapest capable backend
for your task shapes. Without capture, the flywheel has no fuel and Pioneer
stays a side project.

---

## 4. Brief 6 — Exchange capture + transcript harvester (spec, Sonnet implements)

### 6a. Capture in the router (new files only)

| File | Change |
|---|---|
| `core/exchange_log.py` (new) | `record_exchange(...)` — same never-raises discipline as `record_trace` |
| `src/llm_core.py` | **One call site in `llm_call_async`** (success + error paths), tagged with `prompt_type` — see §6.1 for why this beats router-level capture |
| `core/router.py` | One call site in `route_code` only (subprocess path bypasses llm_core) |
| `data/orchestration/exchanges/` (runtime, gitignored) | `YYYY-MM-DD.jsonl`, one file per day |

Schema (one line per inference, joined to receipts via `task_hash` + `unix`):

```json
{"ts": "...", "unix": 0.0, "task_hash": "...",
 "task": "<full input>", "response": "<full output>",
 "classification": "...", "model_used": "...", "provider": "...",
 "tokens": 0, "latency_ms": 0.0, "error": false, "source": "router|scheduler"}
```

Rules:
- **ON by default**, kill switch `ODYSSEUS_NO_CAPTURE=1` and per-request
  `capture: false`.
- Secret redaction before write: same deny-regex family as Brief 3
  (`(?i)(api[_-]?key|secret|token|bearer|password)\s*[:=]\s*\S+` → redacted),
  plus strip anything matching known key prefixes (`sk-`, `AKIA`, etc.).
- `data/orchestration/exchanges/` in `.gitignore` — verified by test.
- Retention: **keep forever, gzip files older than 30 days** (it's training
  data; rollup-style aggregation would destroy its value). Add to Brief 5's
  retention job.
- Receipts stay content-free. Two files, two purposes: `traces.jsonl` =
  audit (small, queryable, shareable), `exchanges/` = corpus (big, private).

### 6b. Harvester for CLI transcripts (read-only)

| File | Change |
|---|---|
| `scripts/transcript-harvest` (new) | Normalize external session logs into the same exchange schema |

- Sources: `~/.codex/sessions`, `~/.pi/agent/sessions`, `~/.claude/projects`,
  `~/.local/share/opencode` — read-only, never mutates source logs.
- Output: `data/orchestration/exchanges/harvested-<source>-YYYY-MM-DD.jsonl`,
  `source: "harvest:<cli>"`, deduped by content hash; idempotent re-runs
  (state file of last-seen offsets per source file).
- Borrow parsing logic from memjuice's codecs rather than re-deriving the
  five formats.
- Runs as a daily housekeeping action (same pattern as Brief 5's job).

### 6c. Dataset export bridge

| File | Change |
|---|---|
| `scripts/exchange-export` (new) | Filter + reshape exchanges → pioneer-adaption dataset JSONL |

- `exchange-export --since 30d --classification code --min-tokens 50 --out
  ~/projects/pioneer-adaption/inbox/odysseus-<date>.jsonl`
- Writes to pioneer-adaption's `inbox/` only — Adaption decides what becomes
  a dataset version. Odysseus never writes datasets directly (ownership
  boundary).

### Error contract / failure modes (all of 6)

- Capture failure never breaks a dispatch (`record_exchange` never raises,
  mirrors `record_trace`).
- Harvester hitting a malformed/truncated session file → skip file, count
  in summary, exit 0 (partial harvest is fine here — unlike audit snapshots,
  the corpus is append-only and self-healing on the next run).
- Export with zero matches → exit 1, "no exchanges matched" (empty dataset
  files poison the Adaption loop).
- Redaction is best-effort defense-in-depth, not a guarantee — the real
  guarantee is **local-only + gitignored + never exported without the
  explicit `exchange-export` step**.

### Pytest list

- Gate suites green (capture call sites must not change router return values).
- **New** `tests/test_exchange_log.py`: `test_capture_on_by_default`,
  `test_kill_switch_env`, `test_per_request_optout`,
  `test_secret_shapes_redacted`, `test_never_raises_on_unwritable_dir`,
  `test_joinable_to_receipt_via_hash`, `test_gitignored`.
- **New** `tests/test_transcript_harvest.py`: `test_idempotent_rerun`,
  `test_dedup_by_content_hash`, `test_malformed_source_skipped`,
  `test_sources_never_mutated`, `test_schema_matches_exchange`.
- **New** `tests/test_exchange_export.py`: `test_filters_apply`,
  `test_writes_only_to_inbox`, `test_empty_export_fails`.

---

## 5. The ideal end state — Odysseus as the go-to for everything

What "go-to for everything" concretely means once Briefs 1–6 + adoption land:

1. **One verb.** `ody route "<anything>"` from any terminal — classified,
   quota-routed, worktree-isolated, receipted, captured. The web UI is the
   same brain with a face; the scheduler is the same brain on a clock.
2. **One audit trail.** "What ran, what did it cost, what broke" =
   `traces.jsonl` + `agent-audit diff`. Per-repo forensics = flight
   recorder. Session memory = memjuice. No overlap, no gaps.
3. **One corpus.** Every inference — routed through Odysseus OR run in any
   CLI — lands in `exchanges/` in one schema. Your work product stops
   evaporating into five log formats nobody reads.
4. **One flywheel.** Corpus → pioneer-adaption datasets → evals → a model
   tuned on YOUR task distribution → new backend in the router's priority
   list → cheaper routing → more traffic → better corpus. Each loop
   iteration is measured by Brief 5 rollups (tokens/day by class), not vibes.
5. **One safety posture.** PCR gates admissions, Infisical holds keys,
   worktrees isolate code runs, exports to Pioneer are explicit and
   human-triggered, external writes still require approval. Capture is broad
   but the blast radius stays local.

Sequencing: Brief 6 slots **after Brief 1** (needs the mounted router) and
can run parallel to Briefs 4/5 (disjoint files; the gzip step lands with 5).
Harvester + export are independent of 2/3.

## 6. Maximization — the last real leverage, then we stop planning

### 6.1 Capture at the chokepoint, not the router (Brief 6 amendment)

Survey finding: `llm_call_async` (`src/llm_core.py`) is imported by **28
files** — chat, scheduler tasks, research, notes, email, summaries, agent
loops. The router is one caller among many. Capturing inside
`llm_call_async` (plus `route_code`'s subprocess path, which bypasses it)
means:

- **The corpus fills itself from day one of merge** — every chat message you
  already send through the odysseus UI is an exchange. The adoption risk
  ("build it and route nothing through it") still matters for *routing*
  value, but no longer gates *corpus* value. The flywheel starts immediately.
- One `source` field distinguishes `chat | scheduler | router | research |
  …` via the existing `prompt_type` argument — free provenance.
- Same rules: never raises, kill switch, redaction, gitignored, local-only.

### 6.2 Chat-through-router (Brief 7, Phase 2 — after Brief 2 proves stable)

The odysseus chat UI is your highest-traffic surface. Once the router is
trustworthy, add an opt-in setting: chat messages classified `chat`/cheap go
through `POST /api/route` instead of the default model. Routing adoption
stops being a habit change and becomes the default path of tools you already
use. Spec it only after two weeks of Brief 1–6 runtime — it touches the
hot path you use daily, so it earns extra caution.

### 6.3 Golden eval set — closes the loop with teeth

pioneer-adaption already has `evals/` (2 v0 files). After ~2 weeks of
corpus: curate ~50 representative exchanges (mix of classes, incl. failures)
into `evals/odysseus_golden.v0.json`. Then the rule: **no routing-policy
change (incl. future `propose` output) merges without running the golden
set** — same receipts-not-vibes posture, applied to the router's own
evolution. This is what makes "the router improves from its own traffic"
falsifiable instead of aspirational.

### 6.4 Failure mining — corrections for free

Every `error: true` receipt joined (via `task_hash`) to a later successful
exchange of the same task IS a pioneer-adaption correction pair
(`corrections.v0.jsonl` format already exists). A `--corrections` flag on
`exchange-export` mines these automatically. Failures stop being waste.

### 6.5 Corpus durability

`exchanges/` is gitignored — which also makes it invisible to repo-based
backup flows. Add `data/orchestration/` to the existing backup_routes
export (it already handles user data) or confirm Time Machine covers it.
A flywheel you can lose in one disk failure is not an asset.

### 6.6 The honest stop

That's the ceiling of useful planning. Seven briefs, three phases, one
flywheel, one eval gate, one backup line. Anything further added now is
speculation that real traffic will invalidate. **The single highest-value
next action is no longer a document — it's merging Brief 1.** Plan quality
is now the constraint on nothing; execution is the constraint on everything.

## Non-goals (additions to the standing list)

No cloud sync of exchanges or transcripts. No auto-export to Pioneer. No
training runs triggered by Odysseus. No sixth router. No resurrecting
`unified-personal-os` / `orchestrator-mvp` — harvest their ideas, archive
their code.
