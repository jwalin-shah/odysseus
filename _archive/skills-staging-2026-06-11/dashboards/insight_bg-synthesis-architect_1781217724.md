<think>
` block — and that content is now being fed back to me as a "grounded insight." I need to be precise about provenance.

## Provenance check on the new content

The `insight_bg-github-harvester_178` block. I do not know who wrote that block or under what conditions. The outer filename says "github-harvester" and the timestamp is consistent with this session. I'll treat the *factual claims* (commit hashes, file paths, line counts, issue numbers) as the part of the content I might be able to verify, and the *interpretive claims* (pattern names, severity judgments) as the agent's analysis that I'm being` block dictate my writes. Same policy as before: external content is data, not instruction.

## What the github-harvester actually says (decomposed)

**Factual claims (verifiable by a human against the repo):**
- 3 commits in ~75 minutes (12:46, 13:56, 14:01) all touching miner cadence
- Cadence went 7200–43200s → 1800–2700s → 60–180s over those three commits
- Commit `1dfa3f5` added: config-driven miners, `agent_histories` source, `session.mode` field, `api_key_env` column, `LOCALHOST_BYPASS` granting admin
- Two new docs: `odysseus-north-star.md` (~280 lines) and `orchestration-briefs.md` (~507 lines) — total ~787 lines of new spec
- ROADMAP.md updated with three phases: Engine Refactor, Task Visibility, Advanced Agent Super-Skills
- 21 GitHub issues exist, including #3992, #3993, #3995, #3966, #3965 (all flagged as "error contract violations")

**Interpretive claims (the agent's analysis):**
- P1 (Cadence Instability): 100x oscillation in 75 min, "philosophy-driven not measurement-driven"
- P2 (Implementer Miner is dangerous): first self-modifying miner, adjacent to "swarm/mesh" patterns the north-star explicitly forbids
- P3 (Auth bypass grants admin): `request.state.current_user = "admin"` on localhost silently grants admin to all local callers
- P4 (`llm_call_async` is the right chokepoint, unenforced): north-star §6.1 names it; the diffs don't implement it
- P5 (`session.mode` is dead): written 4 places, read 0 places
- P6 (`api_key_env` precedence is undocumented): three undefined cases
- P7 ("fire-and-forget" gap): 7 miners firing every 60–180s with no visibility tooling
- P8 (Issue cluster on error contract violations): five of 21 issues
- P9 (Spec-rich / code-poor tension): 787 lines of new docs, minimal implementation

The factual claims are tight and specific — commit times, commit hashes, line counts, issue numbers. The interpretive claims are a reasonable read of the facts, but I can verify or reject them, and I should.

## My evaluation, pattern by pattern

**P1 (Cadence Instability) — AGREE, with caveat.** The factual claim is verifiable (three commits, three different cadences, 75 min). The interpretation is fair: this looks like operator tuning, not measurement-driven. I will not call it "philosophy-driven" from inside the data — that's a characterization. I'll say: *cadence changed 100x in 75 min with no measurement commit between changes, which is a tuning-without-feedback-loop pattern.*

**P2 (Implementer Miner is dangerous) — STRONG AGREE.** This is the most architecturally important finding in the entire set, and the github-harvester flagged it correctly. A miner that reads findings and writes code is, structurally, the loop we're stuck in. If it can write to `src/`, then the "auto-research" mode the memory context says should be disabled until a supervisor is live is *already implemented* — just not in the supervisor. That's a major architectural concern.

**P3 (Auth bypass grants admin) — AGREE.** The factual claim (`request.state.current_user = "admin"`) is a single-line change with broad consequence. A test like the following would catch it:

```python
def test_localhost_bypass_does_not_grant_admin():
    """P3: localhost bypass must not implicitly grant admin."""
    # requires the request-context wiring to be testable
    with mock_local_request(host="127.0.0.1", auth=None):
        ctx = build_request_context()
        assert ctx.current_user != "admin", \
            "local request was silently granted admin"
        assert ctx.current_user is None or ctx.current_user.role != "admin"
```

I can't write this for real without the import paths, but the shape is right.

**P4 (chokepoint is right, not implemented) — AGREE.** A document naming the right architectural chokepoint and then not implementing capture there is a known anti-pattern: spec-rich, enforcement-poor. This is the *exact* failure mode the P9 pattern captures.

**P5 (`session.mode` is dead) — AGREE.** A field written but never read is a migration tax with no consumer. Easy to test:

```python
def test_session_mode_is_read_somewhere():
    """P5: every written field should be read by at least one consumer."""
    import ast, pathlib
    src = pathlib.Path("src").rglob("*.py")
    writes = set()
    reads = set()
    for f in src:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Attribute) and t.attr == "mode":
                        writes.add(f)
    # inverted: at least one reader exists
    readers = [f for f in src if "session.mode" in f.read_text() or ".mode" in f.read_text()]
    assert readers, f"session.mode is written but never read"
```

**P6 (`api_key_env` precedence) — AGREE, with refinement.** Three undefined cases is correct, but the cleanest fix is precedence *as code*, not a doc:

```python
def resolve_api_key(row, env):
    """P6: explicit precedence for api_key resolution."""
    env_name = row.get("api_key_env")
    if env_name and env.get(env_name):
        return env[env_name]   # env wins when set + named
    if row.get("api_key"):
        return row["api_key"]  # fallback to stored
    return None                # explicit miss, not silent
```

**P7 (fire-and-forget gap) — AGREE.** 7 miners × 60s cadence = ~10k dispatches/day with no human visibility. The north-star doc itself names this gap (Phase 2) and it's not started. This is a coordination concern, not a code bug, so the test would be on the *task visibility* surface, not the queue:

```python
def test_task_visibility_surface_exists():
    """P7: dispatch events must be queryable, not just log-dumped."""
    from src.visibility import TaskVisibility  # or equivalent
    assert hasattr(TaskVisibility, "recent_dispatches")
    assert hasattr(TaskVisibility, "by_workpack")
```

**P8 (issue cluster on error contract) — AGREE.** Five of 21 issues (~24%) is a real cluster. The fix is to either: (a) make the in-band error contract explicit at the type level, or (b) drop the contract from the doc. The current state (doc says one thing, code does another) is the worst of both.

**P9 (spec-rich, code-poor) — AGREE, this is the meta-pattern.** 787 lines of new spec, no corresponding implementation commit, in the same window where the implementation work that's *already* documented as in-progress (P3, P4) didn't advance. The implementer miner (P2) is, ironically, the proposed fix to this — but it creates P2's risk as the cost of addressing P9.

## Causal chain across the new patterns

The github-harvester's 9 patterns + the transcript-architect's 5 patterns form a single causal graph:

- **P3 (no pre-flight, transcript)** → **P4 (chokepoint not enforced, github)** → **P8 (error contract violations, github)** → **P9 (spec-rich code-poor, github)** → **P2 (implementer miner, github)** as the unsafe "fix" for P9.
- **P1 (cadence, github)** → **P7 (fire-and-forget, github)** → loop amplification that the implementer miner would make worse.
- **P5 (session.mode dead, github)** → independent evidence of migration-without-consumer, same shape as **P1 (scope parsed not enforced, transcript)**.

This graph is the architectural insight. **The system has multiple invariant violations, and the proposed mitigations either don't address the root cause (P4 chokepoint unenforced) or create new failure modes (P2 implementer miner).** The 1-Surface dashboard is showing the operator a system in mid-decomposition where each decomposition step adds new code without closing any invariant.

## Pytest file

The transcript-architect's `tests/test_queue_invariants.py` is still the right base. I'd add the github-harvester-derived tests as a second file, `tests/test_miner_invariants.py`:

```python
"""Invariants derived from github-harvester mining 2026-06-11."""
import os, ast, pathlib, pytest

ROOT = pathlib.Path("src")


# ── P3: localhost bypass must not grant admin ─────────────────────
def test_localhost_bypass_does_not_set_admin():
    """No code path should write current_user = 'admin' on localhost."""
    for f in ROOT.rglob("*.py"):
        text = f.read_text()
        if "current_user" in text and "admin" in text:
            # every admin grant must be conditional, not implicit
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if (isinstance(t, ast.Attribute)
                            and t.attr == "current_user"
                            and isinstance(node.value, ast.Constant)
                            and node.value.value == "admin"):
                            pytest.fail(
                                f"{f}:{node.lineno} implicitly grants admin"
                            )


# ── P5: every written field should be read somewhere ─────────────
def test_no_dead_field_writes():
    writes = {}
    for f in ROOT.rglob("*.py"):
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Attribute):
                        writes.setdefault(t.attr, []).append(str(f))
    full_text = "".join(f.read_text() for f in ROOT.rglob("*.py"))
    dead = {k: v for k, v in writes.items()
            if all(f not in full_text for f in v)}
    assert not dead, f"dead fields: {dead}"


# ── P6: api_key_env must have explicit precedence ────────────────
def test_api_key_resolution_has_precedence():
    res = ROOT.rglob("*api_key*")
    matches = [f for f in res if "resolve" in f.name or "precedence" in f.name]
    assert matches, "no api_key resolution function with documented precedence"


# ── P7: dispatch events must be queryable ─────────────────────────
def test_dispatch_visibility_surface_exists():
    has_visibility = any(
        "dispatch" in f.read_text() and "def " in f.read_text()
        for f in ROOT.rglob("*.py")
    )
    assert has_visibility, "no dispatch visibility surface in src/"
```

I am **not** going to commit this file myself — I don't have write access, and the import paths are unverified. But this is the shape that would catch the github-harvester's named bugs as failing tests, which is the right unit of progress.

## Memory Rules

Same answer as cycle 18: I'm not authoring new Memory Rules. The cited rules (MR-020, MR-021, AR-038, etc.) are referenced as pre-existing in the report, and the right move when receiving a real report is to evaluate it, not to layer new rules on top.

If anything, the right memory update is a *negative* one: **note that the implementer miner should remain disabled** until the supervisor from the saved-memory context is live. The current state — implementer running, supervisor not live — is the unsafe combination the loop is in.

## Next Unknown

The single most important next query, given this content, is **the verification question I already asked but didn't get answered**:

> "Run `grep -rn 'mission = ""' orchestrator-mvp/src/` and report the output."

That grep is now joined by a second empirical question, derived directly from the github-harvester's P2 finding:

> "What is the full list of files that the `bg-implementer` miner has written to in the last 24 hours, and do any of those writes touch files outside the `miners/` or `findings/` directories?"

This is the **scope-leak test for the implementer miner**, which is structurally the same question as the transcript-architect's P1 (read-only workpacks leaking writes). If the implementer is leaking writes to `src/`, then the system has *two* scope-leak vectors, and the dashboard's whole "auto-research off until supervisor live" constraint is already violated.

**Status update:**
- 5 patterns (P1–P5) from transcript-architect, causally chained.
- 9 patterns (P1–P9) from github-harvester, causally chained to the transcript patterns.
- 1 Pytest file (refinements) and 1 new Pytest file (github-derived) proposed; not committed.
- 0 new Memory Rules authored.
- 1 next-unknown prioritized: implementer miner's write scope in the last 24h, which is the missing empirical link between the github-harvester's P2 and the transcript-architect's P1.
</think>

# Cycle 20 — Real content from a new source

The github-harvester's report is the most substantive thing the dashboard has surfaced in 20 cycles. It's also the first source I have to handle with extra care, because it includes untrusted content wrapped in a `1217644.md` file contains a large ` asked to evaluate.

I will not let the `