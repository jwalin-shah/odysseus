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
import pathlib
import shutil
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()

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
    # Short aliases: ca = claude opus (best), cb = claude sonnet (mid), cc = haiku (fast).
    # All three go through OpenCode+Pioneer so they share one API key and quota bucket.
    "ca":            {"argv": ["opencode", "run", "-m", "pioneer/claude-opus-4-8", "{prompt}"], "kind": "coder", "alias_of": "opencode-opus"},
    "cb":            {"argv": ["opencode", "run", "-m", "pioneer/claude-sonnet-4-6", "{prompt}"], "kind": "coder"},
    "cc":            {"argv": ["opencode", "run", "-m", "pioneer/claude-haiku-4-5", "{prompt}"], "kind": "coder"},
    # codex refuses to run outside a trusted git repo; --skip-git-repo-check
    # lets it run anywhere. We route through Pioneer (matching ca/cb/cc)
    # so the ChatGPT plan model restrictions don't bite us.
    "codex":         {"argv": ["codex", "exec", "--skip-git-repo-check",
                               "-c", "model_provider=pioneer",
                               "-m", "pioneer/claude-haiku-4-5", "{prompt}"], "kind": "coder"},
    "opencode-m3":   {"argv": ["opencode", "run", "-m", "tokenrouter/MiniMax-M3", "{prompt}"], "kind": "analyst"},
    "m3":            {"argv": ["opencode", "run", "-m", "tokenrouter/MiniMax-M3", "{prompt}"], "kind": "analyst", "alias_of": "opencode-m3"},
    # gemini refuses to run outside a trusted directory; --skip-trust
    # lets it run anywhere. Note: --skip-trust must come BEFORE -p, otherwise
    # gemini treats the next arg as the -p value, not a flag.
    "gemini":        {"argv": ["gemini", "--skip-trust", "-p", "{prompt}"], "kind": "analyst"},
    "cursor-agent":  {"argv": ["cursor-agent", "-p", "{prompt}"], "kind": "coder"},
    "agy":           {"argv": ["agy", "-p", "{prompt}"], "kind": "analyst"},
}

CODE_WATERFALL = ["claude", "ca", "cb", "codex"]
ANALYZE_WATERFALL = ["opencode-m3", "gemini"]

CODE_WORDS = ("fix", "implement", "refactor", "rewrite", "add ", "patch",
              "make the test", "bug", "broken", "failing")
RESEARCH_WORDS = ("arxiv", "paper", "papers", "literature")
ANALYZE_WORDS = ("analyze", "analyse", "review", "summarize", "summarise",
                 "diagnose", "explain", "why does", "what is", "audit")

OPERATOR_COMMANDS = {
    "ask",
    "chat",
    "logs",
    "pilot",
    "run",
    "sessions",
    "start",
    "status",
    "stop",
}


def _exec(argv):
    os.execvp(argv[0], argv)


def _operator_command(argv):
    command = argv[0]
    rest = argv[1:]

    if command == "run":
        return rest
    if command == "chat":
        _exec([sys.executable, os.path.join(ODY_HOME, "src", "ody_talk.py"), *rest])
        return 0
    if command == "pilot":
        prompt = os.path.join(ODY_HOME, "ORCHESTRATOR.md")
        with open(prompt, encoding="utf-8") as handle:
            instructions = handle.read()
        _exec(["claude", "--append-system-prompt", instructions, *rest])
        return 0
    if command == "sessions":
        _exec(["ody-sessions", *rest])
        return 0
    if command == "ask":
        _exec(["ody-ask", *rest])
        return 0
    if command == "logs":
        log_path = os.path.expanduser("~/Library/Logs/odysseus-server.log")
        _exec(["tail", "-n", "120", "-f", log_path, *rest])
        return 0

    label = f"gui/{os.getuid()}/com.odysseus.server"
    plist = os.path.expanduser("~/Library/LaunchAgents/com.odysseus.server.plist")
    if command == "start":
        return subprocess.call(["launchctl", "kickstart", "-k", label])
    if command == "stop":
        return subprocess.call(["launchctl", "kill", "SIGTERM", label])
    if command == "status":
        health_url = os.environ.get(
            "ODYSSEUS_HEALTH_URL",
            "http://127.0.0.1:7860/api/orchestration/health",
        )
        try:
            with urllib.request.urlopen(health_url, timeout=5) as response:
                health = json.loads(response.read().decode("utf-8"))
            print(json.dumps(health, indent=2, sort_keys=True))
            return 0 if health.get("healthy") else 1
        except Exception as exc:
            print(f"Odysseus health check failed: {exc}", file=sys.stderr)
            print(f"LaunchAgent: {plist}", file=sys.stderr)
            return 1
    raise AssertionError(f"unhandled operator command: {command}")


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


def route(mission):
    """M3 is the routing engine (free); keyword tree is the fallback.

    M3 only picks the lane — tool selection stays in the waterfalls, so it can
    never route code to itself. ODY_ROUTER=keyword disables the LLM hop.
    """
    if os.environ.get("ODY_ROUTER") == "keyword":
        return classify(mission), "keyword"
    try:
        import m3
        out = m3.complete(
            f"Mission: {mission}\n\nPick exactly one lane:\n"
            "- code: the mission asks to change/fix/write files or make tests pass\n"
            "- analyze: read-only diagnosis, review, summary, explanation\n"
            "- research: find papers/literature (arxiv)\n"
            "Reply with one word: code, analyze, or research.",
            system="You are a router. Reply with a single word.", max_tokens=600,
            timeout=30)
        if "</think>" in out:
            out = out.split("</think>")[-1]
        lane = out.strip().lower().split()[-1].strip(".")
        if lane in ("code", "analyze", "research"):
            return lane, "m3"
    except Exception:
        pass
    return classify(mission), "keyword"


def cli_exists(tool):
    return shutil.which(REGISTRY[tool]["argv"][0]) is not None


# daily call budgets per tool; deducted 1 per dispatch
# Aliases (ca, cb, cc, m3) share quota with their canonical name.
QUOTA_LIMITS = {"claude": 300, "opencode-opus": 100, "ca": 100, "cb": 200, "cc": 400,
                "codex": 200,
                "opencode-m3": 2000, "m3": 2000, "m3-direct": 2000, "m3-hybrid": 2000,
                "gemini": 200, "cursor-agent": 100, "agy": 200}


def _quota(args_list):
    return subprocess.run([SYS_QUOTA, *args_list, "--db", QUOTA_DB],
                          capture_output=True, text=True, timeout=10)


def ensure_quota_db():
    if not os.path.exists(SYS_QUOTA) or os.path.exists(QUOTA_DB):
        return
    os.makedirs(os.path.dirname(QUOTA_DB), exist_ok=True)
    for tool, lim in QUOTA_LIMITS.items():
        _quota(["init", "--type", tool, "--limit", str(lim), "--window", "1d"])


def quota_ok(tool):
    """Gate on sys-quota. Fail-open only if the harness itself is unavailable."""
    if not os.path.exists(SYS_QUOTA):
        return True
    try:
        ensure_quota_db()
        rc = _quota(["check", "--type", tool]).returncode
        return rc != 75  # 75 = exhausted; 2 = dim not initialized -> allow
    except Exception:
        return True


def quota_deduct(tool):
    """Deduct one call; return remaining for the feedback record."""
    if not os.path.exists(SYS_QUOTA) or tool not in QUOTA_LIMITS:
        return None
    try:
        ensure_quota_db()
        _quota(["deduct", "--type", tool, "--amount", "1"])
        out = _quota(["check", "--type", tool]).stdout
        return float(out.split(":")[-1]) if "REMAINING" in out else None
    except Exception:
        return None


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


def pioneer_env():
    """opencode's pioneer provider reads {env:PIONEER_API_KEY}; resolve it from
    Infisical (/providers/pioneer api_key) when absent."""
    env = os.environ.copy()
    if not env.get("PIONEER_API_KEY"):
        try:
            out = subprocess.run(
                ["infisical", "export", "--env", "dev", "--path", "/providers/pioneer",
                 "--format", "dotenv"], capture_output=True, text=True, timeout=20).stdout
            for line in out.splitlines():
                if line.startswith("api_key="):
                    env["PIONEER_API_KEY"] = line.split("=", 1)[1].strip("'\"")
        except Exception:
            pass
    return env


def run_tool(tool, prompt, cwd, timeout):
    argv = [a.replace("{prompt}", prompt) for a in REGISTRY[tool]["argv"]]
    env = pioneer_env() if tool.startswith("opencode") else None
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s", time.time() - t0


def run_agent(agent, prompt, cwd=None, timeout=180):
    """Run a single agent CLI with a prompt. Returns (rc, stdout, stderr, dur).

    Recognised agents: claude, ca, cb, cc, codex, gemini, agy, opencode-m3,
    m3, opencode-opus, cursor-agent. Looks the agent up in REGISTRY,
    substitutes the prompt, sets up the right env (Pioneer API key for
    opencode-launched agents), and runs.
    """
    if agent not in REGISTRY:
        raise ValueError(
            f"unknown agent {agent!r}; known: {sorted(REGISTRY)}"
        )
    template = REGISTRY[agent]["argv"]
    argv = [template[0]] + [
        (p.format(prompt=prompt) if p == "{prompt}" else p)
        for p in template[1:]
    ]
    env = pioneer_env() if argv[0] in ("opencode", "codex") else None
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=cwd or ODY_HOME, capture_output=True,
                           text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s", time.time() - t0


def do_research(mission, args):
    q = urllib.parse.quote(mission)
    url = f"https://export.arxiv.org/api/query?search_query=all:{q}&max_results=10"
    with urllib.request.urlopen(url, timeout=30, context=SSL_CTX) as r:
        feed = r.read().decode()
    items = []
    for entry in feed.split("<entry>")[1:]:
        title = entry.split("<title>")[1].split("</title>")[0].strip()
        summary = (entry.split("<summary>")[1].split("</summary>")[0].strip()[:600]
                   if "<summary>" in entry else "")
        items.append(f"- {title}\n  {summary}")
    corpus = "\n".join(items)
    if not corpus:
        print("(no results)")
        return {"agent_used": "arxiv", "result": "ok", "test_passed": None}
    agent = "arxiv"
    out = corpus
    try:
        import m3
        out = m3.complete(f"<papers>\n{corpus}\n</papers>\n\nMission: {mission}\n"
                          "Synthesize: which papers matter and why, key takeaways, "
                          "and what to read first.", timeout=args.timeout)
        agent = "arxiv+m3"
    except Exception as e:
        print(f"[ody] m3 synthesis failed ({e}); raw results follow", file=sys.stderr)
    print(out)
    return {"agent_used": agent, "result": "ok", "test_passed": None,
            "output": out[:2000]}


def do_analyze(mission, args, docs):
    prompt = (f"{docs}\n\nMISSION (analysis only — do NOT edit files, do NOT run "
              f"write commands; produce a report):\n{mission}" if docs else mission)
    if args.tool is None:
        # Fusion path: --fuse flag or ODY_FUSE=1 env var enables multi-model panel synthesis.
        # Budget panel (M3 + DeepSeek + free OpenRouter) synthesized by Claude A.
        # Skips M3-direct and goes straight to parallel dispatch.
        use_fusion = getattr(args, "fuse", False) or os.environ.get("ODY_FUSE") == "1"
        if use_fusion:
            try:
                from src.fusion import fuse_sync, budget_panel
                t0 = time.time()
                result_data = fuse_sync(
                    prompt,
                    panel=budget_panel(),
                    synth_backend=getattr(args, "synth_backend", "ca"),
                    return_analysis=True,
                )
                answer = result_data["answer"]
                print(answer)
                return {"agent_used": "fusion-budget", "result": "ok", "test_passed": None,
                        "duration": round(time.time() - t0, 1), "output": answer[:2000]}
            except Exception as e:
                print(f"[ody] fusion failed ({e}); falling back to m3-direct", file=sys.stderr)

        # direct TokenRouter call beats spawning an agent CLI for pure analysis
        try:
            import m3
            t0 = time.time()
            out = m3.complete(prompt, max_tokens=8192, timeout=args.timeout)
            answer = out.split("</think>")[-1].strip()
            print(out)
            # exit-0 with an empty post-think payload is NOT ok (M3 can burn
            # its whole budget reasoning) — grade honestly so the router learns
            result = "ok" if answer else "empty_output"
            return {"agent_used": "m3-direct", "result": result, "test_passed": None,
                    "duration": round(time.time() - t0, 1), "output": answer[:2000]}
        except Exception as e:
            print(f"[ody] m3-direct failed ({e}); falling back", file=sys.stderr)
    tool = args.tool or pick(ANALYZE_WATERFALL)
    if tool is None:
        return {"agent_used": None, "result": "no_tool_available", "test_passed": None}
    rc, out, err, dur = run_tool(tool, prompt, args.repo, args.timeout)
    print(out or err)
    return {"agent_used": tool, "result": "ok" if rc == 0 else f"exit_{rc}",
            "test_passed": None, "duration": round(dur, 1), "output": out[:2000]}


def hybrid_patch(wt, spec, mission):
    """M3 drafts one function body; a deterministic AST splice applies it.

    The corpus' only working M3-code pattern (2/2): function-scoped, never a diff.
    Returns (rc, out, err).
    """
    import ast as ast_mod
    import m3
    rel, _, func = spec.partition(":")
    path = os.path.join(wt, rel)
    if not func or not os.path.exists(path):
        return 1, "", f"bad --hybrid spec or missing file: {spec}"
    src = open(path).read()
    node = next((n for n in ast_mod.walk(ast_mod.parse(src))
                 if isinstance(n, (ast_mod.FunctionDef, ast_mod.AsyncFunctionDef))
                 and n.name == func), None)
    if node is None:
        return 1, "", f"function {func} not found in {rel}"
    lines = src.splitlines(keepends=True)
    current = "".join(lines[node.lineno - 1:node.end_lineno])
    out = m3.complete(
        "Rewrite this Python function to satisfy the mission. Return ONLY the "
        f"complete function definition — no fences, no prose.\n\nMISSION: {mission}"
        f"\n\nCURRENT:\n{current}",
        system="You output only valid Python code.")
    code = out.strip()
    if "</think>" in code:
        code = code.split("</think>")[-1].strip()
    if code.startswith("```"):
        code = code.split("```")[1]
        code = code[code.find("\n") + 1:] if code.startswith(("python", "py")) else code
    code = code.strip()
    try:
        new_tree = ast_mod.parse(code)
    except SyntaxError as e:
        return 1, "", f"M3 returned invalid Python: {e}"
    if not (len(new_tree.body) == 1
            and getattr(new_tree.body[0], "name", None) == func):
        return 1, "", "M3 did not return exactly the requested function"
    indent = " " * node.col_offset
    body = "".join((indent + l) if l.strip() else l
                   for l in code.splitlines(keepends=True))
    if not body.endswith("\n"):
        body += "\n"
    lines[node.lineno - 1:node.end_lineno] = [body]
    open(path, "w").write("".join(lines))
    return 0, f"spliced {func} in {rel}", ""


def derive_hybrid_spec(mission, repo):
    """Ask M3 (free) to name the FILE:FUNC a mission targets, so the hybrid
    splice can be attempted before any paid coder. Returns spec or None."""
    try:
        import m3
        listing = subprocess.run(
            ["git", "-C", repo, "ls-files", "*.py"],
            capture_output=True, text=True, timeout=15).stdout[:4000]
        out = m3.complete(
            f"<files>\n{listing}\n</files>\n\nMission: {mission}\n\n"
            "If this mission is a fix scoped to ONE function in ONE of these "
            "files, reply with exactly FILE.py:function_name and nothing else. "
            "Otherwise reply NO.", system="You are a precise code locator.",
            max_tokens=600, timeout=60)
        if "</think>" in out:
            out = out.split("</think>")[-1]
        spec = out.strip().splitlines()[-1].strip()
        if spec != "NO" and ":" in spec and spec.split(":")[0].endswith(".py"):
            return spec
    except Exception:
        pass
    return None


def _venv_bin(project_dir):
    """Locate the project's venv bin directory, walking up if in a worktree.

    A git worktree is a separate checkout at
    ``<main_repo>/.ody-worktrees/<branch>/`` and does NOT have its own
    ``.venv/``. Code running inside a worktree must still resolve to the
    main repo's venv. Try the current dir first, then walk up.
    """
    p = pathlib.Path(project_dir).resolve()
    for candidate in (p, p.parent, p.parent.parent):
        v = candidate / ".venv" / "bin"
        if v.is_dir():
            return v
    return None


def _worktree_test_env(repo):
    """Build the env for a worktree test subprocess.

    The worktree is a separate git checkout; it does NOT have its own
    ``.venv/``. We prepend the project's venv bin to PATH (walking up from
    the worktree to the main repo if needed) so ``pytest``, ``python``,
    etc. resolve to the project venv, not the system Python. Without this,
    ``pytest -q`` fails with ``pytest: command not found``.
    """
    env = os.environ.copy()
    venv_bin = _venv_bin(repo)
    if venv_bin is not None:
        venv_bin_str = str(venv_bin)
        if venv_bin_str not in env.get("PATH", "").split(":"):
            env["PATH"] = f"{venv_bin_str}:{env.get('PATH', '')}"
    return env


def do_code(mission, args, docs):
    if not args.hybrid and not args.tool and not args.dry_run:
        # cheap-first default: try the free M3 splice before any paid coder
        spec = derive_hybrid_spec(mission, os.path.abspath(args.repo))
        if spec:
            print(f"[ody] cheap-first: trying m3-hybrid on {spec}", file=sys.stderr)
            args.hybrid = spec
            rec = do_code(mission, args, docs)
            if rec.get("test_passed"):
                return rec
            args.hybrid = None
            print("[ody] hybrid failed; escalating to coder waterfall",
                  file=sys.stderr)
    if args.hybrid:
        tool = "m3-hybrid"
    else:
        tool = args.tool or pick(CODE_WATERFALL)
    if tool is None:
        return {"agent_used": None, "result": "no_tool_available", "test_passed": None}
    repo = os.path.abspath(args.repo)
    branch = f"ody-{tool}-{int(time.time())}"
    wt = os.path.join(repo, ".ody-worktrees", branch)
    if args.dry_run:
        print(f"[dry-run] lane=code tool={tool} branch={branch} test={args.test!r}")
        return {"agent_used": tool, "result": "dry_run", "test_passed": None}
    if tool == "m3-hybrid":
        subprocess.run(["git", "-C", repo, "worktree", "add", "-b", branch, wt, "HEAD"],
                       check=True, capture_output=True)
        try:
            t0 = time.time()
            passed, rc, err = False, 1, ""
            goal = mission
            for attempt in range(3):  # M3 self-corrects on gate feedback (free)
                rc, out, err = hybrid_patch(wt, args.hybrid, goal)
                if rc != 0:
                    break
                test = subprocess.run(args.test, shell=True, cwd=wt,
                                      env=_worktree_test_env(repo),
                                      capture_output=True, text=True, timeout=600)
                passed = test.returncode == 0
                if passed:
                    break
                goal = (f"{mission}\n\nYour previous attempt failed the gate "
                        f"`{args.test}` with:\n{(test.stdout + test.stderr)[-1500:]}\n"
                        "Fix the function properly this time.")
                print(f"[ody] hybrid attempt {attempt + 1} red; retrying with "
                      "gate feedback", file=sys.stderr)
            dur = time.time() - t0
            if passed:
                subprocess.run(["git", "-C", wt, "add", "-A"], capture_output=True)
                subprocess.run(["git", "-C", wt, "commit", "-m",
                                f"ody(m3-hybrid): {mission[:60]}"], capture_output=True)
                print(f"PASS — committed on branch {branch} ({out})")
            else:
                print(f"FAIL — discarded ({err or 'gate red'})")
            return {"agent_used": tool, "result": "ok" if rc == 0 else "splice_failed",
                    "test_passed": passed, "branch": branch if passed else None,
                    "duration": round(dur, 1)}
        finally:
            subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt],
                           capture_output=True)
            if not locals().get("passed", False):
                subprocess.run(["git", "-C", repo, "branch", "-D", branch],
                               capture_output=True)

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
        test = subprocess.run(args.test, shell=True, cwd=wt, env=_worktree_test_env(repo),
                              capture_output=True, text=True, timeout=600)
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
    # Honor ODY_FEEDBACK_DIR if set, so do_dispatch_mission can route
    # feedback to the dispatch's log dir (and do_dispatch_status can find
    # it there). Default to the project-wide FEEDBACK_DIR.
    feedback_dir = os.environ.get("ODY_FEEDBACK_DIR", FEEDBACK_DIR)
    os.makedirs(feedback_dir, exist_ok=True)
    path = os.path.join(feedback_dir, f"{int(time.time() * 1000)}.jsonl")
    # Stamp dispatch_id from env if set, so do_dispatch_status can match
    # the feedback record back to its dispatch.
    dispatch_id = os.environ.get("ODY_DISPATCH_ID")
    if dispatch_id:
        record = dict(record)
        record["dispatch_id"] = dispatch_id
    with open(path, "w") as f:
        f.write(json.dumps(record) + "\n")
    return path


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "supervise":
        from ody_supervisor import supervise_main
        return supervise_main(argv[1:])
    if argv and argv[0] in OPERATOR_COMMANDS:
        routed = _operator_command(argv)
        if isinstance(routed, int):
            return routed
        argv = routed
    p = argparse.ArgumentParser(prog="ody", description=__doc__.splitlines()[0])
    p.add_argument("mission", help="what to do, in plain words")
    p.add_argument("--repo", default=os.getcwd(), help="target repo (default: cwd)")
    p.add_argument("--test", default="pytest -q", help="gate command for code lane")
    p.add_argument("--lane", choices=["code", "analyze", "research"],
                   help="override the router")
    p.add_argument("--tool", choices=sorted(REGISTRY), help="override tool selection")
    p.add_argument("--hybrid", metavar="FILE:FUNC",
                   help="code lane: M3 drafts FUNC's body, AST splice applies it")
    p.add_argument("--timeout", type=int, default=900, help="agent timeout seconds")
    p.add_argument("--no-docs", action="store_true", help="skip the 8-doc preamble")
    p.add_argument("--dry-run", action="store_true", help="print routing decision only")
    p.add_argument("--fuse", action="store_true",
                   help="use multi-model panel synthesis (budget panel: M3+DeepSeek+free OR) instead of M3-direct")
    p.add_argument("--synth-backend", default="ca", choices=["ca", "cb", "pioneer", "m3"],
                   help="backend for fusion final synthesis (default: ca = Claude A subscription)")
    args = p.parse_args(argv)

    if args.lane:
        lane, router = args.lane, "explicit"
    else:
        lane, router = route(args.mission)
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

    remaining = quota_deduct(rec.get("agent_used"))
    rec.update({"ts": time.time(), "prompt": args.mission, "lane": lane,
                "router": router, "quota_remaining": remaining, "cost": None,
                "duration": rec.get("duration", round(time.time() - t0, 1))})
    try:  # M3 grades the attempt (free, advisory — the gate already judged)
        import m3
        rec["post_mortem"] = m3.complete(
            f"Mission: {args.mission}\nAgent: {rec.get('agent_used')} "
            f"Result: {rec.get('result')} test_passed: {rec.get('test_passed')}\n"
            "One sentence: what does this outcome teach the router?",
            max_tokens=400, timeout=30).split("</think>")[-1].strip()[:300]
    except Exception:
        pass
    path = write_feedback(rec)
    print(f"[ody] feedback -> {path}", file=sys.stderr)
    return 0 if rec.get("result") in ("ok", "dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
