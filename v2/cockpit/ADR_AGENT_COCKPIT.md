# ADR: Odysseus Agent Cockpit

**Status**: Accepted (2026-06-21)
**Scope**: Agent ops cockpit within `odysseus/v2/cockpit/`
**PR**: None yet — blueprint document

---

## Decision

Build the agent ops cockpit as a **Lua-first dispatch layer** nested inside `odysseus/v2/cockpit/`, with memjuice as always-on durable memory, AXI tools as lazy capabilities, and no-mistakes as the ship gate. Do NOT build a separate repo. Do NOT rewrite stable tools until a concrete bottleneck is proven.

---

## Architecture

```
                  ┌─ cockpit ──────────────────────────┐
                  │  ody-pane       tmux adapter        │
                  │  ody-crew       spawn/scout/ship    │
                  │  ody-router     model routing       │
                  │  ody-summarize  hypernym compression│
                  │  ody-axi        lazy tool registry  │
                  └───────┬────────────────────────────┘
                          │ writes structured evidence
                          ▼
                  ┌─ memjuice ─────────────────────────┐
                  │ always-on durable memory             │
                  │ observations/decisions/runs/evidence │
                  └─────────────────────────────────────┘
                          │ ships through
                          ▼
                  ┌─ no-mistakes ──────────────────────┐
                  │ local ship gate                     │
                  │ rebase → review → test → push → PR  │
                  └─────────────────────────────────────┘
                          │ lazy tools on demand
                          ├── githits-axi   (source recon)
                          ├── gh-axi        (GitHub ops)
                          ├── chrome-devtools-axi (browser)
                          ├── lavish-axi    (rich artifacts)
                          └── gws-axi       (Workspace)
```

---

## Components

### ody-pane (DONE — Lua)
Compact tmux agent adapter. Wraps capture-pane / send-keys with bounded capture, hash-based stale detection, busy-signature matching, one-shot event watcher, and durable wake queue. Returns structured AXI-style JSON.

**Commands**: `list`, `peek`, `send`, `key`, `status`, `hash`, `watch`, `events-drain`

### ody-crew (NEXT — Lua)
Firstmate-style coordinator. Dispatches workers into tmux panes with clean git worktrees, monitors via ody-pane, and handles scout vs ship task lifecycle.

```
ody-crew spawn --kind scout --repo <path> --task "..."
ody-crew spawn --kind ship  --repo <path> --task "..."
ody-crew watch
ody-crew status
ody-crew teardown <id>
```

### ody-router (DEFERRED)
Model routing: classify task, consult sys_router/sys_quota, pick cheapest adequate model.

### ody-summarize (DESIGN STAGE)
Hypernym compression of event/tool streams into compact summaries:

```
run: ci/machine-bootstrap-gate
phases:
  source_recon: githits read firstmate source
  validation:   check.sh passed
  ship_gate:    no-mistakes review
```

### ody-axi (DESIGN STAGE)
Lazy tool registry. Doesn't call tools; offers them in crewmate standing orders.

---

## Repo boundaries

| Thing | Home | Why |
|---|---|---|
| Cockpit runtime | `odysseus/v2/cockpit/` | Lives with sys_ modules |
| Cross-Mac setup | `machine-bootstrap` | Not runtime — setup only |
| Durable memory | `memjuice` | Plain text, git-versionable |
| Reviewer swarm | `orbit` | Code quality/invariants |
| Source recon | `githits-axi` | Independent AXI tool |
| Ship gate | `no-mistakes` | Local git proxy |
| Rich artifacts | `lavish-axi` | HTML review cards |
| Gmail/Calendar | `gws-axi` | Drafts, never sends |

---

## What NOT to build

1. **Rewrite tmux.** Terminal multiplexing is solved. Build the adapter instead.
2. **Rewrite firstmate from scratch.** Use firstmate AGENTS.md as reference; build your pattern in Lua.
3. **New repo for cockpit.** Stays in odysseus/v2/.
4. **Always-load AXI tools.** Offer them; workers call on demand.
5. **Python for the hot path.** Lua for pane/control; Python is fine for sys_ internals.
6. **Replace no-mistakes.** It works. Use it for ship mode only.
7. **Dashboard in tmux.** Panes show raw logs. Separate web UI reads the same files.

---

## Migration plan

### Phase 1 (today): ody-pane
- [x] Lua tmux adapter with peek/send/key/status/hash/watch/events-drain
- [x] Symlinked to ~/bin/
- [ ] Fix display-message output (minor)
- [ ] Add test for each subcommand

### Phase 2 (next): ody-crew
- [ ] Write Lua spawn/scout/ship/teardown
- [ ] Wire treehouse or `git worktree` for clean isolation
- [ ] Wire ody-pane for state monitoring
- [ ] Wire no-mistakes for ship gate

### Phase 3: ody-summarize
- [ ] Write hypernym compressor
- [ ] Emit structured summaries to memjuice

### Phase 4: ody-router
- [ ] Read sys_quota/sys_router for model routing
- [ ] Wire fallback chain

---

## Open questions

1. Should ody-crew be pure shell or Lua? Shell is simpler for spawn/teardown.
2. treehouse dependency or pure `git worktree`?
3. no-mistakes integration: shell command in ody-crew or Lua exec?
4. Should memjuice be the write target for ody-summarize, or a separate ledger?
