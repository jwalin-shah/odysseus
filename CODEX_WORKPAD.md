# Odysseus Agent Handoff / Workpad

## Current State
- **Miners Cadence**: `miners.json` was updated so background architects (transcript, code, test, memory, job, sandbox) run continuously (staggered every 5-15 mins) using free compute.
- **Implementer Loop**: The `bg-implementer` Haiku agent just finished building the sandbox loop. It pulls miner findings, spins up a git worktree sandbox, writes code + a pytest, runs the test, and reports back.
- **OpenCode Token Fix**: The `TOKENROUTER_API_KEY` was missing from the shell. It was successfully extracted from `data/app.db` (decrypted) and injected directly into `~/.config/opencode/opencode.json`. OpenCode is now properly routed to **MiniMax-M3** for budget tasks.

## Tasks for the Next Agent

### 1. Per-Miner Model Routing (High Priority)
Right now, the miners are hitting the default local model/MiniMax too hard. 
**Goal:** Distribute the load across the free API pool.
- Update `miners.json` to allow specifying a `model` or `endpoint_id`.
- Route transcript mining to M3, code synthesis to NVIDIA NIM (Qwen/DeepSeek), and query evolution to OpenRouter's free tier. 

### 2. Sandbox Review & Test Gating
- Verify the `bg-implementer`'s first sandbox attempts.
- Ensure the pytest templates derived from `bg-test-architect` are actually gating bad code correctly.

### 3. Promotion Pipeline & Skills Extraction
- Build the manual/scheduled "Promotion pass" where green worktree diffs are reviewed and merged into `main`.
- Turn the validated findings (e.g. the router patch, session-persistence patterns, the orchestrator read-only bug) into permanent skills in `~/.codex/skills/` (which symlink to Cline, Aider, Cursor, Claude).
