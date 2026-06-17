#!/usr/bin/env python3
"""Summarize M3 routing extraction into an action report.

Reads  ~/projects/odysseus/.credit-lab/routing_dataset.jsonl
Writes ~/projects/odysseus/.credit-lab/m3_decision_report.md

The report is intentionally compact: counts, top patterns, representative
reports, and concrete follow-up lanes for ody/tools/hooks/skills.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

DATASET = Path.home() / "projects/odysseus/.credit-lab/routing_dataset.jsonl"
REPORT = Path.home() / "projects/odysseus/.credit-lab/m3_decision_report.md"
ATLAS_FEED = Path.home() / ".atlas/odysseus_m3_feed.md"

LANES = {
    "malformed-diff": {
        "lane": "diff/apply harness",
        "action": "Stop accepting model-invented hunk geometry; require find/replace or validate/regenerate unified-diff headers before apply.",
        "targets": "ody executor, patch validation hook, coding skills",
    },
    "wrong-file": {
        "lane": "context targeting",
        "action": "Require target file/function evidence before editing; reject missions without a resolvable symbol/file anchor.",
        "targets": "mission prompt schema, repomap selection, ody preflight",
    },
    "test-never-ran": {
        "lane": "validation discipline",
        "action": "Make completion impossible without the smallest relevant test command or an explicit blocker record.",
        "targets": "TDD skill, completion hook, bg-worker acceptance contract",
    },
    "halt-message": {
        "lane": "prompt/safety framing",
        "action": "Add authorized-context framing and route suspicious refusals into a retry path before marking mission failed.",
        "targets": "agent rules, safety preamble, provider routing policy",
    },
    "empty-output": {
        "lane": "provider/runtime reliability",
        "action": "Add empty-output retry, timeout classification, and provider/task-shape routing evidence.",
        "targets": "TokenRouter config, subscriptions, ody retry policy",
    },
    "timeout": {
        "lane": "runtime limits",
        "action": "Split long missions, lower prompt size, or route timeout-heavy task shapes away from weak providers.",
        "targets": "mission sizing, provider routing, timeout policy",
    },
    "landed": {
        "lane": "positive examples",
        "action": "Mine landed rows into golden few-shot mission examples and regression checks.",
        "targets": "mission brief generation, skills, evaluator tests",
    },
}


def load_rows(path: Path) -> list[dict]:
    try:
        import duckdb
        return duckdb.sql(
            f"SELECT * FROM read_json({str(path)!r}, auto_detect=true)"
        ).df().to_dict("records")
    except Exception:
        pass
    rows = []
    with path.open() as fh:
        for line in fh:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def sample_ids(rows: list[dict], key: str, value: str, limit: int) -> list[str]:
    picked = []
    for row in rows:
        if row.get(key) != value:
            continue
        rid = row.get("report_id")
        if rid:
            picked.append(rid)
        if len(picked) >= limit:
            break
    return picked


def feature_counts(rows: list[dict]) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        for feature in row.get("mission_features") or []:
            counts[feature] += 1
    return counts


def render(rows: list[dict], sample_limit: int) -> str:
    outcomes = Counter(row.get("outcome", "unknown") for row in rows)
    failures = Counter(row.get("failure_mode", "unknown") for row in rows)
    report_types = Counter(row.get("report_type", "unknown") for row in rows)
    features = feature_counts(rows)
    extract_errors = sum(1 for row in rows if row.get("extract_error"))

    lines = [
        "# M3 Decision Report",
        "",
        f"Dataset rows: **{len(rows)}**",
        f"Extraction errors: **{extract_errors}**",
        "",
        "## Outcome counts",
        "",
    ]

    for outcome, count in outcomes.most_common():
        lines.append(f"- `{outcome}`: {count}")

    lines += ["", "## Report types", ""]
    for rtype, count in report_types.most_common():
        lines.append(f"- `{rtype}`: {count}")

    lines += ["", "## Top failure modes → action lanes", ""]
    for mode, count in failures.most_common(12):
        lane = LANES.get(mode, {
            "lane": "triage",
            "action": "Inspect representative reports and decide whether this is a new failure class.",
            "targets": "M3 taxonomy, mission brief generator",
        })
        pct = (count / len(rows) * 100) if rows else 0
        lines += [
            f"### `{mode}` — {count} rows ({pct:.1f}%)",
            f"- Lane: {lane['lane']}",
            f"- Action: {lane['action']}",
            f"- Targets: {lane['targets']}",
            "- Representative reports:",
        ]
        for rid in sample_ids(rows, "failure_mode", mode, sample_limit):
            lines.append(f"  - `{rid}`")
        lines.append("")

    lines += ["## Top mission features", ""]
    for feature, count in features.most_common(25):
        lines.append(f"- `{feature}`: {count}")

    landed = [row for row in rows if row.get("outcome") == "landed" or row.get("failure_mode") == "landed"]
    lines += ["", "## Landed rows to mine as positive examples", ""]
    if landed:
        for row in landed[:sample_limit * 2]:
            lines.append(f"- `{row.get('report_id')}` features={row.get('mission_features') or []}")
    else:
        lines.append("- None yet")

    lines += [
        "",
        "## Recommended next actions",
        "",
        "1. Regenerate mission briefs from the completed dataset.",
        "2. Pick one high-confidence brief from the highest-count actionable failure mode.",
        "3. Run exactly one `ody` mission in a worktree and capture diff + validation evidence.",
        "4. Patch the corresponding lane (rules/hooks/skills/tools) only after the ody run proves the failure mode is real.",
        "5. Move landed examples into golden prompts/regression fixtures.",
        "",
        "## What not to decide yet",
        "",
        "- Do not rewrite Atlas/tools/hooks/skills from counts alone; require at least one representative verified run.",
        "- Do not merge M3 analysis and ody implementation roles.",
        "- Do not start many missions before the executor path is proven on one mission.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--output", type=Path, default=REPORT)
    parser.add_argument("--atlas-feed", action="store_true",
                        help=f"Also write {ATLAS_FEED}")
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    rows = load_rows(args.dataset)
    report = render(rows, args.sample_limit)
    if args.stdout:
        print(report, end="")
    else:
        args.output.write_text(report)
        print(f"Wrote {args.output} ({len(rows)} rows)")

    if args.atlas_feed:
        ATLAS_FEED.write_text(report)
        print(f"Wrote {ATLAS_FEED} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
