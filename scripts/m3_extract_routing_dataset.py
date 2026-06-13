#!/usr/bin/env python3
"""M3 batch job: extract routing dataset from bg-fleet evidence corpus.

Reads ~/projects/sandbox-bg-agents/evidence/*.md, pre-filters noise,
sends substantive reports to M3 for structured extraction, writes
~/projects/odysseus/.credit-lab/routing_dataset.jsonl.

Each output row:
  {report_id, report_type, task_kind, outcome, failure_mode,
   agent_used, mission_features, raw_size_chars}

failure_mode taxonomy:
  malformed-diff | wrong-file | test-never-ran | timeout |
  empty-output | halt-message | refed | analysis-only | landed | unknown

Usage:
  python3 scripts/m3_extract_routing_dataset.py [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

EVIDENCE_DIR = Path.home() / "projects/sandbox-bg-agents/evidence"
OUTPUT_FILE = Path.home() / "projects/odysseus/.credit-lab/routing_dataset.jsonl"
M3_CMD = "m3"

# ── Pre-filter: skip pure noise ───────────────────────────────────────────────

# Architect reports are analysis/description — useful but different extraction
# than coding reports. We extract both but mark them separately.
_NOISE_PATTERNS = [
    re.compile(r"Bypass Attempt #\d+"),
    re.compile(r"QUOTA_EXHAUSTED"),
    re.compile(r"^.{0,50}$", re.DOTALL),  # tiny stubs (<50 chars whole file)
]

_HALT_PATTERNS = re.compile(
    r"(halt|refused|i cannot|i will not|i'm not able|as an ai|"
    r"inappropriate request|ethical|content policy)",
    re.IGNORECASE,
)


def is_noise(text: str) -> bool:
    if len(text.strip()) < 80:
        return True
    for p in _NOISE_PATTERNS:
        if p.search(text):
            return True
    return False


def report_type(filename: str) -> str:
    name = Path(filename).name
    if name.startswith("bg-imp"):
        return "coding"
    for kind in ("synthesis", "test", "token", "memory", "job",
                 "global", "transcript", "sandbox"):
        if name.startswith(kind):
            return "architect"
    return "other"


# ── M3 extraction ─────────────────────────────────────────────────────────────

EXTRACT_PROMPT = """\
You are a dataset labeler for an AI agent routing system.

I will give you one evidence report from an autonomous coding agent run.
Extract EXACTLY this JSON object — no other text, no markdown, just JSON:

{{
  "task_kind": "<code|analysis|review|unknown>",
  "outcome": "<landed|failed|unverified|analysis-only|error>",
  "failure_mode": "<malformed-diff|wrong-file|test-never-ran|timeout|empty-output|halt-message|analysis-only|landed|unknown>",
  "mission_features": ["<list of 1-4 short strings describing what the task was about, e.g. 'quota-enforcement', 'patch-application', 'test-writing', 'float-precision'>"],
  "agent_used": "<m3|claude|opencode|unknown>"
}}

Rules:
- outcome=landed means a test passed or the report shows successful completion
- outcome=failed means a test ran and failed, or patch/diff was rejected
- outcome=error means M3/agent produced malformed output (bad diff, parse error)
- outcome=unverified means the agent ran but we can't confirm result
- failure_mode must match outcome: if outcome=landed, failure_mode=landed
- agent_used: infer from report header or content; bg-quota-implementer used m3
- mission_features: 1-4 lowercase kebab-case tags for what was being worked on
- Return ONLY the JSON object. No explanation.

Evidence report:
---
{report}
---
"""


def call_m3(report_text: str, report_id: str) -> dict | None:
    prompt = EXTRACT_PROMPT.format(report=report_text[:3000])
    try:
        result = subprocess.run(
            [M3_CMD, prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        raw = result.stdout.strip()
        # M3 may include thinking text before JSON — find the JSON object
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return None
        return json.loads(match.group(0))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="Max reports to process (0=all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Pre-filter only, don't call M3")
    parser.add_argument("--skip-architects", action="store_true",
                        help="Only process coding (bg-imp) reports")
    parser.add_argument("--workers", type=int, default=1,
                        help="Concurrent M3 calls (default: 1)")
    args = parser.parse_args()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    all_files = sorted(EVIDENCE_DIR.glob("*.md"))
    print(f"Total evidence files: {len(all_files)}", flush=True)

    # Pre-filter
    substantive = []
    noise_count = 0
    for f in all_files:
        rtype = report_type(f.name)
        if args.skip_architects and rtype == "architect":
            continue
        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue
        if is_noise(text):
            noise_count += 1
            continue
        substantive.append((f, rtype, text))

    print(f"After pre-filter: {len(substantive)} substantive, {noise_count} noise skipped",
          flush=True)

    if args.limit:
        substantive = substantive[: args.limit]
        print(f"Limited to {args.limit} reports", flush=True)

    if args.dry_run:
        print("Dry run — no M3 calls. Exiting.", flush=True)
        return

    # Already-processed report IDs (resume support)
    processed_ids: set[str] = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                    processed_ids.add(row.get("report_id", ""))
                except json.JSONDecodeError:
                    pass
        print(f"Resuming — {len(processed_ids)} already processed", flush=True)

    pending = []
    skipped = 0
    for fpath, rtype, text in substantive:
        report_id = fpath.stem
        if report_id in processed_ids:
            skipped += 1
            continue
        pending.append((fpath, rtype, text, report_id))

    print(f"Pending: {len(pending)} reports, {skipped} skipped", flush=True)
    print(f"Workers: {args.workers}", flush=True)

    def extract_one(item: tuple[Path, str, str, str]) -> dict:
        fpath, rtype, text, report_id = item
        extracted = call_m3(text, report_id)

        if extracted is None:
            return {
                "report_id": report_id,
                "report_type": rtype,
                "raw_size_chars": len(text),
                "outcome": "error",
                "failure_mode": "unknown",
                "task_kind": "unknown",
                "mission_features": [],
                "agent_used": "unknown",
                "extract_error": True,
            }

        return {
            "report_id": report_id,
            "report_type": rtype,
            "raw_size_chars": len(text),
            **extracted,
        }

    out = open(OUTPUT_FILE, "a")
    landed = failed = errors = 0
    t0 = time.time()

    def write_row(row: dict, done: int) -> None:
        nonlocal landed, failed, errors
        if row.get("extract_error"):
            errors += 1
        elif row.get("outcome") == "landed":
            landed += 1
        else:
            failed += 1

        out.write(json.dumps(row) + "\n")
        out.flush()

        elapsed = time.time() - t0
        rate = done / elapsed * 60 if elapsed > 0 else 0
        print(
            f"[{done}/{len(pending)}] {row.get('report_id','')[:40]}  "
            f"outcome={row.get('outcome','?'):12s}  "
            f"rate={rate:.0f}/min  "
            f"landed={landed} failed={failed} err={errors}",
            flush=True,
        )

    if args.workers <= 1:
        for done, item in enumerate(pending, start=1):
            write_row(extract_one(item), done)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(extract_one, item) for item in pending]
            for done, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                write_row(future.result(), done)

    out.close()
    elapsed = time.time() - t0
    print(f"\nDone. {landed} landed, {failed} failed, {errors} errors, "
          f"{skipped} skipped. Total time: {elapsed:.0f}s", flush=True)
    print(f"Output: {OUTPUT_FILE}", flush=True)


if __name__ == "__main__":
    main()
