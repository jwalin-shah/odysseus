# ody-router (V3.1)

Replaces `v2/.venv/bin/ody-router` with a static Go binary that runs the same
waterfall (claude-a → claude-b → pioneer → codex) and CLI surface as
`v2/src/sys_router.py`. Stdlib only, no third-party deps, target <2ms per
call steady-state. V3.1 emits the simulated "Routed to <model> successfully"
line; real provider API passthrough is V3 Phase 2.
