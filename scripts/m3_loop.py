#!/usr/bin/env python3
"""
M3 improvement loop — runs MiniMax-M3 continuously to improve the harness.
Usage: python3 scripts/m3_loop.py [--max-rounds N] [--target src/foo.py]
Run as: nohup python3 scripts/m3_loop.py >> /tmp/m3_loop.log 2>&1 &
"""
import argparse
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()

TOKENROUTER_KEY = os.environ.get(
    "TOKENROUTER_API_KEY",
    "sk-umkgY44a1AeYkZa2ZCZFpPwnGY4ZeedbFByHfm8eZcfRKXZJ",
)
REPO_ROOT = Path(__file__).parent.parent

HARNESS_FILES = [
    "src/intent_router.py",
    "src/pi_call.py",
    "src/inbox_tool.py",
    "src/m3_editor.py",
    "src/fusion.py",
    "src/agent_tools.py",
    "src/tool_schemas.py",
    "src/tool_implementations.py",
    "src/odysseus.py",
]

SYSTEM = (
    "You are an expert Python engineer improving the Odysseus personal AI harness. "
    "When you want to edit a file, output a fenced code block with the language tag "
    "and filename on the fence line, like:\n"
    "```python:src/foo.py\n"
    "...complete file content...\n"
    "```\n"
    "Only output files you actually changed. If nothing needs changing, say so."
)


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def m3(prompt: str, system: str = SYSTEM, max_tokens: int = 8000) -> str:
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    req = urllib.request.Request(
        "https://api.tokenrouter.com/v1/chat/completions",
        data=json.dumps({"model": "MiniMax-M3", "messages": msgs, "max_tokens": max_tokens}).encode(),
        headers={"Authorization": f"Bearer {TOKENROUTER_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=240, context=SSL_CTX) as r:
        body = json.load(r)
    out = body["choices"][0]["message"]["content"]
    if "</think>" in out:
        out = out.split("</think>", 1)[1].strip()
    return out


def read_file(rel_path: str) -> str:
    path = REPO_ROOT / rel_path
    if path.exists():
        return path.read_text()
    return ""


def parse_edits(text: str) -> dict[str, str]:
    """Parse ```python:src/foo.py ... ``` blocks."""
    result: dict[str, str] = {}
    for m in re.finditer(r"```\w*:(\S+)\n(.*?)```", text, re.DOTALL):
        result[m.group(1)] = m.group(2).strip()
    return result


def apply_edits(edits: dict[str, str]) -> list[str]:
    applied = []
    for rel_path, content in edits.items():
        path = REPO_ROOT / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n")
        applied.append(rel_path)
        log(f"  wrote {rel_path} ({len(content)} chars)")
    return applied


def run_tests() -> tuple[bool, str]:
    result = subprocess.run(
        ["python3", "-m", "pytest", "tests/", "-x", "-q", "--tb=short", "--no-header"],
        capture_output=True, text=True, timeout=60, cwd=REPO_ROOT
    )
    output = (result.stdout + result.stderr).strip()
    passed = result.returncode == 0
    return passed, output


def build_context(target_files: list[str] | None = None) -> str:
    files = target_files or HARNESS_FILES
    parts = []
    for f in files:
        content = read_file(f)
        if content:
            parts.append(f"=== {f} ===\n{content}")
    return "\n\n".join(parts)


def improvement_round(round_num: int, goal: str, target_files: list[str] | None, test_output: str) -> tuple[dict[str, str], str]:
    context = build_context(target_files)
    prompt_parts = [
        f"ROUND {round_num} — IMPROVEMENT GOAL:\n{goal}",
        f"\nCURRENT FILES:\n{context}",
    ]
    if test_output:
        prompt_parts.append(f"\nLAST TEST OUTPUT:\n{test_output}")
    prompt_parts.append(
        "\nAnalyze the code and produce improved versions of any files that need changes. "
        "Focus on the goal above. If tests were failing, fix them. "
        "Output only changed files using the ```python:path/to/file.py format."
    )
    prompt = "\n".join(prompt_parts)
    log(f"Calling M3 (prompt {len(prompt)} chars)...")
    response = m3(prompt)
    log(f"M3 response: {len(response)} chars")
    edits = parse_edits(response)
    return edits, response


def run_loop(goal: str, max_rounds: int, target_files: list[str] | None) -> None:
    log(f"Starting M3 improvement loop — goal: {goal}")
    log(f"Max rounds: {max_rounds}, targets: {target_files or 'all harness files'}")

    test_output = ""
    for round_num in range(1, max_rounds + 1):
        log(f"--- Round {round_num}/{max_rounds} ---")

        edits, response = improvement_round(round_num, goal, target_files, test_output)

        if not edits:
            log("M3 made no edits this round — harness is good or goal is complete")
            log(f"M3 said: {response[:300]}")
            break

        log(f"Applying {len(edits)} file(s)...")
        applied = apply_edits(edits)

        # Run tests
        log("Running tests...")
        try:
            passed, test_output = run_tests()
            status = "PASSED" if passed else "FAILED"
            log(f"Tests {status}: {test_output[:200]}")
        except subprocess.TimeoutExpired:
            passed = False
            test_output = "Tests timed out after 60s"
            log(test_output)

        if passed:
            log(f"Round {round_num} complete — tests green. Committing...")
            subprocess.run(
                ["git", "add"] + applied,
                cwd=REPO_ROOT, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", f"m3-loop round {round_num}: {goal[:60]}"],
                cwd=REPO_ROOT, capture_output=True
            )
            break

        time.sleep(5)  # Brief pause before next round

    log("Loop complete.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", default="Improve intent classification accuracy and add missing inbox routes")
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--target", action="append", dest="targets", help="Specific files to improve")
    args = parser.parse_args()
    run_loop(args.goal, args.max_rounds, args.targets)


if __name__ == "__main__":
    main()
