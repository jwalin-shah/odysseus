# ody — the front door

One command. It routes, isolates, gates, and logs. You talk to `ody`; it talks
to everything else.

```bash
ody 'fix the failing test in v2/src/sys_quota.py'   # code lane
ody 'review the v2 router for security'             # analyze lane (M3 direct)
ody 'find arxiv papers on agent routing'            # research lane (arxiv API)
ody run '<mission>' --repo DIR --test 'pytest -q'   # explicit form + options
ody ask --pane current 'what is happening'          # tmux observability (v1)
ody start|stop|status|logs|sessions                 # v1 app, unchanged
```

## Lanes

| Lane | Trigger words | Engine | Safety |
|---|---|---|---|
| code | fix/implement/rewrite/bug/failing… | claude → pioneer-opus → codex | git worktree + test gate; red = discarded, green = committed on an `ody-*` branch (never main) |
| analyze | review/summarize/diagnose/why… | **M3 direct** (TokenRouter, free) → gemini | read-only prompt contract |
| research | arxiv/paper/literature | arxiv API, no LLM | read-only |

Overrides: `--lane`, `--tool`, `--dry-run`, `--no-docs`, `--timeout`.

## The law (from .credit-lab/mining/FINDINGS.md, n=5,574)

- M3 as coder: **0/257** test-fix attempts passed (89% malformed diffs).
  M3 is therefore hard-excluded from the code waterfall.
- Direct targeted Python fixes: 10/10. The test gate is the only verdict.
- `m3 "question"` / `cat x | m3 "summarize"` — standalone direct client
  (`src/m3.py`, ~/bin/m3) for free bulk analysis. It never writes code.

## Harness (constraint layer)

`sys-quota` (atomic SQLite quota, exit 75 = exhausted) gates dispatch;
`sys-router` is the quota-aware waterfall; `ody-map` (AST repo map) feeds
context into coder prompts. All 27 v2 tests green. Rebuild shims after any
venv rebuild: `v2/scripts/make-shims.sh`.

## Feedback

Every call appends `{ts, prompt, lane, agent_used, result, test_passed,
duration}` to `.credit-lab/ody/`. That stream + the mined
`routing-dataset.jsonl` is the training set for the learned router (next).

Unit tests: `python3 -m pytest tests/test_odysseus.py -q`.
