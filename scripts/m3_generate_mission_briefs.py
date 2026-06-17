#!/usr/bin/env python3
"""M3 job: turn routing_dataset.jsonl into actionable mission briefs.

Reads  ~/projects/odysseus/.credit-lab/routing_dataset.jsonl
Reads  ~/projects/sandbox-bg-agents/evidence/*.md  (for report bodies)
Writes ~/projects/odysseus/.credit-lab/mission_queue.jsonl

Algorithm:
  1. Group extracted rows by failure_mode.
  2. For each top-N failure modes, sample up to 10 representative reports.
  3. Send the sample to M3 — ask for a concrete mission brief:
       {file, function, bug_description, proposed_test, mission_prompt, confidence}
  4. Append each brief to mission_queue.jsonl.

Validate the queue before dispatch:
  python3 scripts/m3_run_mission_queue.py

Dispatch validated briefs only with explicit approval:
  python3 scripts/m3_run_mission_queue.py --execute

Usage:
  python3 scripts/m3_generate_mission_briefs.py [--top N] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import collections
from pathlib import Path

DATASET   = Path.home() / "projects/odysseus/.credit-lab/routing_dataset.jsonl"
EVIDENCE  = Path.home() / "projects/sandbox-bg-agents/evidence"
QUEUE     = Path.home() / "projects/odysseus/.credit-lab/mission_queue.jsonl"
M3_CMD    = "m3"

# Failure modes worth generating missions for — skip analysis-only and landed
ACTIONABLE_MODES = {
    "malformed-diff", "wrong-file", "test-never-ran",
    "empty-output", "unknown", "failed",
}

BRIEF_PROMPT = """\
You are a senior engineer writing concrete fix briefs for junior agents.

I will give you {n} evidence reports from an autonomous coding agent.
All of them share the same failure pattern: {failure_mode}.

Your job: produce ONE concrete mission brief that a coding agent can execute.
The brief must be specific enough that a fresh agent with no context can act on it.

Return EXACTLY this JSON — no other text:
{{
  "failure_mode": "{failure_mode}",
  "affected_files": ["<list of repo-relative file paths involved>"],
  "root_cause": "<one sentence — what is actually broken>",
  "proposed_fix": "<one paragraph — exactly what to change and why>",
  "proposed_test": "<pytest invocation or test name that would verify the fix>",
  "mission_prompt": "<the exact 1-2 sentence prompt to give `ody` — imperative, specific, actionable>",
  "confidence": <0.0-1.0 float — how confident you are this is the real root cause>,
  "sample_count": {n}
}}

Evidence reports (truncated to 800 chars each):
---
{reports}
---
"""


def load_dataset() -> list[dict]:
    if not DATASET.exists():
        return []
    try:
        import duckdb
        return duckdb.sql(
            f"SELECT * FROM read_json({str(DATASET)!r}, auto_detect=true)"
        ).df().to_dict("records")
    except Exception:
        pass
    rows = []
    with open(DATASET) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def load_report_body(report_id: str) -> str:
    path = EVIDENCE / f"{report_id}.md"
    if not path.exists():
        return f"[report not found: {report_id}]"
    try:
        return path.read_text(errors="replace")[:800]
    except Exception:
        return "[read error]"


def call_m3(prompt: str) -> dict | None:
    try:
        result = subprocess.run(
            [M3_CMD, prompt],
            capture_output=True, text=True, timeout=180,
        )
        raw = result.stdout.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return None
        return json.loads(match.group(0))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None


def already_queued(failure_mode: str) -> bool:
    if not QUEUE.exists():
        return False
    with open(QUEUE) as f:
        for line in f:
            try:
                row = json.loads(line)
                if row.get("failure_mode") == failure_mode:
                    return True
            except Exception:
                pass
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=5,
                        help="Number of failure mode clusters to brief (default 5)")
    parser.add_argument("--samples", type=int, default=8,
                        help="Reports per cluster to send M3 (default 8)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print cluster stats only, no M3 calls")
    parser.add_argument("--force", action="store_true",
                        help="Re-generate briefs even if already in queue")
    args = parser.parse_args()

    rows = load_dataset()
    if not rows:
        print(f"No data in {DATASET} — run m3_extract_routing_dataset.py first.")
        sys.exit(1)

    print(f"Loaded {len(rows)} extracted rows from dataset.", flush=True)

    # Group by failure_mode, only actionable ones
    by_mode: dict[str, list[dict]] = collections.defaultdict(list)
    for row in rows:
        mode = row.get("failure_mode", "unknown")
        if mode in ACTIONABLE_MODES:
            by_mode[mode].append(row)

    # Rank by count
    ranked = sorted(by_mode.items(), key=lambda x: len(x[1]), reverse=True)

    print(f"\nFailure mode distribution (actionable):")
    for mode, cluster in ranked:
        print(f"  {len(cluster):5d}  {mode}")
    print()

    if args.dry_run:
        print("Dry run — no M3 calls.")
        return

    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    out = open(QUEUE, "a")
    generated = 0

    for mode, cluster in ranked[: args.top]:
        if not args.force and already_queued(mode):
            print(f"[{mode}] already in queue — skipping (use --force to regenerate)")
            continue

        # Sample: prefer coding reports, take diverse report_ids
        coding = [r for r in cluster if r.get("report_type") == "coding"]
        sample_pool = coding if len(coding) >= args.samples else cluster
        # Take evenly spaced samples across the pool for diversity
        step = max(1, len(sample_pool) // args.samples)
        sample = sample_pool[::step][: args.samples]

        report_bodies = []
        for row in sample:
            body = load_report_body(row["report_id"])
            report_bodies.append(f"## {row['report_id']}\n{body}")
        reports_text = "\n\n---\n\n".join(report_bodies)

        prompt = BRIEF_PROMPT.format(
            n=len(sample),
            failure_mode=mode,
            reports=reports_text,
        )

        print(f"[{mode}] Generating brief from {len(sample)} samples...", flush=True)
        brief = call_m3(prompt)

        if brief is None:
            print(f"[{mode}] M3 returned no parseable JSON — skipping", flush=True)
            continue

        # Add metadata
        brief["generated_at"] = time.time()
        brief["cluster_size"] = len(cluster)
        brief["dataset_rows"] = len(rows)

        out.write(json.dumps(brief) + "\n")
        out.flush()
        generated += 1

        mp = brief.get("mission_prompt", "")
        conf = brief.get("confidence", "?")
        print(f"[{mode}] ✓ confidence={conf}  prompt={mp[:80]!r}", flush=True)

    out.close()
    print(f"\nDone. {generated} briefs written to {QUEUE}", flush=True)
    print("\nTo validate the queue:")
    print("  python3 scripts/m3_run_mission_queue.py")
    print("To dispatch validated briefs:")
    print("  python3 scripts/m3_run_mission_queue.py --execute")


if __name__ == "__main__":
    main()
