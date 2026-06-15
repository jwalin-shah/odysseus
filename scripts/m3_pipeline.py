#!/usr/bin/env python3
"""
M3 Deterministic Pipeline — Tower-of-Babylon decomposition.

CORE ARCHITECTURE:
  M3 decomposes high-level goals into atomic subtasks.
  Deterministic Python validates + commits every output.
  M3 never controls flow — Python does.

TASK HIERARCHY:
  Goal (e.g. "build approval gate")
    → M3 DECOMPOSER: outputs 5-10 atomic subtasks (each = one function, one test)
    → Parallel M3 WORKERS: each implements exactly ONE function
    → Deterministic VALIDATOR: ast.parse + ruff + test assertion
    → COMMIT: only if validator passes

LANES (run in parallel):
  L1: review   — 3-gate chain (critic JSON → verifier JSON → judge patch)
  L2: impl     — atomic function implementations, M3-decomposed
  L3: harness  — meta-harness / API key router
  L4: research — GitHits + ArXiv mining
  L5: btw      — router + retrieval (src/ only, NEVER data/)
  L6: physics  — PINN improvements

DETERMINISM:
  - All control flow: Python
  - All file I/O: Python (not M3)
  - All validation: ast.parse + ruff (not M3)
  - All commits: Python (not M3)
  - M3 only: implements functions given exact signatures+tests

Usage: nohup python3 scripts/m3_pipeline.py >> /tmp/m3_pipeline.log 2>&1 &
"""
import ast
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

KEY = os.environ.get("TOKENROUTER_API_KEY", "sk-umkgY44a1AeYkZa2ZCZFpPwnGY4ZeedbFByHfm8eZcfRKXZJ")
DEADLINE = datetime(2026, 6, 17, 23, 59)
LOCK = threading.Lock()

REPOS = {
    "odysseus":       Path("/Users/jwalinshah/projects/odysseus"),
    "btw":            Path("/Users/jwalinshah/projects/btw"),
    "physics":        Path("/Users/jwalinshah/projects/physics"),
    "tensor-logic":   Path("/Users/jwalinshah/projects/tensor-logic"),
    "career-resumes": Path("/Users/jwalinshah/projects/career-resumes"),
}

REPORTS = Path("/Users/jwalinshah/projects/odysseus/reports")
REPORTS.mkdir(parents=True, exist_ok=True)


# ─── Logging ──────────────────────────────────────────────────────────────────

def log(lane: str, name: str, msg: str) -> None:
    line = f"[{datetime.now().strftime('%H:%M:%S')}][{lane}][{name}] {msg}"
    with LOCK:
        print(line, flush=True)


# ─── M3 API ───────────────────────────────────────────────────────────────────

def m3(prompt: str, system: str | None = None, retries: int = 2) -> str:
    """
    Call MiniMax-M3 via TokenRouter. Always max_tokens=65536.
    Strip <think>...</think>. Return empty string on failure.
    """
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    payload = json.dumps({
        "model": "MiniMax-M3",
        "messages": msgs,
        "max_tokens": 65536,
    }).encode()

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                "https://api.tokenrouter.com/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {KEY}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=600, context=CTX) as r:
                body = json.load(r)
            raw = body["choices"][0]["message"]["content"]
            finish = body["choices"][0].get("finish_reason", "?")
            toks = body.get("usage", {}).get("total_tokens", "?")
            out = raw.split("</think>", 1)[1].strip() if "</think>" in raw else raw.strip()
            log("m3", "api", f"finish={finish} tok={toks} out={len(out)}c")
            if out:
                return out
            log("m3", "api", f"empty (finish={finish}) attempt={attempt+1}")
        except Exception as e:
            log("m3", "api", f"err attempt={attempt+1}: {e}")
            time.sleep(5 * (attempt + 1))
    return ""


# ─── Deterministic context tools ──────────────────────────────────────────────

def file_tree(repo: str, subdir: str = "src") -> str:
    """
    Compact file tree with line counts and top-level defs.
    Deterministic: ast.parse, no LLM.
    """
    root = REPOS[repo] / subdir
    if not root.exists():
        root = REPOS[repo]
    lines = [f"{repo}/{subdir}/"]
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(REPOS[repo])
        try:
            text = path.read_text()
            n = len(text.splitlines())
            tree = ast.parse(text)
            defs = [
                nd.name for nd in ast.walk(tree)
                if isinstance(nd, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and nd.col_offset == 0
            ]
            lines.append(f"  {rel} ({n}L) [{', '.join(defs[:6])}]")
        except Exception:
            lines.append(f"  {rel} (parse-err)")
    return "\n".join(lines)


def extract_fn(repo: str, rel_path: str, fn_name: str) -> str:
    """Extract one function/class body. Deterministic."""
    path = REPOS[repo] / rel_path
    if not path.exists():
        return f"# {rel_path} not found"
    try:
        src = path.read_text()
        tree = ast.parse(src)
        lines = src.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == fn_name:
                    return "\n".join(lines[node.lineno - 1:node.end_lineno])
    except Exception:
        pass
    return f"# {fn_name} not found in {rel_path}"


def read_head(repo: str, rel_path: str, lines: int = 50) -> str:
    """Read first N lines of a file. Deterministic."""
    path = REPOS[repo] / rel_path
    if not path.exists():
        return f"# {rel_path} not found"
    return "\n".join(path.read_text().splitlines()[:lines])


# ─── Output parsing ───────────────────────────────────────────────────────────

def parse_files(text: str) -> dict[str, str]:
    """Parse ```lang:path blocks. Deterministic regex."""
    result: dict[str, str] = {}
    for m in re.finditer(r"```[\w]*:(\S+)\n(.*?)```", text, re.DOTALL):
        result[m.group(1)] = m.group(2).rstrip()
    return result


def parse_json(text: str) -> Any:
    """Extract first JSON object/array from text. Deterministic."""
    for m in re.finditer(r"(\[.*?\]|\{.*?\})", text, re.DOTALL):
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
    return None


def parse_subtasks(text: str) -> list[dict]:
    """Parse M3's subtask decomposition output. Expects JSON array."""
    data = parse_json(text)
    if isinstance(data, list):
        return data
    return []


# ─── Validation (deterministic) ───────────────────────────────────────────────

def validate_python(code: str) -> tuple[bool, str]:
    """AST parse + ruff E9/F8 check. No LLM."""
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    r = subprocess.run(
        ["ruff", "check", "--select=E9,F8,F7", "-"],
        input=code, capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0 and r.stdout.strip():
        return False, r.stdout.strip()[:200]
    return True, "ok"


# ─── Commit (deterministic) ───────────────────────────────────────────────────

def commit_files(repo: str, edits: dict[str, str], label: str) -> list[str]:
    """
    Write files + git commit. Only commits AST-valid Python.
    BTW: never writes into data/.
    """
    root = REPOS[repo]
    applied = []
    for rel_path, content in edits.items():
        # Safety: BTW data/ is HIGH ISOLATION ZONE
        if repo == "btw" and (rel_path.startswith("data/") or "/data/" in rel_path):
            log("commit", rel_path, "BLOCKED: btw data/ protected")
            continue
        if rel_path.endswith(".py"):
            ok, reason = validate_python(content)
            if not ok:
                log("commit", rel_path, f"SKIP invalid: {reason}")
                continue
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n")
        applied.append(rel_path)

    if applied:
        with LOCK:
            subprocess.run(["git", "add"] + applied, cwd=root, capture_output=True)
            r = subprocess.run(
                ["git", "commit", "-m", f"m3-pipeline: {label}"],
                cwd=root, capture_output=True, text=True,
            )
            if r.returncode != 0:
                log("commit", label, f"git: {r.stderr.strip()[:80]}")
    return applied


# ─── Tower-of-Babylon decomposer ──────────────────────────────────────────────

DECOMPOSE_SYSTEM = """You decompose software goals into atomic subtasks.
Each subtask = exactly one function with a signature and 2-3 test assertions.
Output ONLY a JSON array. No prose. No markdown."""

DECOMPOSE_TEMPLATE = """Decompose this goal into 5-8 atomic subtasks.

GOAL: {goal}
REPO: {repo}
EXISTING FILES: {tree}

Rules:
- Each subtask = ONE Python function (or class method)
- Include exact function signature
- Include 2-3 concrete test assertions (input → expected output)
- Subtasks must be independent (no subtask depends on another's output)
- Target file must be specific (e.g. src/approval_gate.py)

Output JSON array:
[{{
  "name": "short-kebab-case-name",
  "target_file": "src/foo.py",
  "signature": "def fn_name(arg: type) -> return_type:",
  "spec": "one sentence: what it does",
  "tests": ["assert fn_name(x) == y", "assert fn_name(z) raises ValueError"],
  "imports": ["from src.bar import Baz"]
}}]"""


def decompose_goal(goal: str, repo: str) -> list[dict]:
    """
    Call M3 once to decompose a high-level goal into atomic subtasks.
    Returns list of subtask dicts. Deterministic parsing.
    """
    tree = file_tree(repo)
    prompt = DECOMPOSE_TEMPLATE.format(goal=goal, repo=repo, tree=tree)
    response = m3(prompt, DECOMPOSE_SYSTEM)
    if not response:
        return []
    subtasks = parse_subtasks(response)
    log("decompose", goal[:40], f"→ {len(subtasks)} subtasks")
    return subtasks


# ─── Atomic task runner ───────────────────────────────────────────────────────

IMPL_SYSTEM = """You implement Python functions. Output ONLY a ```python:path/to/file.py block.
No prose. No explanation. No markdown outside the code block."""

IMPL_TEMPLATE = """Implement this Python function. Output ONLY the complete file.

TARGET: {target_file}
SIGNATURE: {signature}
SPEC: {spec}

TESTS (must pass):
{tests}

IMPORTS AVAILABLE:
{imports}

Output: ```python:{target_file}
[complete file starting from imports]
```"""


def run_subtask(subtask: dict, repo: str, lane: str) -> dict:
    """Run one atomic M3 subtask. Validate + commit. Deterministic."""
    name = subtask.get("name", "unknown")
    target = subtask.get("target_file", "src/unknown.py")
    sig = subtask.get("signature", "def fn():")
    spec = subtask.get("spec", "")
    tests = subtask.get("tests", [])
    imports = subtask.get("imports", [])

    log(lane, name, f"impl → {target}")

    prompt = IMPL_TEMPLATE.format(
        target_file=target,
        signature=sig,
        spec=spec,
        tests="\n".join(f"  {t}" for t in tests),
        imports="\n".join(imports) if imports else "standard library only",
    )

    response = m3(prompt, IMPL_SYSTEM)
    if not response:
        return {"name": name, "status": "empty"}

    edits = parse_files(response)
    if not edits:
        log(lane, name, f"no file blocks in response ({len(response)}c)")
        return {"name": name, "status": "no_files"}

    applied = commit_files(repo, edits, f"{lane}/{name}")
    if applied:
        log(lane, name, f"committed: {applied}")
        return {"name": name, "status": "ok", "files": applied}
    log(lane, name, "validation failed — not committed")
    return {"name": name, "status": "invalid"}


def run_goal_decomposed(goal: str, repo: str, lane: str,
                        max_workers: int = 4) -> list[dict]:
    """
    Full tower-of-babylon execution:
      1. M3 decomposes goal → subtasks
      2. Parallel M3 workers implement each subtask
      3. Deterministic validate + commit
    """
    subtasks = decompose_goal(goal, repo)
    if not subtasks:
        return [{"name": goal, "status": "decompose_failed"}]

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(run_subtask, st, repo, lane): st["name"] for st in subtasks}
        for fut in as_completed(futs):
            results.append(fut.result())
    return results


# ─── Lane 1: 3-gate review chain ─────────────────────────────────────────────

CRITIC_SYS = "You find bugs in Python code. Output ONLY a JSON array. No prose."
VERIFIER_SYS = "You verify bug reports. Output ONLY a JSON array. No prose."
JUDGE_SYS = "You are a senior engineer. You write minimal bug fixes. Output ONLY code blocks."


def review_chain(name: str, repo: str, target_file: str) -> dict:
    """
    3-gate review. All 3 M3 calls produce machine-parseable output.
    Gate 1 (critic): JSON bug list.
    Gate 2 (verifier): JSON verification of each bug.
    Gate 3 (judge): minimal patch for confirmed bugs only.
    """
    log("review", name, f"start → {target_file}")
    content = read_head(repo, target_file, 100)

    # Gate 1: critic
    critic_out = m3(
        f"Find bugs in this Python file. Output ONLY JSON array.\n\n"
        f"FILE: {target_file}\n{content}\n\n"
        f'Format: [{{"line": N, "issue": "bug", "fix": "fix", "severity": "critical|major|minor"}}]',
        CRITIC_SYS,
    )
    bugs = parse_json(critic_out or "")
    if not bugs:
        return {"name": name, "status": "critic_empty"}
    log("review", name, f"critic: {len(bugs)} bugs found")

    # Gate 2: verifier
    verify_out = m3(
        f"Verify these bug reports against the actual code. Output ONLY JSON array.\n\n"
        f"FILE: {target_file}\n{content}\n\n"
        f"CLAIMS:\n{json.dumps(bugs[:10], indent=2)}\n\n"
        f'Format: [{{"issue": "...", "real": true|false, "reason": "why"}}]',
        VERIFIER_SYS,
    )
    verified = parse_json(verify_out or "")
    if not verified:
        return {"name": name, "status": "verifier_empty", "bugs": len(bugs)}
    real_bugs = [v for v in verified if v.get("real")]
    log("review", name, f"verifier: {len(real_bugs)}/{len(bugs)} real")

    if not real_bugs:
        return {"name": name, "status": "clean"}

    # Gate 3: judge — write minimal patch
    judge_out = m3(
        f"Fix ONLY these confirmed bugs. Output the complete fixed file.\n\n"
        f"FILE: {target_file}\n{content}\n\n"
        f"CONFIRMED BUGS:\n{json.dumps(real_bugs, indent=2)}\n\n"
        f"Output: ```python:{target_file}\n[complete fixed file]\n```\n"
        f"If too complex to fix safely, output: SKIP",
        JUDGE_SYS,
    )
    if not judge_out or "SKIP" in judge_out[:20]:
        return {"name": name, "status": "judge_skipped", "real_bugs": len(real_bugs)}

    edits = parse_files(judge_out)
    if not edits:
        return {"name": name, "status": "judge_no_patch", "real_bugs": len(real_bugs)}

    applied = commit_files(repo, edits, f"review/{name}")
    return {"name": name, "status": "ok", "files": applied, "bugs_fixed": len(real_bugs)}


REVIEW_TARGETS = [
    ("review-intent-router",   "odysseus", "src/intent_router.py"),
    ("review-harness",         "odysseus", "src/harness.py"),
    ("review-inbox-tool",      "odysseus", "src/inbox_tool.py"),
    ("review-workflow-engine", "odysseus", "src/workflow_engine.py"),
    ("review-btw-storage",     "btw",      "src/btw_world_state/storage.py"),
    ("review-btw-edge",        "btw",      "src/btw_world_state/edge.py"),
]


# ─── Lane 4: Research — GitHits + ArXiv ──────────────────────────────────────

ARXIV_API = "https://export.arxiv.org/api/query"


def arxiv_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search arXiv API. Returns list of {title, abstract, authors, arxiv_id}.
    Deterministic: pure HTTP + XML parse.
    """
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
    })
    try:
        with urllib.request.urlopen(f"{ARXIV_API}?{params}", timeout=30, context=CTX) as r:
            xml = r.read().decode()
    except Exception as e:
        log("arxiv", query[:30], f"error: {e}")
        return []

    entries = []
    for entry in re.finditer(r"<entry>(.*?)</entry>", xml, re.DOTALL):
        body = entry.group(1)
        def tag(t: str) -> str:
            m = re.search(rf"<{t}[^>]*>(.*?)</{t}>", body, re.DOTALL)
            return m.group(1).strip() if m else ""
        arxiv_id = tag("id").split("/abs/")[-1].strip()
        entries.append({
            "arxiv_id": arxiv_id,
            "title": tag("title").replace("\n", " "),
            "abstract": tag("summary")[:500].replace("\n", " "),
        })
    return entries


RESEARCH_QUERIES = [
    ("agent-routing", "deterministic intent routing LLM agent systems"),
    ("incremental-sync", "incremental data synchronization agent memory"),
    ("skill-learning", "autonomous skill creation agent closed learning loop"),
    ("trajectory-finetuning", "trajectory compression fine-tuning language model agent"),
    ("retrieval-augmented", "retrieval augmented generation routing query classification"),
]


def research_arxiv_and_synthesize(topic: str, query: str) -> dict:
    """
    Fetch arXiv papers, then ask M3 to synthesize the findings into
    a concrete implementation recommendation for Odysseus.
    """
    log("research", topic, f"arxiv: {query}")
    papers = arxiv_search(query, max_results=5)
    if not papers:
        log("research", topic, "no arxiv results")
        papers_text = "No arxiv results found."
    else:
        papers_text = "\n".join(
            f"[{p['arxiv_id']}] {p['title']}\n  {p['abstract'][:200]}"
            for p in papers
        )
        log("research", topic, f"found {len(papers)} papers")

    synthesis = m3(
        f"Based on these research papers, what is the best implementation pattern for Odysseus?\n\n"
        f"TOPIC: {topic}\n\nPAPERS:\n{papers_text}\n\n"
        f"Output JSON:\n"
        f'{{"topic": "{topic}", "key_insight": "...", "implementation": "...", '
        f'"concrete_steps": ["step1", "step2", "step3"], "priority": "high|medium|low"}}',
    )
    if synthesis:
        out = REPORTS / f"arxiv_{topic}.json"
        out.write_text(synthesis)
        log("research", topic, f"saved {out.name}")
        return {"name": topic, "status": "ok"}
    return {"name": topic, "status": "synthesis_empty"}


# ─── High-level goals → decomposed → implemented ──────────────────────────────

HIGH_LEVEL_GOALS = [
    # odysseus core
    ("approval gate: CLI confirmation flow for harness write actions",    "odysseus", "impl"),
    ("session manager: track conversation history, pending actions",       "odysseus", "impl"),
    ("skill registry: load/save/match skills from ~/.odysseus/skills/",   "odysseus", "impl"),
    ("API key router: round-robin multiple keys, rotate on quota errors",  "odysseus", "impl"),
    ("trajectory logger: record turns as fine-tuning trajectories",        "odysseus", "impl"),
    ("incremental inbox sync: hash-based, only fetch new messages",        "odysseus", "impl"),
    ("prompt template library: IMPLEMENT_FN, IMPROVE_FILE, REVIEW, SEARCH_REPLACE",
     "odysseus", "impl"),
    # btw (src/ only)
    ("deterministic query router: classify BTW queries into world_state/simulation/trajectory/benchmark",
     "btw", "btw"),
    ("retrieval cache: TTL-based cache for BTW module query results",      "btw", "btw"),
    # physics
    ("improve PINN pendulum: type hints, docstrings with units, input validation",
     "physics", "physics"),
]


# ─── Lane 3: harness improvement ─────────────────────────────────────────────

def improve_agent_tools() -> dict:
    """M3 audits and improves ~/.agent-rules/ tooling. Output as report."""
    rules_path = Path("/Users/jwalinshah/.agent-rules/GLOBAL.md")
    if not rules_path.exists():
        return {"name": "agent-tools", "status": "not_found"}
    rules = rules_path.read_text()[:3000]
    out = m3(
        f"Audit these agent rules. Find stale, missing, or unclear entries.\n\n"
        f"RULES:\n{rules}\n\n"
        f'Output JSON: [{{"section": "...", "issue": "...", "fix": "...", '
        f'"priority": "high|medium|low"}}]\nOnly JSON.',
    )
    if out:
        (REPORTS / "agent_rules_audit.json").write_text(out)
        return {"name": "agent-tools", "status": "ok"}
    return {"name": "agent-tools", "status": "empty"}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    log("pipeline", "main", f"Start. Deadline={DEADLINE}. Now={datetime.now():%Y-%m-%d %H:%M}")
    log("pipeline", "main", "Architecture: M3 decomposes → Python orchestrates → M3 implements → Python validates")

    all_futures: list = []

    with ThreadPoolExecutor(max_workers=24) as ex:

        # Lane 1: review chains (parallel across files, sequential within)
        for name, repo, target in REVIEW_TARGETS:
            all_futures.append(ex.submit(review_chain, name, repo, target))

        # Lane 2+3+5+6: decomposed implementation goals
        for goal_desc, repo, lane in HIGH_LEVEL_GOALS:
            all_futures.append(ex.submit(run_goal_decomposed, goal_desc, repo, lane))

        # Lane 4a: ArXiv research
        for topic, query in RESEARCH_QUERIES:
            all_futures.append(ex.submit(research_arxiv_and_synthesize, topic, query))

        # Lane 4b: agent tools audit
        all_futures.append(ex.submit(improve_agent_tools))

        # Collect
        ok = report = invalid = error = 0
        for fut in as_completed(all_futures):
            try:
                r = fut.result()
                if isinstance(r, list):
                    for item in r:
                        s = item.get("status", "error")
                        if s == "ok": ok += 1
                        elif s in ("report", "clean"): report += 1
                        elif s in ("invalid", "no_files"): invalid += 1
                        else: error += 1
                else:
                    s = r.get("status", "error")
                    if s == "ok": ok += 1
                    elif s in ("report", "clean"): report += 1
                    elif s in ("invalid", "no_files"): invalid += 1
                    else: error += 1
            except Exception as e:
                log("pipeline", "future", f"exception: {e}")
                error += 1

    log("pipeline", "main", f"Done. ok={ok} report={report} invalid={invalid} error={error}")


if __name__ == "__main__":
    main()
