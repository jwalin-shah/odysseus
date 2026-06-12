#!/usr/bin/env python3
"""odysseus: single front door that routes missions to agent CLIs through the sys harness.

Lanes:
  research -> direct arxiv API (no LLM)
  analyze  -> MiniMax-M3 via opencode (free tier; M3 NEVER writes code)
  code     -> coder waterfall (claude -> opencode/opus -> codex) inside a git
              worktree, gated by pytest; commit on green, discard on red.

Every call appends a feedback record to .credit-lab/ody/. The router retrains
on that data; .credit-lab/mining/FINDINGS.md holds the corpus-derived rules.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ODY_HOME = os.path.expanduser(os.environ.get("ODY_HOME", "~/projects/odysseus"))
FEEDBACK_DIR = os.path.join(ODY_HOME, ".credit-lab", "ody")
QUOTA_DB = os.path.join(ODY_HOME, ".credit-lab", "quota.db")
SYS_QUOTA = os.path.join(ODY_HOME, "v2", ".venv", "bin", "sys-quota")

DOCS = [
    "FABLE_BLUEPRINT.md", "V2_MASTERPLAN.md", "CODEX_WORKPAD.md",
    "SESSION_BRIEF.md", "ROADMAP.md", "V2_ADVANCED_RESEARCH.md",
    "README.md", "ACKNOWLEDGMENTS.md",
]
DOC_CHAR_CAP = 6000          # per doc
DOCS_TOTAL_CAP = 30000       # whole preamble

# argv templates; {prompt} is substituted. kind: coder | analyst | research
REGISTRY = {
    # bypass is safe here: coder runs only inside a disposable worktree with a
    # pytest gate; red = discarded
    "claude":        {"argv": ["claude", "-p", "--dangerously-skip-permissions", "{prompt}"], "kind": "coder"},
    "opencode-opus": {"argv": ["opencode", "run", "-m", "pioneer/claude-opus-4-8", "{prompt}"], "kind": "coder"},
    "codex":         {"argv": ["codex", "exec", "{prompt}"], "kind": "coder"},
    "opencode-m3":   {"argv": ["opencode", "run", "-m", "tokenrouter/MiniMax-M3", "{prompt}"], "kind": "analyst"},
    "gemini":        {"argv": ["gemini", "-p", "{prompt}"], "kind": "analyst"},
    "cursor-agent":  {"argv": ["cursor-agent", "-p", "{prompt}"], "kind": "coder"},
    "agy":           {"argv": ["agy", "-p", "{prompt}"], "kind": "analyst"},
}

CODE_WATERFALL = ["claude", "opencode-opus", "codex"]
ANALYZE_WATERFALL = ["opencode-m3", "gemini"]

CODE_WORDS = ("fix", "implement", "refactor", "rewrite", "add ", "patch",
              "make the test", "bug", "broken", "failing")
RESEARCH_WORDS = ("arxiv", "paper", "papers", "literature")
ANALYZE_WORDS = ("analyze", "analyse", "review", "summarize", "summarise",
                 "diagnose", "explain", "why does", "what is", "audit")


def classify(mission):
    m = mission.lower()
    if any(w in m for w in RESEARCH_WORDS):
        return "research"
    # code beats analyze when both match: "fix" implies a write
    if any(w in m for w in CODE_WORDS):
        return "code"
    if any(w in m for w in ANALYZE_WORDS):
        return "analyze"
    return "code"


def cli_exists(tool):
    return shutil.which(REGISTRY[tool]["argv"][0]) is not None


def quota_ok(tool):
    """Gate on sys-quota. Fail-open until the harness is trustworthy."""
    if not os.path.exists(SYS_QUOTA) or not os.path.exists(QUOTA_DB):
        return True
    try:
        rc = subprocess.run([SYS_QUOTA, "check", "--type", tool, "--db", QUOTA_DB],
                            capture_output=True, timeout=10).returncode
        return rc != 75  # 75 = exhausted; 2 = dim not initialized -> allow
    except Exception:
        return True


def load_docs():
    parts, total = [], 0
    for name in DOCS:
        path = os.path.join(ODY_HOME, name)
        if not os.path.exists(path):
            continue
        text = open(path, errors="replace").read()[:DOC_CHAR_CAP]
        if total + len(text) > DOCS_TOTAL_CAP:
            break
        parts.append(f"--- {name} ---\n{text}")
        total += len(text)
    return "\n\n".join(parts)


def pick(waterfall):
    for tool in waterfall:
        if cli_exists(tool) and quota_ok(tool):
            return tool
    return None


def run_tool(tool, prompt, cwd, timeout):
    argv = [a.replace("{prompt}", prompt) for a in REGISTRY[tool]["argv"]]
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s", time.time() - t0


def do_research(mission, args):
    q = urllib.parse.quote(mission)
    url = f"https://export.arxiv.org/api/query?search_query=all:{q}&max_results=10"
    with urllib.request.urlopen(url, timeout=30) as r:
        feed = r.read().decode()
    titles = [seg.split("</title>")[0].strip()
              for seg in feed.split("<title>")[2:]]  # first <title> is the feed's own
    out = "\n".join(f"- {t}" for t in titles) or "(no results)"
    print(out)
    return {"agent_used": "arxiv", "result": "ok", "test_passed": None, "output": out[:2000]}


def do_analyze(mission, args, docs):
    prompt = (f"{docs}\n\nMISSION (analysis only — do NOT edit files, do NOT run "
              f"write commands; produce a report):\n{mission}" if docs else mission)
    if args.tool is None:
        # direct TokenRouter call beats spawning an agent CLI for pure analysis
        try:
            import m3
            t0 = time.time()
            out = m3.complete(prompt, timeout=args.timeout)
            print(out)
            return {"agent_used": "m3-direct", "result": "ok", "test_passed": None,
                    "duration": round(time.time() - t0, 1), "output": out[:2000]}
        except Exception as e:
            print(f"[ody] m3-direct failed ({e}); falling back", file=sys.stderr)
    tool = args.tool or pick(ANALYZE_WATERFALL)
    if tool is None:
        return {"agent_used": None, "result": "no_tool_available", "test_passed": None}
    rc, out, err, dur = run_tool(tool, prompt, args.repo, args.timeout)
    print(out or err)
    return {"agent_used": tool, "result": "ok" if rc == 0 else f"exit_{rc}",
            "test_passed": None, "duration": round(dur, 1), "output": out[:2000]}


def do_code(mission, args, docs):
    tool = args.tool or pick(CODE_WATERFALL)
    if tool is None:
        return {"agent_used": None, "result": "no_tool_available", "test_passed": None}
    repo = os.path.abspath(args.repo)
    branch = f"ody-{tool}-{int(time.time())}"
    wt = os.path.join(repo, ".ody-worktrees", branch)
    if args.dry_run:
        print(f"[dry-run] lane=code tool={tool} branch={branch} test={args.test!r}")
        return {"agent_used": tool, "result": "dry_run", "test_passed": None}

    subprocess.run(["git", "-C", repo, "worktree", "add", "-b", branch, wt, "HEAD"],
                   check=True, capture_output=True)
    try:
        repomap = ""
        ody_map = os.path.join(ODY_HOME, "v2", ".venv", "bin", "ody-map")
        if os.path.exists(ody_map):
            try:
                mp = subprocess.run([ody_map, repo], capture_output=True, text=True,
                                    timeout=60)
                if mp.returncode == 0 and mp.stdout:
                    repomap = f"\n\n--- repo map ---\n{mp.stdout[:8000]}"
            except Exception:
                pass
        prompt = (f"{docs}{repomap}\n\nMISSION (you are in an isolated git worktree; "
                  f"edit files directly; the gate is: `{args.test}`):\n{mission}"
                  if docs or repomap else mission)
        rc, out, err, dur = run_tool(tool, prompt, wt, args.timeout)
        test = subprocess.run(args.test, shell=True, cwd=wt, capture_output=True,
                              text=True, timeout=600)
        passed = test.returncode == 0
        if passed:
            subprocess.run(["git", "-C", wt, "add", "-A"], capture_output=True)
            subprocess.run(["git", "-C", wt, "commit", "-m", f"ody({tool}): {mission[:60]}"],
                           capture_output=True)
            print(f"PASS — committed on branch {branch}\n{out[-1500:]}")
        else:
            print(f"FAIL — discarded\n{test.stdout[-1000:]}{test.stderr[-500:]}")
        return {"agent_used": tool, "result": "ok" if rc == 0 else f"exit_{rc}",
                "test_passed": passed, "branch": branch if passed else None,
                "duration": round(dur, 1)}
    finally:
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt],
                       capture_output=True)
        # keep the branch only on green
        if not locals().get("passed", False):
            subprocess.run(["git", "-C", repo, "branch", "-D", branch], capture_output=True)


def write_feedback(record):
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    path = os.path.join(FEEDBACK_DIR, f"{int(time.time() * 1000)}.jsonl")
    with open(path, "w") as f:
        f.write(json.dumps(record) + "\n")
    return path


def main(argv=None):
    p = argparse.ArgumentParser(prog="ody", description=__doc__.splitlines()[0])
    p.add_argument("mission", help="what to do, in plain words")
    p.add_argument("--repo", default=os.getcwd(), help="target repo (default: cwd)")
    p.add_argument("--test", default="pytest -q", help="gate command for code lane")
    p.add_argument("--lane", choices=["code", "analyze", "research"],
                   help="override the router")
    p.add_argument("--tool", choices=sorted(REGISTRY), help="override tool selection")
    p.add_argument("--timeout", type=int, default=900, help="agent timeout seconds")
    p.add_argument("--no-docs", action="store_true", help="skip the 8-doc preamble")
    p.add_argument("--dry-run", action="store_true", help="print routing decision only")
    args = p.parse_args(argv)

    lane = args.lane or classify(args.mission)
    docs = "" if args.no_docs else load_docs()
    if args.dry_run and lane != "code":
        tool = args.tool or pick(ANALYZE_WATERFALL if lane == "analyze" else [])
        print(f"[dry-run] lane={lane} tool={tool or 'arxiv'}")
        return 0

    t0 = time.time()
    if lane == "research":
        rec = do_research(args.mission, args)
    elif lane == "analyze":
        rec = do_analyze(args.mission, args, docs)
    else:
        rec = do_code(args.mission, args, docs)

    rec.update({"ts": time.time(), "prompt": args.mission, "lane": lane,
                "cost": None, "duration": rec.get("duration", round(time.time() - t0, 1))})
    path = write_feedback(rec)
    print(f"[ody] feedback -> {path}", file=sys.stderr)
    return 0 if rec.get("result") in ("ok", "dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
