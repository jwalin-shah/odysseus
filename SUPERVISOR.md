# Odysseus Self-Improvement Supervisor

The supervisor turns mined evidence into bounded, test-gated work. It never
merges, deploys, spends paid quota, or overrides a failed test.

## Flow

1. `proposer` reads blueprint, grading, mining, GitHits, and arXiv evidence.
2. `requirements` narrows one candidate to a testable `FILE:FUNC` workpack.
3. `test_author` defines the red test and exact command.
4. `implementer` runs through `src/odysseus.py` in an isolated worktree.
5. The subprocess test gate supplies the green/red verdict.
6. `red_team` attacks green results and returns `pass` or `revise`.
7. Revision findings return to the test author and implementer, up to the
   configured attempt limit.
8. The ledger records completion/failure and prevents duplicate missions.

## State

Default directory: `.credit-lab/supervisor/`

- `mission-queue.jsonl`: immutable proposed workpacks.
- `supervisor-ledger.jsonl`: queue, retry, completion, and failure events.
- `role-receipts.jsonl`: redacted role inputs/outputs, hashes, duration,
  provider usage when reported, test verdicts, and mission lineage.

## Commands

```bash
ody supervise propose --max-missions 5
ody supervise status
ody supervise run --max-missions 5 --max-attempts 3
ody supervise run --max-missions 5 --cycles 12 --interval 300
ody supervise enqueue --mission "fix quota reset" --test "pytest -q tests/test_quota.py"
```

The final command is a bounded one-hour loop: at most five missions per cycle,
twelve cycles, five minutes apart. It exits sooner when the queue is empty.

## Research Policy

- Local tests, diffs, ledgers, and mining findings are consulted first.
- GitHits is reserved for unresolved implementation patterns. Queries must be
  deduplicated and capped at 50 per rolling 24 hours.
- arXiv is used for architecture and evaluation evidence, not hot-path coding.
- Research findings enqueue missions; research workers never write source.
- Only one implementer owns a worktree/file scope at a time.

## Stop Conditions

- Queue empty or no novel mission proposed.
- Mission or cycle limit reached.
- Three failed implementation/review attempts by default.
- Free-model or research quota exhausted.
- Test baseline degrades.
- Missing repository, test command, or owned file scope.
