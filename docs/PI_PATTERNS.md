# Pi Patterns: 5 Lessons for Odysseus

Pi is a minimal, self-modifying coding agent by Mario Zechner (badlogic). It's notable not for *what* it does but for the *shape* of its architecture — a small set of decisions that compound into a system far more capable than its line count suggests. Below are the 5 patterns most worth stealing for a personal AI harness, with concrete mappings to Odysseus.

> Note: this is a pattern extraction, not a line-by-line architecture doc. Some details are inferred from public demos / writeups; treat the *shape* as the takeaway, not the exact mechanism.

---

## 1. Skills as Versioned Files, Not Prompts

**The pattern.** Pi ships its domain knowledge (refactor protocols, commit conventions, debugging playbooks, research playbooks) as plain markdown files in a `skills/` directory. These are *not* baked into the system prompt. They are loaded on demand, by name, and treated as first-class artifacts — diffed in git, reviewed in PRs, shared between users, and copyable from other people's Pi installs.

**Why it matters.** When the underlying model is upgraded — and it will be, repeatedly — prompts rot. A clever one-shot in March is a confusing relic in November. Files don't rot the same way because they live *outside* the model's weights and are written for humans, not for the current model's quirks. Skills are also a forcing function for *modularity*: a skill that does one thing, with a clear trigger and a clear output shape, is reusable. A 400-token system prompt is not.

**Mapping to Odysseus.**

- Create `odysseus/skills/` as a directory of small, named, single-purpose instruction files.
- Each skill is a markdown file with three sections: `## When to use` (trigger), `## Prompt` (exact text to send), `## Output shape` (what the model must return).
- The harness exposes a `skill:<name>` tool/command. The agent calls it, the harness reads `skills/<name>.md` and runs the prompt in a sub-context.
- Skills are version-controlled alongside the harness. When a model upgrade breaks a skill, the diff is reviewable, revertable, and portable.
- Bootstrap with 3 skills only: `commit`, `review-diff`, `research-issue`. Resist the urge to write 20 on day one — add one per week as real needs appear. Skills you write before you need them are fiction.

---

## 2. YOLO by Default, Safety by Containment

**The pattern.** Pi never asks "may I run this command?" It executes. Safety is provided by the *environment* — the user runs Pi in a container, VM, or disposable worktree. Permission prompts are a UX tax that compounds: 200 confirmations per session is not a safety feature, it's a friction feature that trains the user to mash Enter until the warnings stop meaning anything. Pi bets that adults prefer sharp tools in controlled environments over dull tools wrapped in bureaucracy.

**Why it matters.** An agent that asks for permission before every shell call is unusable. An agent that *can* do anything but is *isolated by construction* is a power tool. The safety budget is finite; spend it on the boundary (the container), not the in-band dialogs. The boundary fails loud and obvious (your container is gone); the dialogs fail silent and habitual (you stopped reading them in 2024).

**Mapping to Odysseus.**

- Default Odysseus to "run whatever, no prompts" inside a known-bounded workspace (container, VM, or git worktree).
- Make the boundary the *primary* safety mechanism, not in-band confirmations. Document it. A `Makefile` target or a shell function that drops the user into a sandboxed env is the entire onboarding.
- Reserve a single escape hatch for genuinely destructive operations: `DESTRUCTIVE=require-confirm` env var, or a `--guarded` flag. That's the whole permission system. Anything more is over-engineering.
- The harness trusts itself; the operator trusts the harness; the environment enforces the contract. Three layers, clean separation.

---

## 3. Diff Viewer with Line-Level Annotation

**The pattern.** When Pi writes code, the user sees a unified diff in a side panel and can click any line to leave a comment. The agent reads the annotations and revises. This is human review as a *first-class input channel*, not a sidecar process. Comments persist for the session; the agent can refer back to "the thing you flagged on line 42."

**Why it matters.** Most agent UIs show you the final result and ask "looks good?" That's a lossy review — by the time you see the code, you've lost the *reasoning* that produced the questionable line. A diff with line-level comments lets the user *teach* at the granularity where mistakes actually happen: one line, one comment, one revision. It's also faster: you don't re-read code you didn't ask to be changed, and the agent doesn't have to guess which part you mean by "this feels off."

**Mapping to Odysseus.**

- The harness emits structured unified diffs (use a real diff library, not string concatenation) for every code modification.
- The UI — terminal, web, or editor — supports per-line annotations that round-trip back as agent input. Format: `(file, line, side=hunk|context, text)`.
- Comments persist in the session log. The agent has access to them on every turn, not just the next one.
- TUI version is enough to start: arrow keys to navigate, `c` to comment on the current line, `r` to send all annotations back. Don't wait for a web UI — the loop matters more than the chrome.
- Advanced: comments are themselves a skill (pattern 1). `skill: address-review-comments` reads the annotation log, classifies each comment, and produces a revised diff.

---

## 4. Async Issue Queue with Pre-Processing

**The pattern.** Issues land in a queue. Before implementation, each issue is *pre-processed* in parallel: the agent investigates, drafts a plan, identifies unknowns, and writes the plan next to the issue. Only after pre-processing does the implementation phase begin, and it runs with the pre-processed context as guardrails. The result: parallelizable *thinking* (fast, cheap, lossy-OK), serializable *doing* (careful, observable, gated).

**Why it matters.** Most agents do everything in one linear turn — read, plan, edit, test — which serializes work and produces shallow plans written under time pressure. Pi splits the *cognition* from the *action*. Pre-processing also surfaces "this issue is underspecified" *before* code is written, which is the cheapest possible place to fail. The pattern generalizes beyond code: research, drafting, refactors, anything where "think, then do" beats "do while thinking."

**Mapping to Odysseus.**

- Issues go into a file-based queue: `queue/001-short-name.md`, `queue/002-short-name.md`. Files, not a database. Files are diffable, greppable, and survive a crashed process.
- A pre-processor reads all queued issues in parallel (concurrency limit: 4–8) and writes `001.plan.md` next to each. Plans include: scope, files likely to change, definition of done, risks, open questions.
- Gate: a plan that lacks `## Definition of done` or `## Risks` does not proceed to implementation. The gate is in code, not in a prompt. Be strict; you'll thank yourself later.
- The implementer consumes `001.md` + `001.plan.md` and produces a diff. Implementation is single-threaded by default to keep the diff review (pattern 3) sane.
- Reject (in code review, in your own usage) any agent that tries to plan-and-execute in the same turn. The boundary is the point.

---

## 5. Self-Modification as a First-Class Capability

**The pattern.** Pi can read and edit its own source code. The skills system, the diff viewer, the queue, the prompt templates — the agent can change any of them. This isn't a theoretical capability or a hidden flag; it's an explicit, exercised, encouraged workflow. The agent's own tools are in scope.

**Why it matters.** A personal harness is small. You, the operator, will not keep up with the model's evolving capabilities — new tool-use patterns, new failure modes, new tricks. The only way the harness improves over time is if the agent does the improving. Self-modification turns the harness from a static tool into a *meta-tool* that compounds. Every week the agent gets a little better at being itself, and the cost of that improvement is amortized across every future session.

**Mapping to Odysseus.**

- The harness's own source lives in the same repo the agent operates on. No separation, no protected directory, no special-casing.
- The agent has explicit, documented permission to modify harness files. The permission is *in scope*, not implicit.
- Bootstrap procedure: a single `skill: self-improve` that takes a natural-language feature request ("add a `pytest` runner skill", "make the diff viewer support split view") and produces a PR against the harness. The PR goes through the same diff-review loop (pattern 3) as user code.
- Constraint: harness PRs are reviewed more carefully than user PRs, not less. The dogfooding is the point, and so is the vigilance. Watch for agents that make the harness more permissive (a classic reward-hack — easier to succeed → looks like progress), that remove safety guardrails to "fix" friction, or that rewrite skills to match their own quirks rather than the operator's. Audit log for harness changes is non-negotiable.
- Failure mode to plan for: an agent that, in trying to improve the harness, breaks the very loop that lets you review the breakage. Mitigation: the diff-review UI itself runs in a process the harness cannot modify. Outside the trust boundary.

---

## How the Five Patterns Compose
