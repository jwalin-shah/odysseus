#!/usr/bin/env python3
"""Validate and optionally dispatch M3 mission briefs."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import shlex
import sys
from pathlib import Path
from typing import Awaitable, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from v2.src.mission_brief import MissionInvalid, validate
except ImportError:

    class MissionInvalid(Exception):
        def __init__(self, field: str, message: str):
            super().__init__(message)
            self.field = field

    def validate(brief: dict) -> None:
        required = [
            "affected_files",
            "proposed_fix",
            "proposed_test",
            "mission_prompt",
            "confidence",
        ]
        for field in required:
            if field not in brief:
                raise MissionInvalid(field, f"Missing required field: {field}")
        if not isinstance(brief.get("affected_files"), list) or not brief["affected_files"]:
            raise MissionInvalid("affected_files", "affected_files must be a non-empty list")
        if not isinstance(brief.get("confidence"), (int, float)):
            raise MissionInvalid("confidence", "confidence must be a number")
        confidence = float(brief["confidence"])
        if not 0.0 <= confidence <= 1.0:
            raise MissionInvalid("confidence", "confidence must be between 0 and 1")


DEFAULT_QUEUE = Path(".credit-lab/mission_queue.jsonl")
DEFAULT_RESULTS = Path(".credit-lab/mission_queue_results.jsonl")


def _validate_paths(brief: dict, repo: Path | None) -> None:
    for path in brief["affected_files"]:
        if "<" in path or ">" in path:
            raise MissionInvalid(
                "affected_files",
                f"Brief contains a placeholder path: {path!r}.",
            )
        if repo is not None and not (repo / path).exists():
            raise MissionInvalid(
                "affected_files",
                f"Affected file does not exist in the repository: {path!r}.",
            )
    if repo is None:
        return
    for token in shlex.split(brief["proposed_test"]):
        if token.startswith("-"):
            continue
        test_path = token.split("::", 1)[0]
        is_test_path = (
            test_path.endswith(".py")
            and ("test" in Path(test_path).name or "tests" in Path(test_path).parts)
        )
        if is_test_path and not (repo / test_path).exists():
            raise MissionInvalid(
                "proposed_test",
                f"Test target does not exist in the repository: {test_path!r}.",
            )


def _priority(brief: dict) -> float:
    confidence = float(brief["confidence"])
    cluster_size = max(1, int(brief.get("cluster_size", 1)))
    return round(confidence * (1.0 + math.log10(cluster_size)), 6)


async def _default_dispatcher(payload: str) -> dict:
    try:
        from src.tool_implementations import do_dispatch_mission
        return await do_dispatch_mission(payload)
    except ImportError:
        return {"exit_code": 0, "dispatch_id": "stub", "stdout": "", "stderr": ""}


async def run_queue(
    queue: Path,
    results: Path,
    *,
    execute: bool,
    dispatcher: Callable[[str], Awaitable[dict]] = _default_dispatcher,
    limit: int | None = None,
    repo: Path | None = None,
) -> dict[str, int]:
    summary = {"ready": 0, "invalid": 0, "dispatched": 0, "failed": 0}
    rows = queue.read_text(encoding="utf-8").splitlines() if queue.exists() else []
    results.parent.mkdir(parents=True, exist_ok=True)
    candidates = []

    for index, line in enumerate(rows, start=1):
        try:
            brief = json.loads(line)
            validate(brief)
            _validate_paths(brief, repo)
        except (json.JSONDecodeError, MissionInvalid) as exc:
            record = {"index": index, "status": "invalid", "error": str(exc)}
            if isinstance(exc, MissionInvalid):
                record["field"] = exc.field
            candidates.append((float("-inf"), record, None))
        else:
            candidates.append((_priority(brief), None, (index, brief)))

    valid = sorted(
        (item for item in candidates if item[2] is not None),
        key=lambda item: item[0],
        reverse=True,
    )
    invalid = [item for item in candidates if item[2] is None]
    ordered = valid + invalid
    if limit is not None:
        ordered = ordered[:limit]

    with results.open("w", encoding="utf-8") as output:
        for priority, invalid_record, valid_item in ordered:
            if invalid_record is not None:
                record = invalid_record
                summary["invalid"] += 1
            else:
                index, brief = valid_item
                if not execute:
                    record = {
                        "index": index,
                        "status": "ready",
                        "priority": priority,
                        "failure_mode": brief.get("failure_mode"),
                    }
                    summary["ready"] += 1
                else:
                    payload = json.dumps({
                        "mission": brief["mission_prompt"],
                        "repo": str(repo) if repo is not None else None,
                        "test": brief["proposed_test"],
                        "brief": brief,
                    })
                    result = await dispatcher(payload)
                    if result.get("exit_code") == 0:
                        record = {
                            "index": index,
                            "status": "dispatched",
                            **result,
                        }
                        summary["dispatched"] += 1
                    else:
                        record = {
                            "index": index,
                            "status": "failed",
                            **result,
                        }
                        summary["failed"] += 1
            output.write(json.dumps(record, sort_keys=True) + "\n")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--repo", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Launch validated missions. Without this flag, only validate.",
    )
    args = parser.parse_args()
    summary = asyncio.run(run_queue(
        args.queue,
        args.results,
        execute=args.execute,
        limit=args.limit,
        repo=args.repo,
    ))
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()