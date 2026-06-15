#!/usr/bin/env python3
"""
M3 Supervisor — runs all night until June 17 free tier ends.

Monitors all M3 worker scripts. If any dies (crash, OOM, exception),
restarts it automatically. Checks every 60s.

Also runs a continuous discovery loop every 30 min that mines:
  - New model releases (Hugging Face, arXiv, model blogs)
  - New CLI agent tools
  - New benchmarks
  - New agent frameworks (DSPy, PromptFoo updates, etc.)

Usage:
  nohup python3 scripts/m3_supervisor.py >> /tmp/m3_supervisor.log 2>&1 &
  echo "supervisor PID: $!"

To watch all logs at once:
  tail -f /tmp/m3_supervisor.log /tmp/m3_forever.log /tmp/m3_pipeline.log /tmp/m3_model_research.log /tmp/m3_discovery.log
"""
import json
import os
import re
import ssl
import subprocess
import sys
import time
import threading
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

KEY = os.environ.get("TOKENROUTER_API_KEY", "sk-umkgY44a1AeYkZa2ZCZFpPwnGY4ZeedbFByHfm8eZcfRKXZJ")
SCRIPTS = Path(__file__).parent
DEADLINE = datetime(2026, 6, 17, 23, 59)
LOCK = threading.Lock()
DISCOVERY_REPORTS = SCRIPTS.parent / "reports" / "discovery"
DISCOVERY_REPORTS.mkdir(parents=True, exist_ok=True)

PYTHON = sys.executable  # same Python that's running us


def log(name: str, msg: str) -> None:
    with LOCK:
        print(f"[{datetime.now().strftime('%H:%M:%S')}][{name}] {msg}", flush=True)


# ─── Managed workers ──────────────────────────────────────────────────────────
# Each entry: (script_path, log_file)
# Supervisor ensures exactly one instance of each is running at all times.

WORKERS = [
    (SCRIPTS / "m3_forever.py",        Path("/tmp/m3_forever.log")),
    (SCRIPTS / "m3_pipeline.py",       Path("/tmp/m3_pipeline.log")),
    (SCRIPTS / "m3_model_research.py", Path("/tmp/m3_model_research.log")),
]

# Track PIDs we started
_pids: dict[str, int] = {}


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def find_existing_pid(script_path: Path) -> int | None:
    """Check if a script is already running (from before supervisor started)."""
    name = script_path.name
    r = subprocess.run(
        ["pgrep", "-f", name], capture_output=True, text=True
    )
    pids = [int(p) for p in r.stdout.strip().split() if p.isdigit()]
    return pids[0] if pids else None


def start_worker(script: Path, log_file: Path) -> int:
    """Start a worker script. Returns PID."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as lf:
        proc = subprocess.Popen(
            [PYTHON, str(script)],
            stdout=lf, stderr=lf,
            cwd=str(SCRIPTS.parent),
            start_new_session=True,  # detach from our process group
        )
    log("supervisor", f"started {script.name} PID={proc.pid}")
    return proc.pid


def supervise_workers() -> None:
    """Main supervision loop. Check workers every 60s, restart if dead."""
    # Seed with existing PIDs (workers launched before supervisor)
    for script, log_file in WORKERS:
        existing = find_existing_pid(script)
        if existing:
            _pids[script.name] = existing
            log("supervisor", f"found existing {script.name} PID={existing}")

    while datetime.now() < DEADLINE:
        for script, log_file in WORKERS:
            pid = _pids.get(script.name)
            if pid is None or not is_running(pid):
                reason = "never started" if pid is None else f"PID {pid} died"
                log("supervisor", f"{script.name} {reason} — restarting")
                new_pid = start_worker(script, log_file)
                _pids[script.name] = new_pid
            else:
                log("supervisor", f"{script.name} OK PID={pid}")
        time.sleep(60)

    log("supervisor", f"Deadline reached {DEADLINE} — stopping supervision")


# ─── M3 API ───────────────────────────────────────────────────────────────────

def m3(prompt: str) -> str:
    payload = json.dumps({
        "model": "MiniMax-M3",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 65536,
    }).encode()
    try:
        req = urllib.request.Request(
            "https://api.tokenrouter.com/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600, context=CTX) as r:
            body = json.load(r)
        raw = body["choices"][0]["message"]["content"]
        out = raw.split("</think>", 1)[1].strip() if "</think>" in raw else raw.strip()
        return out
    except Exception as e:
        log("m3", f"error: {e}")
        return ""


# ─── ArXiv search ─────────────────────────────────────────────────────────────

def arxiv_search(query: str, n: int = 5) -> list[dict]:
    params = urllib.parse.urlencode({"search_query": f"all:{query}", "start": 0, "max_results": n})
    try:
        with urllib.request.urlopen(
            f"https://export.arxiv.org/api/query?{params}", timeout=15, context=CTX
        ) as r:
            xml = r.read().decode()
    except Exception:
        return []
    entries = []
    for entry in re.finditer(r"<entry>(.*?)</entry>", xml, re.DOTALL):
        body = entry.group(1)
        def tag(t: str) -> str:
            m = re.search(rf"<{t}[^>]*>(.*?)</{t}>", body, re.DOTALL)
            return m.group(1).strip() if m else ""
        entries.append({
            "arxiv_id": tag("id").split("/abs/")[-1].strip(),
            "title": tag("title").replace("\n", " "),
            "abstract": tag("summary")[:300].replace("\n", " "),
            "published": tag("published")[:10],
        })
    return entries


# ─── Discovery tasks (run every 30 min) ───────────────────────────────────────

def discover_new_models() -> dict:
    """Find recently released models we should add to model_spec.py."""
    papers = arxiv_search("large language model release benchmark 2026", n=8)
    papers_text = "\n".join(
        f"[{p['arxiv_id']}] ({p['published']}) {p['title']}: {p['abstract'][:150]}"
        for p in papers
    )

    out = m3(f"""Find new AI models released in the last 2 weeks (as of June 2026) that we should track.

Focus on: coding models, agentic models, models available via API or open-weight.

RECENT ARXIV PAPERS:
{papers_text}

MODELS WE ALREADY TRACK:
- MiniMax M3 (tokenrouter) — frontier coding, 1M ctx, free until June 17
- Claude Sonnet 4.6 / Opus 4.8 / Haiku 4.5 (anthropic)
- DeepSeek V4 Pro (tokenrouter)
- GPT-5.5 (openai)
- Gemini 3.1 Pro (google)

Output JSON: new models we should add to our registry.
[{{
  "name": "ModelName",
  "provider": "who makes it",
  "api_available": true,
  "best_for": ["coding", "reasoning"],
  "why_interesting": "specific capability or benchmark",
  "how_to_access": "API endpoint or CLI"
}}]
ONLY JSON array. If nothing new, output [].""")

    if out and out.strip() != "[]":
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        report = DISCOVERY_REPORTS / f"new_models_{ts}.json"
        report.write_text(out)
        log("discover", f"new models report: {report.name}")
    return {"task": "new_models", "found": len(out) > 10 if out else False}


def discover_agent_frameworks() -> dict:
    """Find new agent frameworks, tools, benchmarks released recently."""
    papers = arxiv_search("agent framework evaluation tool use LLM 2026", n=6)
    papers_text = "\n".join(
        f"[{p['arxiv_id']}] ({p['published']}) {p['title']}: {p['abstract'][:150]}"
        for p in papers
    )

    out = m3(f"""Find new agent frameworks, eval tools, or coding tools released in the last month (June 2026).

FRAMEWORKS WE KNOW ABOUT:
- DSPy: automated prompt optimization, LM-agnostic
- PromptFoo: prompt evaluation + A/B testing across models
- LangGraph: stateful agent graphs
- Cognee: knowledge graph memory
- CocoIndex: incremental code indexing
- OpenCode: open-source coding agent (MiniMax Code is based on this)
- Atropos: RL environment for LLMs
- Hermes: personal agent with skill creation + trajectory logging

RECENT PAPERS:
{papers_text}

What's new that we should evaluate? Output JSON:
[{{
  "name": "FrameworkName",
  "category": "eval|memory|agent|coding|benchmark",
  "what_it_does": "...",
  "why_relevant": "specific gap it fills in our stack",
  "try_with": "pip install X or brew install X",
  "priority": "high|medium|low"
}}]
ONLY JSON. If nothing new, output [].""")

    if out and out.strip() != "[]":
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        report = DISCOVERY_REPORTS / f"new_frameworks_{ts}.json"
        report.write_text(out)
        log("discover", f"frameworks report: {report.name}")
    return {"task": "frameworks", "found": len(out) > 10 if out else False}


def discover_prompt_techniques() -> dict:
    """Find new prompting techniques (beyond CoT, ToT, etc.)."""
    papers = arxiv_search("chain of thought prompting LLM technique 2026 new", n=6)
    papers_text = "\n".join(
        f"[{p['arxiv_id']}] ({p['published']}) {p['title']}: {p['abstract'][:200]}"
        for p in papers
    )

    out = m3(f"""Find prompting techniques we should add to our M3 pipeline.

TECHNIQUES WE ALREADY USE:
- Stable preamble first (signature+tests before variable content) → KV cache hits
- max_tokens=65536 always → prevents M3 empty output
- Decompose → implement → validate (tower of babylon)
- 3-gate review (critic → verifier → judge)
- Structured output (JSON arrays, ```lang:path blocks)

RECENT PAPERS ON PROMPTING:
{papers_text}

What new techniques from research or practice should we adopt? Output JSON:
[{{
  "technique": "name",
  "how_it_works": "...",
  "when_to_use": "...",
  "expected_gain": "...",
  "implementation": "how to add to m3_pipeline.py in < 10 lines"
}}]
ONLY JSON. If nothing new, [].""")

    if out and out.strip() != "[]":
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        report = DISCOVERY_REPORTS / f"prompt_techniques_{ts}.json"
        report.write_text(out)
        log("discover", f"techniques report: {report.name}")
    return {"task": "techniques", "found": len(out) > 10 if out else False}


def discover_minimax_updates() -> dict:
    """Check for MiniMax-specific updates: MaxProof, new API features, etc."""
    # Known: M3 blog (June 1), MaxProof blog (recently posted)
    papers = arxiv_search("MiniMax language model 2026", n=4)

    out = m3(f"""Synthesize what we know about MiniMax's latest updates as of June 2026.

KNOWN UPDATES:
1. M3 blog (2026-06-01): SWE-Bench-Pro=59%, 1M context, MSA architecture, thinking toggle,
   priority tier, native multimodal, MiniMax Code built on OpenCode+Pi
2. MaxProof blog: math proof evolution (URL: minimax.io/blog/minimax-maxproof-math-proof-evolution)
   - Likely: RL + formal proof verifier (Lean/Coq) for evolving math proofs
   - M3 is strong at IMO 2025 + USAMO 2026 (mentioned in eval methodology)

RELEVANT ARXIV:
{chr(10).join(f"[{p['arxiv_id']}] {p['title']}" for p in papers)}

QUESTIONS:
1. What does MaxProof mean for our tensor-logic repo? Can we apply similar RL+verifier?
2. Any M3 API updates not in the June 1 blog? (e.g. function calling, streaming updates)
3. How does M3's IMO 2025 performance affect how we should use it for math-heavy tasks?

Output JSON:
{{
  "maxproof_for_tensor_logic": "specific idea",
  "api_updates_to_check": ["..."],
  "math_task_guidance": "when to use M3 for reasoning vs other models",
  "action_items": ["concrete thing to try this week"]
}}""")

    if out:
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        report = DISCOVERY_REPORTS / f"minimax_updates_{ts}.json"
        report.write_text(out)
        log("discover", f"minimax updates: {report.name}")
    return {"task": "minimax_updates", "found": bool(out)}


DISCOVERY_TASKS = [
    discover_new_models,
    discover_agent_frameworks,
    discover_prompt_techniques,
    discover_minimax_updates,
]


def discovery_loop() -> None:
    """Runs discovery tasks every 30 minutes until deadline."""
    import concurrent.futures
    run = 0
    while datetime.now() < DEADLINE:
        run += 1
        log("discovery", f"run #{run} starting ({len(DISCOVERY_TASKS)} tasks)")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(fn) for fn in DISCOVERY_TASKS]
            for fut in concurrent.futures.as_completed(futs):
                try:
                    r = fut.result()
                    log("discovery", f"task={r['task']} found={r['found']}")
                except Exception as e:
                    log("discovery", f"error: {e}")

        log("discovery", f"run #{run} done. Sleeping 30 min.")
        # Sleep in small chunks so we check deadline
        for _ in range(30 * 60 // 10):
            if datetime.now() >= DEADLINE:
                break
            time.sleep(10)

    log("discovery", "Deadline reached — stopping discovery loop")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    log("supervisor", f"Starting. Deadline: {DEADLINE}")
    log("supervisor", f"Managing {len(WORKERS)} worker scripts")
    log("supervisor", "Check interval: 60s | Discovery interval: 30min")
    log("supervisor", f"Discovery reports: {DISCOVERY_REPORTS}")

    # Run supervision + discovery in parallel threads
    threads = [
        threading.Thread(target=supervise_workers, daemon=False, name="supervision"),
        threading.Thread(target=discovery_loop, daemon=False, name="discovery"),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    log("supervisor", "All threads complete. Exiting.")


if __name__ == "__main__":
    main()
