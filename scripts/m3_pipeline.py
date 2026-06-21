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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m3_client import call_m3, KEY  # unified call harness → reports/m3_calls.jsonl

# FULL SEND: lift the file-descriptor soft limit to the hard max so high
# concurrency (hundreds of in-flight calls + subprocess per commit) doesn't hit
# "Too many open files". The machine, not a TPM ceiling, is the real wall here.
try:
    import resource
    _soft, _hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (_hard, _hard))
except Exception:
    pass

PIPELINE_WORKERS = 256   # outer pool (24→128→256; peak burst held 94 RPM @ 100% ok, headroom)
SUBTASK_WORKERS = 12     # nested pool per goal (4→8→12)

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

DEADLINE = datetime(2026, 6, 17, 23, 59)
LOCK = threading.Lock()

# Retargeted to REAL, active, load-bearing repos (audit found physics/tensor-logic/
# career-resumes were near-dead vanity targets eating ~half the compute). The repo
# guard in main() auto-skips any stale HIGH_LEVEL_GOALS pointing at dropped repos.
REPOS = {
    "odysseus":         Path("/Users/jwalinshah/projects/odysseus"),
    "btw":              Path("/Users/jwalinshah/projects/btw"),
    "inbox":            Path("/Users/jwalinshah/projects/inbox"),
    "orchestrator-mvp": Path("/Users/jwalinshah/projects/orchestrator-mvp"),
    "pcr-core":         Path("/Users/jwalinshah/projects/pcr-core"),
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
    """Call MiniMax-M3 via the shared harness (scripts/m3_client).

    Every call is logged centrally to reports/m3_calls.jsonl; we keep one local
    line too so the existing /tmp/m3_pipeline.log monitoring still works.
    """
    out = call_m3(prompt, system, retries=retries, worker="pipeline")
    log("m3", "api", f"out={len(out)}c ok={bool(out)}")
    return out


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
    """Extract first JSON object/array from text. Handles nested brackets + ``` fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = next((i for i, c in enumerate(text) if c in "[{"), -1)
    if start < 0:
        return None
    open_c = text[start]
    close_c = "]" if open_c == "[" else "}"
    depth = in_str = esc = 0
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = 0
            elif c == "\\":
                esc = 1
            elif c == '"':
                in_str = 0
            continue
        if c == '"':
            in_str = 1
        elif c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
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
    try:
        r = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--select=E9,F8,F7", "-"],
            input=code, capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return True, "ok (ruff unavailable, ast-only)"
    if r.returncode != 0 and r.stdout.strip():
        return False, r.stdout.strip()[:200]
    return True, "ok"


def run_tests(repo: str, target_file: str, tests: list) -> tuple[bool, str]:
    """Execute a subtask's assertion list against the just-written target file.

    Imports the target module and runs each assertion in a subprocess. This is
    the gate that makes "committed" mean "works", not just "AST-valid".
    Returns (passed, detail). No tests / non-py target → pass (nothing to check).
    """
    asserts = [t for t in (tests or []) if isinstance(t, str) and t.strip()]
    if not asserts or not target_file.endswith(".py"):
        return True, "no tests"
    # ODYSSEUS-PIPELINE-RCE: refuse any test string that contains a newline
    # or a top-level `import` / `from` / `@` / `exec(` / `eval(` / `__import__`
    # token. The downstream concatenation feeds these strings into a
    # `-c` python invocation; an M3 hallucination of e.g.
    # `assert __import__('os').system('rm -rf /')` would otherwise run
    # unchanged. Whitelist assertion-form only: a leading `assert` and
    # otherwise only Python expressions, no statements.
    for a in asserts:
        stripped = a.strip()
        if "\n" in stripped or "\r" in stripped:
            return False, f"rejected multi-line test: {stripped[:60]!r}"
        if not stripped.startswith("assert "):
            return False, f"rejected non-assertion test: {stripped[:60]!r}"
        body = stripped[len("assert "):]
        try:
            tree = ast.parse(body, mode="eval")
        except SyntaxError as e:
            return False, f"rejected unparseable assertion: {e}"
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom,
                                 ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef, ast.Lambda)):
                return False, f"rejected disallowed syntax in test: {type(node).__name__}"
            if isinstance(node, ast.Call):
                func = node.func
                name = None
                root_name = None
                if isinstance(func, ast.Name):
                    name = func.id
                    root_name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                    # Walk to the leftmost name: subprocess.run -> "subprocess"
                    cur = func
                    while isinstance(cur, ast.Attribute):
                        cur = cur.value
                    if isinstance(cur, ast.Name):
                        root_name = cur.id
                # Block both the leaf call name AND its root module/attr
                if name in ("exec", "eval", "__import__", "compile", "open",
                            "system", "popen"):
                    return False, f"rejected dangerous call: {name}"
                if root_name in ("subprocess", "popen2", "commands", "os",
                                 "shutil", "pathlib"):
                    return False, f"rejected dangerous module call: {root_name}"
    root = REPOS[repo]
    tgt = root / target_file
    # Load the just-written file directly (no package-path guessing) and expose
    # ALL its names — including underscore-prefixed helpers that `import *` skips.
    # Put repo root + its parent on sys.path so M3's own imports resolve either way,
    # and provide pytest if installed so pytest-style assertions can run.
    script = (
        "import sys, importlib.util\n"
        f"sys.path.insert(0, {str(root)!r})\n"
        f"sys.path.insert(0, {str(root.parent)!r})\n"
        "try:\n    import pytest\nexcept Exception:\n    pytest = None\n"
        f"_spec = importlib.util.spec_from_file_location('_tgt', {str(tgt)!r})\n"
        "_m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)\n"
        "globals().update({k: v for k, v in vars(_m).items() if not k.startswith('__')})\n"
        + "\n".join(asserts)
    )
    try:
        r = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(root), capture_output=True, text=True, timeout=30,
        )
    except subprocess.SubprocessError:
        return False, "test execution timed out"
    if r.returncode == 0:
        return True, "ok"
    err = (r.stderr.strip().splitlines() or ["?"])[-1]
    return False, err[:160]


# ─── Learning loop (M3-driven observe → adapt) ───────────────────────────────

LEARNED_RULES_FILE = REPORTS / "learned_rules.md"


def load_learned_rules() -> str:
    """Rules M3 wrote for itself from past failures; injected into gen prompts."""
    try:
        return LEARNED_RULES_FILE.read_text().split("\n\n", 1)[-1].strip()
    except FileNotFoundError:
        return ""


def update_learned_rules() -> None:
    """Close the loop: read recent test-failure modes, let M3 synthesize rules to
    prevent them, persist them. Those rules feed back into decompose/impl prompts
    so the system stops repeating its own mistakes — this is the 'actually
    learning' step, and M3 itself does the analysis."""
    try:
        lines = Path("/tmp/m3_pipeline.log").read_text().splitlines()
    except FileNotFoundError:
        return
    fails = [ln.split("TESTS FAILED:", 1)[1].split("— reverting")[0].strip()
             for ln in lines if "TESTS FAILED:" in ln][-80:]
    if len(fails) < 5:
        return
    from collections import Counter
    modes = Counter(f.split(":")[0].strip()[:60] for f in fails).most_common(8)
    summary = "\n".join(f"{n}x  {mode}" for mode, n in modes)
    out = m3(
        "These are the most common failure modes when generating Python functions "
        "with inline assert tests. Write 5-7 short imperative rules that would "
        "prevent them (e.g. test format, imports, naming). Output ONLY the rules, "
        "one per line, no numbering.\n\n"
        f"FAILURE MODES (count x mode):\n{summary}",
        "You improve a code-generation prompt. Output only terse imperative rules.",
    )
    if out and len(out.strip()) > 20:
        LEARNED_RULES_FILE.write_text(
            f"# Auto-learned rules — updated {datetime.now():%Y-%m-%d %H:%M} "
            f"from {len(fails)} recent test failures\n\n" + out.strip() + "\n")
        log("pipeline", "learn", f"updated learned_rules from {len(fails)} failures "
            f"(top: {modes[0][0] if modes else '?'})")


# ─── Commit (deterministic) ───────────────────────────────────────────────────

def commit_files(repo: str, edits: dict[str, str], label: str,
                 tests: list | None = None, target: str | None = None) -> list[str]:
    """
    Write files + git commit. Only commits AST-valid Python.
    If `tests` are supplied, they must PASS against `target` or the write is
    reverted and nothing is committed (the tests-must-pass gate).
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

    # Tests-must-pass gate: revert the write if the assertions don't pass.
    if applied and tests and target:
        passed, detail = run_tests(repo, target, tests)
        if not passed:
            log("commit", label, f"TESTS FAILED: {detail} — reverting")
            for rel in applied:
                cr = subprocess.run(["git", "checkout", "HEAD", "--", rel],
                                    cwd=root, capture_output=True)
                if cr.returncode != 0:  # untracked (new) file — remove it
                    (root / rel).unlink(missing_ok=True)
            return []
        log("commit", label, "tests passed")

    if applied:
        with LOCK:
            subprocess.run(["git", "add"] + applied, cwd=root, capture_output=True)
            r = subprocess.run(
                ["git", "commit", "-m", f"m3-pipeline: {label}"],
                cwd=root, capture_output=True, text=True,
            )
            if r.returncode != 0:
                log("commit", label, f"git FAILED: {r.stderr.strip()[:100]}")
                return []
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
- PREFER EXTENDING AN EXISTING FILE from EXISTING FILES above over creating a new
  one. Only create a new file if no existing module fits. Do NOT create parallel
  "shadow" modules that duplicate something already in the repo.
- target_file MUST be a real path that fits the repo's actual layout (match where
  similar code already lives), not a guessed src/ path.

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
    rules = load_learned_rules()
    sys_prompt = DECOMPOSE_SYSTEM + (f"\n\nLEARNED RULES (avoid past mistakes):\n{rules}" if rules else "")
    response = m3(prompt, sys_prompt)
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

EXISTING CODE CONTEXT (match style, reuse what's here, don't break it):
{context}

Output: ```python:{target_file}
[complete file starting from imports]
```"""


def gather_context(repo: str, target: str, query: str = "", budget: int = 150_000) -> str:
    """Give the model the structure it needs, the Aider-Engine way.

    1. agent-repomap: a goal-conditioned, compressed AST map of the whole repo —
       high signal per token (context deflation) so the model sees real APIs to
       reuse instead of hallucinating them.
    2. The full current target file for exact local grounding.
    Falls back to a raw same-dir dump if agent-repomap is unavailable.
    """
    root = REPOS[repo]
    parts = []
    try:
        r = subprocess.run(
            ["agent-repomap", str(root), query or target],
            capture_output=True, text=True, timeout=90,
        )
        if r.returncode == 0 and r.stdout.strip():
            parts.append("=== REPO MAP (agent-repomap, goal-conditioned) ===\n" + r.stdout.strip())
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    tgt = root / target
    if tgt.exists():
        parts.append(f"=== CURRENT {target} (you are editing THIS file) ===\n{tgt.read_text()}")
    elif not parts:  # no map and new file → fall back to sibling dump for some grounding
        d = tgt.parent
        if d.exists():
            for p in sorted(d.glob("*.py"))[:8]:
                try:
                    parts.append(f"=== {p.relative_to(root)} ===\n{p.read_text()}")
                except Exception:
                    pass

    blob = "\n\n".join(parts)
    return blob[:budget] if blob else "(new module — no existing structure in this repo dir)"


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
        context=gather_context(repo, target, query=f"{name} {spec}"),
    )

    rules = load_learned_rules()
    sys_prompt = IMPL_SYSTEM + (f"\n\nLEARNED RULES (avoid past mistakes):\n{rules}" if rules else "")
    response = m3(prompt, sys_prompt)
    if not response:
        return {"name": name, "status": "empty"}

    edits = parse_files(response)
    if not edits:
        log(lane, name, f"no file blocks in response ({len(response)}c)")
        return {"name": name, "status": "no_files"}

    applied = commit_files(repo, edits, f"{lane}/{name}", tests=tests, target=target)
    if applied:
        log(lane, name, f"committed (tests passed): {applied}")
        return {"name": name, "status": "ok", "files": applied}

    # REPAIR: one retry — feed the failed attempt back and demand the tests pass.
    log(lane, name, "first attempt failed gate — repairing")
    repair_prompt = (
        prompt
        + "\n\nYOUR PREVIOUS ATTEMPT FAILED ITS TESTS. Here it was:\n"
        + (response[:4000] if response else "")
        + "\n\nProduce a CORRECTED complete file that passes ALL the tests above. "
          "Define every name, use only stdlib + existing repo modules, plain `assert`-compatible behavior."
    )
    response2 = m3(repair_prompt, sys_prompt)
    edits2 = parse_files(response2 or "")
    if edits2:
        applied = commit_files(repo, edits2, f"{lane}/{name}-fix", tests=tests, target=target)
        if applied:
            log(lane, name, f"committed after repair: {applied}")
            return {"name": name, "status": "ok", "files": applied, "repaired": True}
    log(lane, name, "not committed (failed gate after repair)")
    return {"name": name, "status": "invalid"}


def run_goal_decomposed(goal: str, repo: str, lane: str,
                        max_workers: int = SUBTASK_WORKERS) -> list[dict]:
    """
    Full tower-of-babylon execution:
      1. M3 decomposes goal → subtasks
      2. Parallel M3 workers implement each subtask
      3. Deterministic validate + commit
    """
    subtasks = [st for st in decompose_goal(goal, repo) if isinstance(st, dict)]
    if not subtasks:
        return [{"name": goal, "status": "decompose_failed"}]

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(run_subtask, st, repo, lane): st.get("name", "subtask") for st in subtasks}
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
    if not isinstance(bugs, list) or not bugs:
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
    if not isinstance(verified, list) or not verified:
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
    # ── new goals (added 2026-06-15 by /loop health check) ──
    ("rate limiter: token_bucket(rpm) throttle for outbound API calls, blocks until a token is available; test enforces RPM ceiling",
     "odysseus", "impl"),
    ("cost estimator: estimate_cost(trajectory_log) sums per-model token usage to a USD figure; test asserts known log totals correct",
     "odysseus", "impl"),
    ("retry decorator: with_backoff(fn, retries, base) does exponential backoff on transient API errors; test counts attempts + delays grow",
     "odysseus", "impl"),
    ("BTW benchmark scorer: score_results(preds, gold) returns dict with accuracy + p50/p95 latency; test on fixture preds/gold",
     "btw", "btw"),
    ("PINN energy check: energy_drift(trajectory) returns max total-energy drift; test asserts drift below tolerance for a damped run",
     "physics", "physics"),
    # ── new goals (added 2026-06-15 03:35 by /loop tick 2) ──
    ("structured logger: log_event(level, event, **fields) emits one JSON line per call; test asserts output parses + has required keys",
     "odysseus", "impl"),
    ("config loader: load_config(path) merges defaults < file < env overrides; test asserts env beats file beats default",
     "odysseus", "impl"),
    ("circuit breaker: CircuitBreaker(fail_threshold, cooldown) opens after N fails, half-opens after cooldown; test drives state transitions",
     "odysseus", "impl"),
    ("BTW query-result diff: diff_results(a, b) returns added/removed/changed keys; test on two fixture result dicts",
     "btw", "btw"),
    ("PINN residual metric: pde_residual(model, points) returns mean abs residual; test asserts below tolerance on a trained model",
     "physics", "physics"),
    # ── new goals (added 2026-06-15 04:24 by /loop tick 3) ──
    ("LRU memo cache: memoize(maxsize) decorator evicts oldest entry past maxsize; test asserts eviction order + hit/miss counts",
     "odysseus", "impl"),
    ("token counter: count_tokens(text) returns an estimate; test asserts within +/-10% of reference counts on fixtures",
     "odysseus", "impl"),
    ("dedup queue: DedupQueue.push(item, key) ignores duplicate keys and preserves FIFO; test asserts no repeats + order",
     "odysseus", "impl"),
    ("BTW world-state snapshot: snapshot(state) then restore(blob) round-trips; test asserts restored == original",
     "btw", "btw"),
    ("PINN boundary loss: boundary_loss(model, bc_points) returns mean boundary-condition violation; test asserts below tolerance on a trained model",
     "physics", "physics"),
    # ── new goals (added 2026-06-15 05:13 by /loop tick 4) ──
    ("sliding-window rate stats: WindowStats.add(ts)/rate() returns events-per-sec over a window; test asserts decay as events age out",
     "odysseus", "impl"),
    ("JSON-lines reader: read_jsonl(path) yields parsed records, skips blank/corrupt lines; test asserts good records parsed + bad skipped",
     "odysseus", "impl"),
    ("env interpolation: expand_vars(template, env) replaces ${VAR} with env values, leaves unknown intact; test asserts both cases",
     "odysseus", "impl"),
    ("BTW edge weight normalize: normalize_weights(edges) scales weights to sum=1.0 per node; test asserts per-node sums == 1.0",
     "btw", "btw"),
    ("PINN collocation sampler: sample_collocation(domain, n, seed) returns n reproducible interior points; test asserts shape + determinism by seed",
     "physics", "physics"),
    # ── new goals (added 2026-06-15 06:02 by /loop tick 5) ──
    ("deep merge: deep_merge(a, b) recursively merges nested dicts with b winning conflicts; test asserts nested override + non-dict replace",
     "odysseus", "impl"),
    ("timestamp parser: parse_ts(s) accepts ISO8601 or unix epoch and returns a UTC datetime; test asserts both formats map to same instant",
     "odysseus", "impl"),
    ("secret redactor: redact(text, patterns) masks API keys/tokens in text; test asserts known secret formats masked, normal text untouched",
     "odysseus", "impl"),
    ("BTW shortest path: shortest_path(graph, src, dst) returns node list via BFS or None if unreachable; test asserts shortest path + None case",
     "btw", "btw"),
    ("PINN data loss: data_loss(model, obs_points, obs_vals) returns MSE against observations; test asserts ~0 on an exact-fit fixture",
     "physics", "physics"),
    # ── new goals (added 2026-06-15 06:50 by /loop tick 6) ──
    ("DiffCoT retry: diffcot_retry(gen_fn, validate_fn, n, temps) returns first candidate passing validate (or best merge); test asserts recovery when first attempt fails",
     "odysseus", "impl"),
    ("adaptive gate prompts: build_gate_prompts(task_desc) returns dict with critic/verifier/judge keys and task embedded; test asserts 3 keys + task substring",
     "odysseus", "impl"),
    ("edit distance: levenshtein(a, b) returns int edit distance; test asserts kitten/sitting==3 and empty/empty==0",
     "odysseus", "impl"),
    ("BTW stable cache key: cache_key(query, params) returns an order-independent hash; test asserts same key for reordered params dict",
     "btw", "btw"),
    ("PINN gradient norm: grad_norm(model, points) returns mean output-gradient norm; test asserts finite + matches analytic slope on a linear fixture",
     "physics", "physics"),
    # ── new goals (added 2026-06-15 07:37 by /loop tick 7) ──
    ("ULID generator: new_ulid() returns a 26-char Crockford-base32 sortable id; test asserts length, charset, and monotonic ordering over time",
     "odysseus", "impl"),
    ("diff summarizer: summarize_diff(old, new) returns added/removed line counts; test asserts counts on a fixture pair",
     "odysseus", "impl"),
    ("chunk iterator: chunked(seq, n) yields lists of size n with a possibly-short last chunk; test asserts sizes + full coverage",
     "odysseus", "impl"),
    ("BTW node degree: degree_map(edges) returns {node: degree}; test asserts degrees on a fixture graph",
     "btw", "btw"),
    ("PINN rollout error: rollout_error(model, t0, steps, dt) returns max error vs reference; test asserts below tolerance on a linear ODE",
     "physics", "physics"),
    # ── tensor-logic goals (added 2026-06-15 — repo was registered but had ZERO goals, dormant since May 14) ──
    ("tensor-logic tropical semiring: add a (min,+) tropical semiring to tensor_logic/semirings.py with zero/one identities; test asserts min-plus algebra laws",
     "tensor-logic", "tensor"),
    ("tensor-logic proof JSON export: proof_to_dict(result) serializes a ProofResult to a round-trippable dict; test asserts round-trip equality",
     "tensor-logic", "tensor"),
    ("tensor-logic rule linter: lint_rule(rule) returns errors for unbound variables or arity mismatch; test asserts it catches an unbound variable",
     "tensor-logic", "tensor"),
    ("tensor-logic execution metrics: exec_stats(trace) returns steps + rules-fired counts; test asserts counts on a fixture trace",
     "tensor-logic", "tensor"),
    ("tensor-logic reproducible seeding: deterministic_seed(cfg) seeds all RNG so research runs reproduce; test asserts two seeded runs match",
     "tensor-logic", "tensor"),
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

DONE_GOALS_FILE = REPORTS / "completed_goals.json"
# Cap a run at 30 min. MUST stay below the supervisor's stall threshold:
# otherwise the watchdog kills the run during its quiet straggler phase before it
# can print Done + persist completed_goals + write metrics — which is exactly the
# bug that kept skip-completed from ever accumulating.
RUN_TIMEOUT = 1800


def _load_done_goals() -> set[str]:
    try:
        return set(json.loads(DONE_GOALS_FILE.read_text()))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_done_goals(done: set[str]) -> None:
    with LOCK:
        DONE_GOALS_FILE.write_text(json.dumps(sorted(done), indent=2))


GOALGEN_SYSTEM = ("You propose concrete, high-value engineering goals for a codebase. "
                  "Output ONLY a JSON array. No prose.")


def generate_goals_for_repo(repo: str, n: int = 2) -> list[tuple]:
    """Ask M3 to propose fresh, repo-specific goals from the actual file tree.

    This is the self-directed loop: instead of hand-written filler, M3 reads each
    repo and decides what's worth building. Low-quality proposals are harmless —
    the tests-must-pass gate drops anything that doesn't actually work.
    """
    tree = file_tree(repo)
    out = m3(
        f"Propose {n} high-value engineering goals for this repo. Each must be ONE "
        f"function or capability with a concrete, verifiable acceptance test. Prefer "
        f"real features that advance the project over trivial utilities. Do not "
        f"duplicate what already exists.\n\n"
        f"REPO: {repo}\nFILES:\n{tree}\n\n"
        f'Output JSON: [{{"goal": "<one line: capability + function name + acceptance test>", '
        f'"lane": "impl"}}]\nONLY JSON.',
        GOALGEN_SYSTEM,
    )
    data = parse_json(out or "")
    goals = []
    if isinstance(data, list):
        for it in data:
            if isinstance(it, dict) and isinstance(it.get("goal"), str) and it["goal"].strip():
                goals.append((it["goal"].strip(), repo, it.get("lane", "impl")))
    log("pipeline", "goalgen", f"{repo}: proposed {len(goals)} goals")
    return goals


def goals_from_research(max_reports: int = 5) -> list[tuple]:
    """Close the research→action loop: turn accumulated discovery reports (which
    were being generated and never used) into concrete, buildable goals."""
    import glob
    promoted = REPORTS / "research_factory" / "promoted_goals.json"
    goals = []
    if promoted.exists():
        try:
            for item in json.loads(promoted.read_text()):
                repo = item.get("repo")
                goal = item.get("goal")
                experiment = item.get("experiment")
                if repo in REPOS and isinstance(goal, str) and isinstance(experiment, str):
                    goals.append((
                        f"{goal.strip()} Acceptance: {experiment.strip()}",
                        repo,
                        item.get("lane", "research"),
                    ))
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    files = sorted(glob.glob(str(REPORTS / "discovery" / "*.json")))[-max_reports:]
    if not files:
        return goals
    blob = ""
    for f in files:
        try:
            blob += f"\n=== {Path(f).name} ===\n" + Path(f).read_text()[:2500]
        except Exception:
            pass
    out = m3(
        "Turn these research findings into concrete, buildable engineering goals "
        "for our codebase. Each goal = ONE function/capability in an EXISTING repo "
        "with a verifiable acceptance test. Choose repo from: " + ", ".join(REPOS) + ".\n\n"
        f"RESEARCH:\n{blob[:12000]}\n\n"
        'Output JSON: [{"goal":"<capability + fn + test>","repo":"odysseus","lane":"impl"}] ONLY.',
        GOALGEN_SYSTEM,
    )
    data = parse_json(out or "")
    if isinstance(data, list):
        for it in data:
            if isinstance(it, dict) and it.get("goal") and it.get("repo") in REPOS:
                goals.append((it["goal"].strip(), it["repo"], it.get("lane", "impl")))
    deduped = list(dict.fromkeys(goals))
    log("pipeline", "research-goals", f"{len(deduped)} goals from research")
    return deduped


def aider_refactor(goal: str, repo: str) -> dict:
    """Run a refactor/complex goal through aider's agentic edit→test→repair loop on a
    REAL file (the tool-using lane). aider points at MiniMax via the OpenAI-compatible
    TokenRouter endpoint. Safe: failures return a status, never crash the pipeline."""
    root = REPOS[repo]
    m = re.search(r"([\w./-]+\.py)", goal)
    target = m.group(1) if m else None
    env = {**os.environ,
           "OPENAI_API_BASE": "https://api.tokenrouter.com/v1",
           "OPENAI_API_KEY": KEY}
    cmd = ["aider", "--model", "openai/MiniMax-M3",
           "--openai-api-base", "https://api.tokenrouter.com/v1",
           "--yes", "--no-stream", "--no-show-model-warnings",
           "--no-check-update", "--message", goal]
    if target and (root / target).exists():
        cmd.append(str(root / target))
    try:
        r = subprocess.run(cmd, cwd=str(root), env=env,
                           capture_output=True, text=True, timeout=300)
        ok = r.returncode == 0
        log("aider", goal[:45], f"rc={r.returncode} {'ok' if ok else r.stderr.strip()[:80]}")
        return {"name": goal[:45], "status": "ok" if ok else "invalid", "engine": "aider"}
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        log("aider", goal[:45], f"error: {e}")
        return {"name": goal[:45], "status": "error", "engine": "aider"}


def goals_from_refactor(repo: str, n: int = 3) -> list[tuple]:
    """Find refactor/improvement work in REAL existing code (duplication, complex
    functions, dead code) — high-value work that improves repos, not new filler."""
    ctx = ""
    try:
        r = subprocess.run(
            ["agent-repomap", str(REPOS[repo]), "refactor duplication complexity dead-code improvements"],
            capture_output=True, text=True, timeout=90,
        )
        ctx = r.stdout.strip()[:20000]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    out = m3(
        f"Find {n} concrete refactor/improvement opportunities in this repo: reduce "
        "duplication, simplify a complex function, remove dead code, or fix a clear "
        "issue. Each = ONE change to an EXISTING file with a verifiable test.\n\n"
        f"REPO MAP:\n{ctx}\n\n"
        'Output JSON: [{"goal":"refactor <path/file.py>: <what + test>","lane":"refactor"}] ONLY.',
        GOALGEN_SYSTEM,
    )
    data = parse_json(out or "")
    goals = []
    if isinstance(data, list):
        for it in data:
            if isinstance(it, dict) and it.get("goal"):
                goals.append((it["goal"].strip(), repo, it.get("lane", "refactor")))
    log("pipeline", "refactor-goals", f"{repo}: {len(goals)} refactor goals")
    return goals


def main() -> None:
    log("pipeline", "main", f"Start. Deadline={DEADLINE}. Now={datetime.now():%Y-%m-%d %H:%M}")
    log("pipeline", "main", "Architecture: M3 decomposes → Python orchestrates → M3 implements → Python validates")
    if not KEY:
        log("pipeline", "main", "FATAL: TOKENROUTER_API_KEY is not set")
        raise SystemExit(2)

    # Learning loop: adapt prompts from the previous run's failures before starting.
    update_learned_rules()

    done_goals = _load_done_goals()
    all_futures: list = []
    goal_of: dict = {}  # future -> goal_desc, for marking completed

    ex = ThreadPoolExecutor(max_workers=PIPELINE_WORKERS)

    # Lane 1: review chains (parallel across files, sequential within)
    for name, repo, target in REVIEW_TARGETS:
        all_futures.append(ex.submit(review_chain, name, repo, target))

    # Lane 2+3+5+6: decomposed implementation goals (skip ones already completed in a prior run)
    skipped = 0
    for goal_desc, repo, lane in HIGH_LEVEL_GOALS:
        if goal_desc in done_goals or repo not in REPOS:  # repo guard → safe to retarget REPOS
            skipped += 1
            continue
        fut = ex.submit(run_goal_decomposed, goal_desc, repo, lane)
        goal_of[fut] = goal_desc
        all_futures.append(fut)
    log("pipeline", "main", f"goals: {len(goal_of)} active, {skipped} already-done (skipped)")

    # Lane 2b: WIDEN THE ROAD — three high-value work sources feed a deep queue so
    # the 128 workers stay full. (1) self-directed per-repo goals, (2) research→goals
    # (uses the discovery reports), (3) refactor opportunities in real existing code.
    gen_futs = [ex.submit(generate_goals_for_repo, repo, 5) for repo in REPOS]
    gen_futs += [ex.submit(goals_from_refactor, repo, 3) for repo in REPOS]
    gen_futs.append(ex.submit(goals_from_research, 5))
    auto_added = 0
    for gf in as_completed(gen_futs):
        try:
            for goal_desc, repo, lane in gf.result():
                if goal_desc in done_goals or repo not in REPOS:
                    continue
                # refactor/complex work → aider's agentic tool-loop; rest → fast pipeline
                if lane == "refactor":
                    fut = ex.submit(aider_refactor, goal_desc, repo)
                else:
                    fut = ex.submit(run_goal_decomposed, goal_desc, repo, lane)
                goal_of[fut] = goal_desc
                all_futures.append(fut)
                auto_added += 1
        except Exception as e:
            log("pipeline", "goalgen", f"error: {e}")
    log("pipeline", "main", f"work sources: {auto_added} goals queued "
        f"(self-gen + refactor + research) across {len(REPOS)} repos")

    # Lane 4a: ArXiv research
    for topic, query in RESEARCH_QUERIES:
        all_futures.append(ex.submit(research_arxiv_and_synthesize, topic, query))

    # Lane 4b: agent tools audit
    all_futures.append(ex.submit(improve_agent_tools))

    # Collect, bounded by RUN_TIMEOUT so a few stuck futures can't stall the whole run
    ok = report = invalid = error = 0
    incomplete = 0
    try:
        for fut in as_completed(all_futures, timeout=RUN_TIMEOUT):
            try:
                r = fut.result()
                committed = False
                items = r if isinstance(r, list) else [r]
                for item in items:
                    s = item.get("status", "error")
                    if s == "ok":
                        ok += 1
                        committed = True
                    elif s in ("report", "clean", "skip_exists"): report += 1
                    elif s in ("invalid", "no_files"): invalid += 1
                    else: error += 1
                if committed and fut in goal_of:
                    done_goals.add(goal_of[fut])
                    _save_done_goals(done_goals)
            except Exception as e:
                log("pipeline", "future", f"exception: {e}")
                error += 1
    except TimeoutError:
        incomplete = sum(1 for f in all_futures if not f.done())
        log("pipeline", "main", f"RUN_TIMEOUT {RUN_TIMEOUT}s hit — {incomplete} futures still running, abandoning")

    # Don't wait on stragglers; force exit so the run always terminates promptly.
    ex.shutdown(wait=False, cancel_futures=True)
    log("pipeline", "main",
        f"Done. ok={ok} report={report} invalid={invalid} error={error} incomplete={incomplete}")

    # Progress tracker: append one metrics record per run so trends are visible.
    try:
        rec = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "ok": ok, "report": report, "invalid": invalid,
            "error": error, "incomplete": incomplete,
            "goals_active": len(goal_of), "goals_done_total": len(done_goals),
        }
        with LOCK, open(REPORTS / "pipeline_metrics.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:
        log("pipeline", "metrics", f"write failed: {e}")

    os._exit(0)


if __name__ == "__main__":
    main()
