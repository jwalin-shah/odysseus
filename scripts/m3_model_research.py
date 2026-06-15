#!/usr/bin/env python3
"""
M3 model research loop — mines benchmarks, nuances, and optimal call patterns.

M3 researches models, we write findings to src/model_spec.py updates.
Runs continuously until June 17 deadline.

Lanes:
  1. Benchmark miner: find latest evals for each model across public leaderboards
  2. Quirk miner: find non-obvious call patterns (API params, failures, workarounds)
  3. CLI agent comparison: Codex vs Pi vs MiniMax Code vs Claude Code — when to use what
  4. Paper miner (arXiv): find model architecture + training papers
  5. Router synthesizer: given all findings, improve model_spec.py routing table

Usage: nohup python3 scripts/m3_model_research.py >> /tmp/m3_model_research.log 2>&1 &
"""
import ast
import json
import os
import re
import ssl
import subprocess
import threading
import time
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

KEY = os.environ.get("TOKENROUTER_API_KEY", "sk-umkgY44a1AeYkZa2ZCZFpPwnGY4ZeedbFByHfm8eZcfRKXZJ")
ROOT = Path(__file__).parent.parent
REPORTS = ROOT / "reports" / "model_research"
REPORTS.mkdir(parents=True, exist_ok=True)
DEADLINE = datetime(2026, 6, 17, 23, 59)
LOCK = threading.Lock()


def log(name: str, msg: str) -> None:
    with LOCK:
        print(f"[{datetime.now().strftime('%H:%M:%S')}][{name}] {msg}", flush=True)


def m3(prompt: str, system: str | None = None) -> str:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    payload = json.dumps({"model": "MiniMax-M3", "messages": msgs, "max_tokens": 65536}).encode()
    try:
        req = urllib.request.Request(
            "https://api.tokenrouter.com/v1/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=600, context=CTX) as r:
            body = json.load(r)
        raw = body["choices"][0]["message"]["content"]
        finish = body["choices"][0].get("finish_reason", "?")
        toks = body.get("usage", {}).get("total_tokens", "?")
        out = raw.split("</think>", 1)[1].strip() if "</think>" in raw else raw.strip()
        log("m3", f"finish={finish} tok={toks} out={len(out)}c")
        return out
    except Exception as e:
        log("m3", f"error: {e}")
        return ""


def arxiv_search(query: str, n: int = 8) -> list[dict]:
    params = urllib.parse.urlencode({"search_query": f"all:{query}", "start": 0, "max_results": n})
    try:
        with urllib.request.urlopen(
            f"https://export.arxiv.org/api/query?{params}", timeout=15, context=CTX
        ) as r:
            xml = r.read().decode()
    except Exception as e:
        log("arxiv", f"error: {e}")
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
            "abstract": tag("summary")[:400].replace("\n", " "),
            "published": tag("published")[:10],
        })
    return entries


def save_report(name: str, content: str | dict) -> Path:
    path = REPORTS / f"{name}.json"
    if isinstance(content, str):
        path.write_text(content)
    else:
        path.write_text(json.dumps(content, indent=2))
    log("save", f"{path.name} ({path.stat().st_size} bytes)")
    return path


# ─── Research tasks ───────────────────────────────────────────────────────────

def research_model_benchmarks() -> dict:
    """M3 synthesizes current benchmark landscape for LLM coding models."""
    log("benchmarks", "start")
    papers = arxiv_search("LLM coding benchmark SWE-bench agent evaluation 2025 2026", n=8)
    papers_text = "\n".join(
        f"[{p['arxiv_id']}] ({p['published']}) {p['title']}\n  {p['abstract'][:200]}"
        for p in papers
    )

    out = m3(f"""You are a model capability researcher. Synthesize the latest benchmark data.

KNOWN BENCHMARKS FROM M3 BLOG (2026-06-01):
- MiniMax M3: SWE-Bench-Pro=59%, Terminal-Bench=66%, MCP-Atlas=74.2%, KernelBench-Hard=28.8%
- Claude Opus 4.7: PostTrainBench=0.42, Terminal-Bench ranking unclear
- GPT-5.5: PostTrainBench=0.39
- Gemini 3.1 Pro: competitive on multimodal

RECENT ARXIV PAPERS:
{papers_text}

TASK: For each model below, give the best-known benchmark scores and what task type they excel at.
Models: MiniMax-M3, Claude-Sonnet-4-6, Claude-Opus-4-8, DeepSeek-V4-Pro, GPT-5.5, Gemini-3.1-Pro

Output JSON:
{{
  "as_of": "2026-06-15",
  "models": {{
    "MiniMax-M3": {{
      "benchmarks": {{"SWE-Bench-Pro": 0.59, "...": 0.0}},
      "best_at": ["coding", "long-horizon-agentic"],
      "notes": "non-obvious findings"
    }}
  }},
  "routing_recommendations": [
    {{"task": "long-horizon agentic", "pick": "MiniMax-M3", "reason": "..."}}
  ]
}}
ONLY JSON.""",
    "You are a benchmark researcher. Output only JSON, no prose.",
    )
    if out:
        save_report("benchmark_synthesis", out)
    return {"name": "benchmarks", "status": "ok" if out else "empty"}


def research_m3_quirks() -> dict:
    """Mine non-obvious M3 quirks from the blog post and synthesize call patterns."""
    log("m3-quirks", "start")

    # Key facts from the blog post that affect API calls
    known_facts = """
FROM M3 BLOG (2026-06-01):
1. Thinking can be toggled on/off. Off = faster, for latency-sensitive tasks like conversation/completion.
2. Priority tier (service_tier=priority): stable latency under high-concurrency. Enable via sales, opening to all soon.
3. Input ≤512K billed at standard rate. >512K billed at long-context rate.
4. finish_reason=length means thinking ate all tokens, output is empty after </think>. Fix: max_tokens=65536.
5. MSA architecture: 1M context, 1/20 compute at 1M tokens vs previous gen. 9x prefill speedup, 15x decode speedup.
6. Native multimodal: image+video input. No need for vision adapter.
7. MiniMax Code built on OpenCode + Pi. M3 is the execution model.
8. M3 does NOT stop early on hard tasks (tested: best solution was 145th submission, others stopped at 30).
    """

    out = m3(f"""Given these facts about MiniMax M3's API behavior, write a complete call guide.

{known_facts}

Output a JSON document covering:
1. Required API params for each use case (agentic, completion, multimodal, long-context)
2. What breaks silently (and how to detect it)
3. Cost optimization tips (when to use thinking=off, when long-context pricing kicks in)
4. How to integrate into a router (when to pick M3 vs cheaper model)
5. Key differences from calling Claude/GPT

Output JSON:
{{
  "model": "MiniMax-M3",
  "call_guides": {{
    "agentic_coding": {{"max_tokens": 65536, "thinking": "on", "timeout": 600, "gotchas": [...]}},
    "fast_completion": {{"max_tokens": 4096, "thinking": "off", "timeout": 30, "gotchas": [...]}},
    "long_context": {{"note": "...", "cost_tier_threshold": 524288, "gotchas": [...]}}
  }},
  "silent_failures": [{{"symptom": "...", "cause": "...", "fix": "..."}}],
  "cost_tips": ["..."],
  "vs_claude": {{"prefer_m3": "...", "prefer_claude": "..."}}
}}""",
    "Output only JSON. No prose.",
    )
    if out:
        save_report("m3_quirks", out)
    return {"name": "m3-quirks", "status": "ok" if out else "empty"}


def research_cli_agents() -> dict:
    """Compare coding CLI agents: when to use each."""
    log("cli-agents", "start")

    out = m3("""Compare these coding CLI agents. For each: best use case, worst use case, key quirk.

AGENTS:
1. Claude Code (ca/cb/cp): Anthropic's CLI. We use ca=AccountA, cb=AccountB, cp=Pioneer.
   - Hooks: PreToolUse, PostToolUse (tokenjuice, memjuice auto-inject)
   - Skills: ~/.claude/skills/ (symlinked from ~/.codex/skills/)
   - Spawns subagents via Agent tool
   - /code-review ultra = multi-agent PR review

2. Codex CLI (codex): OpenAI's CLI. Uses o4-mini or o3 via CODEX_MODEL env.
   - Async task execution with git worktrees
   - AGENTS.md + CODEX_WORKPAD.md workflow
   - Best for: multi-file repo-aware implementation

3. Pi CLI (pi): Model-agnostic. Routes to any provider.
   - Provider config in ~/.pi/
   - Skills from ~/.pi/skills/
   - Lower overhead than Claude Code for bulk tasks

4. MiniMax Code (agent.minimaxi.com): Built on OpenCode + Pi + M3
   - Agent Team: Producer + Verifier adversarial loop
   - Computer use (desktop control)
   - 1M context for full-repo tasks

5. Direct API (our m3_pipeline.py approach): raw urllib.request to TokenRouter
   - Maximum control, no CLI overhead
   - Best for: bulk parallel tasks, M3-specific features

For EACH agent output:
{{
  "agent": "name",
  "best_for": ["task1", "task2"],
  "avoid_for": ["task1"],
  "key_command": "how to invoke for a typical coding task",
  "key_quirk": "non-obvious thing that bites you",
  "pair_with": "what other tool to combine with"
}}

Output JSON array of all 5 agents.""",
    "Output only JSON array. No prose.",
    )
    if out:
        save_report("cli_agents", out)
    return {"name": "cli-agents", "status": "ok" if out else "empty"}


def research_arxiv_models() -> dict:
    """Search arXiv for model architecture + training papers relevant to our stack."""
    log("arxiv-models", "start")
    queries = [
        "MiniMax M3 MSA sparse attention 2026",
        "MiniMax thinking model architecture 2025",
        "LLM agent benchmark evaluation coding 2026",
        "sparse attention long context language model 2025 2026",
        "RLVR reinforcement learning LLM coding agent 2025",
    ]
    all_papers = []
    for q in queries:
        papers = arxiv_search(q, n=4)
        all_papers.extend(papers)
        time.sleep(1)  # arXiv rate limiting

    papers_text = "\n".join(
        f"[{p['arxiv_id']}] ({p['published']}) {p['title']}\n  {p['abstract'][:200]}"
        for p in all_papers[:20]
    )

    out = m3(f"""Synthesize these arXiv papers into actionable insights for our agent stack.

We use: MiniMax-M3 (TokenRouter), Claude Sonnet/Opus (Anthropic), local Pi CLI.
We're building: Odysseus personal AI harness, BTW temporal world-state, tensor-logic demos.

PAPERS:
{papers_text}

For each relevant paper, extract:
1. What it claims to improve
2. Technique we could adopt in our harness (concrete, not vague)
3. Whether it's been reproduced / if code is available

Output JSON:
{{
  "papers": [
    {{
      "arxiv_id": "...",
      "title": "...",
      "key_finding": "...",
      "adoptable_technique": "...",
      "code_available": true,
      "relevance": "high|medium|low"
    }}
  ],
  "top_3_to_adopt": ["arxiv_id1", "arxiv_id2", "arxiv_id3"]
}}""",
    "Output only JSON. No prose.",
    )
    if out:
        save_report("arxiv_model_research", out)
        # Also save the raw paper list
        save_report("arxiv_papers_raw", {"papers": all_papers})
    return {"name": "arxiv-models", "status": "ok" if out else "empty", "papers_found": len(all_papers)}


def research_routing_improvements() -> dict:
    """
    Given all research findings, M3 proposes improvements to model_spec.py routing table.
    This is the synthesizer that reads all other reports and outputs concrete code changes.
    """
    log("routing", "start — waiting for other research to complete")
    time.sleep(120)  # wait for other lanes to write their reports

    existing_reports = []
    for report_file in REPORTS.glob("*.json"):
        try:
            content = report_file.read_text()[:2000]
            existing_reports.append(f"=== {report_file.name} ===\n{content}")
        except Exception:
            pass

    current_spec = (ROOT / "src/model_spec.py").read_text()[:3000]

    out = m3(f"""Based on model research findings, improve the routing table in model_spec.py.

CURRENT model_spec.py (truncated):
{current_spec}

RESEARCH FINDINGS:
{chr(10).join(existing_reports[:5])}

Output ONLY the updated _ROUTING_TABLE dict as a Python dict literal (no full file).
Only change routing if there's clear evidence a different model would be better.
Format:
```python:src/model_spec_routing_update.py
_ROUTING_TABLE = {{
  "coding": [...],
  ...
}}
# CHANGES: explain what changed and why
```""",
    "Output only Python code in the requested format. No prose.",
    )
    if out:
        # Save as a patch file, not directly to model_spec.py
        save_report("routing_update_suggestion", out)
        # Write the patch file so a human can review
        patch_path = ROOT / "src" / "model_spec_routing_update.py"
        import re
        for m_obj in re.finditer(r"```python:src/model_spec_routing_update\.py\n(.*?)```", out, re.DOTALL):
            patch_path.write_text(m_obj.group(1))
            log("routing", f"patch written to {patch_path.name}")
            break
    return {"name": "routing", "status": "ok" if out else "empty"}


def research_maxproof() -> dict:
    """
    Research MiniMax MaxProof — math proof evolution.
    Blog: https://www.minimax.io/blog/minimax-maxproof-math-proof-evolution
    Synthesize what this means for our tensor-logic and BTW reasoning systems.
    """
    log("maxproof", "start")
    # Also search arXiv for related work
    papers = arxiv_search("formal math proof language model evolution 2026", n=5)
    papers_text = "\n".join(f"[{p['arxiv_id']}] {p['title']}: {p['abstract'][:200]}" for p in papers)

    out = m3(f"""Research MiniMax MaxProof — a system for math proof evolution.

From the blog (https://www.minimax.io/blog/minimax-maxproof-math-proof-evolution):
This appears to be a system where MiniMax M3 evolves mathematical proofs, likely using:
- Formal proof systems (Lean, Coq, or similar)
- Iterative refinement / RL with proof verification as reward
- Connection to M3's strong reasoning capabilities

Related arXiv papers on formal math proof with LLMs:
{papers_text}

QUESTIONS TO ANSWER:
1. What is MaxProof's core technique (proof evolution = RL + formal verifier?)
2. How does it relate to our tensor-logic repo (Domingos tensor logic paper)?
3. Could we apply MaxProof-style training to tensor-logic inference?
4. What's the connection to BTW world-state reasoning (is there any)?

Output JSON:
{{
  "maxproof_technique": "...",
  "connection_to_tensor_logic": "...",
  "connection_to_btw": "...",
  "adoptable_for_odysseus": "...",
  "next_steps": ["step1", "step2"]
}}""",
    "Output only JSON. No prose.",
    )
    if out:
        save_report("maxproof_research", out)
    return {"name": "maxproof", "status": "ok" if out else "empty"}


# ─── Main ─────────────────────────────────────────────────────────────────────

TASKS = [
    research_model_benchmarks,
    research_m3_quirks,
    research_cli_agents,
    research_arxiv_models,
    research_maxproof,
    research_routing_improvements,  # runs last (waits 120s for others)
]


def main() -> None:
    log("main", f"Starting model research loop. {len(TASKS)} tasks. Deadline: {DEADLINE}")
    log("main", f"Reports → {REPORTS}")

    with ThreadPoolExecutor(max_workers=len(TASKS)) as ex:
        futures = {ex.submit(fn): fn.__name__ for fn in TASKS}
        for fut in as_completed(futures):
            fn_name = futures[fut]
            try:
                result = fut.result()
                log("main", f"{fn_name} → {result}")
            except Exception as e:
                log("main", f"{fn_name} EXCEPTION: {e}")

    log("main", f"All research complete. Reports at {REPORTS}")
    log("main", "Review reports/model_research/ and apply src/model_spec_routing_update.py if valid")


if __name__ == "__main__":
    main()
