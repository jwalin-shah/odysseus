"""
fusion.py — Native multi-model panel synthesis, OpenRouter Fusion-style.

Architecture (reverse-engineered from OpenRouter's blog post):
  1. Dispatch same prompt to N panel models in parallel
  2. Judge model reads all responses → structured analysis
     (consensus / contradictions / partial coverage / unique insights / blind spots)
  3. Synthesizer writes final answer grounded in that analysis

Cost model:
  - Budget panel: MiniMax M3 (TokenRouter free) + DeepSeek V4 Pro + free OpenRouter model
  - Judge/synth: Claude A (tier-0 subscription, zero marginal cost)
  - Pioneer only for scarce/critical tasks

Usage:
  from src.fusion import fuse, budget_panel, frontier_panel

  result = await fuse("What is the best approach to X?", panel=budget_panel())
  result = fuse_sync("Explain Y", panel=budget_panel())
"""
from __future__ import annotations

import asyncio
import json
import os
import ssl
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import Optional

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

# ── Judge prompt ──────────────────────────────────────────────────────────────
# This is the core IP of Fusion. The judge produces structured analysis that
# the synthesizer uses to write a better answer than any single model could.

_JUDGE_SYSTEM = """\
You are a synthesis judge. Multiple AI models answered the same question.
Your job is to produce structured analysis that a final synthesizer will use.
Be precise and evidence-grounded. Do not write the final answer yourself.\
"""

_JUDGE_TEMPLATE = """\
ORIGINAL QUESTION:
{prompt}

PANEL RESPONSES ({n} models):
{responses}

Produce a JSON object with exactly these keys:
{{
  "consensus": ["claims all/most models agree on — cite which"],
  "contradictions": ["where models disagree, what each said, and your judgment on who is right"],
  "partial_coverage": ["important points only 1-2 models covered but should be in the answer"],
  "unique_insights": ["strong points from individual models the others missed entirely"],
  "blind_spots": ["aspects of the question none of the models addressed adequately"],
  "quality_ranking": ["model IDs ranked best to worst with one-line reason each"]
}}

Return only valid JSON, no prose before or after.\
"""

_SYNTH_SYSTEM = """\
You are a synthesis writer. You receive structured panel analysis and write
the best possible final answer. Ground every claim in consensus or strong unique
insights. Resolve contradictions by reasoning from first principles.
Cover blind spots. Be comprehensive but not verbose.\
"""

_SYNTH_TEMPLATE = """\
ORIGINAL QUESTION:
{prompt}

PANEL ANALYSIS:
{analysis}

Write the final answer now. Use the consensus as your foundation, incorporate
the best unique insights, cover the blind spots, and resolve contradictions.\
"""


# ── Panel model config ────────────────────────────────────────────────────────

@dataclass
class PanelModel:
    id: str                          # human label for judge output
    base_url: str
    model: str
    api_key_env: str                 # env var name for the key
    max_tokens: int = 4096
    timeout: int = 120
    opencode_provider: Optional[str] = None  # fallback: read from opencode.json


def _resolve_key(model: PanelModel) -> str:
    key = os.environ.get(model.api_key_env, "").strip()
    if key:
        return key
    if model.opencode_provider:
        cfg_path = os.path.expanduser("~/.config/opencode/opencode.json")
        try:
            cfg = json.load(open(cfg_path))
            key = cfg["provider"][model.opencode_provider]["options"]["apiKey"]
            if key:
                return key
        except Exception:
            pass
    raise RuntimeError(
        f"No API key for panel model {model.id!r}. "
        f"Set {model.api_key_env} or configure {model.opencode_provider!r} in opencode.json"
    )


# ── Standard panels ───────────────────────────────────────────────────────────

def budget_panel() -> list[PanelModel]:
    """Near-zero cost panel. Mirrors OpenRouter's budget panel (64.7% DRACO).
    MiniMax M3 + DeepSeek V4 Pro via TokenRouter + free OpenRouter model.
    NOTE: TokenRouter M3 free tier ends June 17 — swap to another free model after."""
    return [
        PanelModel(
            id="minimax-m3",
            base_url="https://api.tokenrouter.com/v1",
            model="MiniMax-M3",
            api_key_env="TOKENROUTER_API_KEY",
            opencode_provider="tokenrouter",
        ),
        PanelModel(
            id="deepseek-v4-pro",
            base_url="https://api.tokenrouter.com/v1",
            model="deepseek/deepseek-v4-pro",
            api_key_env="TOKENROUTER_API_KEY",
            opencode_provider="tokenrouter",
        ),
        PanelModel(
            id="nex-n2-pro",
            base_url="https://openrouter.ai/api/v1",
            model="nex-agi/nex-n2-pro",
            api_key_env="OPENROUTER_API_KEY",
            opencode_provider="openrouter",
        ),
    ]


def frontier_panel() -> list[PanelModel]:
    """Subscription-backed panel. Uses Claude A + DeepSeek + Gemini.
    Tier 0 where possible — zero marginal cost on existing subscriptions."""
    return [
        PanelModel(
            id="deepseek-v4-pro",
            base_url="https://api.tokenrouter.com/v1",
            model="deepseek/deepseek-v4-pro",
            api_key_env="TOKENROUTER_API_KEY",
            opencode_provider="tokenrouter",
        ),
        PanelModel(
            id="minimax-m3",
            base_url="https://api.tokenrouter.com/v1",
            model="MiniMax-M3",
            api_key_env="TOKENROUTER_API_KEY",
            opencode_provider="tokenrouter",
        ),
        PanelModel(
            id="nex-n2-pro",
            base_url="https://openrouter.ai/api/v1",
            model="nex-agi/nex-n2-pro",
            api_key_env="OPENROUTER_API_KEY",
            opencode_provider="openrouter",
        ),
    ]


# ── Core dispatch ─────────────────────────────────────────────────────────────

def _call_one(model: PanelModel, prompt: str, system: Optional[str] = None) -> str:
    """Synchronous single-model call (run in thread executor for parallelism)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    data = json.dumps({
        "model": model.model,
        "messages": messages,
        "max_tokens": model.max_tokens,
    }).encode()

    headers = {
        "Authorization": f"Bearer {_resolve_key(model)}",
        "Content-Type": "application/json",
    }
    if "openrouter.ai" in model.base_url:
        headers["HTTP-Referer"] = "https://github.com/pewdiepie-archdaemon/odysseus"
        headers["X-Title"] = "Odysseus"

    req = urllib.request.Request(
        f"{model.base_url.rstrip('/')}/chat/completions",
        data=data,
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=model.timeout, context=_SSL_CTX) as r:
        body = json.load(r)
    return body["choices"][0]["message"]["content"]


async def _call_one_async(model: PanelModel, prompt: str, system: Optional[str] = None) -> tuple[str, str]:
    """Returns (model_id, response). Errors produce an error string, not exceptions."""
    loop = asyncio.get_event_loop()
    try:
        text = await loop.run_in_executor(None, lambda: _call_one(model, prompt, system))
        return model.id, text
    except Exception as e:
        return model.id, f"[ERROR from {model.id}: {e}]"


def _judge_via_m3(prompt: str, panel_responses: list[tuple[str, str]]) -> str:
    """Use MiniMax M3 (free) as judge — produces the structured analysis JSON."""
    from src.m3 import complete as m3_complete  # lazy import avoids circular

    responses_block = "\n\n".join(
        f"--- Model: {mid} ---\n{resp}"
        for mid, resp in panel_responses
    )
    judge_prompt = _JUDGE_TEMPLATE.format(
        prompt=prompt,
        n=len(panel_responses),
        responses=responses_block,
    )
    raw = m3_complete(judge_prompt, system=_JUDGE_SYSTEM, max_tokens=4096, timeout=120)
    # Strip markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def _synthesize_via_subprocess(prompt: str, analysis: str, backend: str = "ca") -> str:
    """Use Claude A (or other backend) via subprocess --print for final synthesis.
    Falls back to M3 if subprocess fails."""
    synth_prompt = _SYNTH_TEMPLATE.format(prompt=prompt, analysis=analysis)
    try:
        result = subprocess.run(
            [backend, "--print", synth_prompt],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    # Fallback: M3 synthesizes (lower quality but free)
    from src.m3 import complete as m3_complete
    return m3_complete(synth_prompt, system=_SYNTH_SYSTEM, max_tokens=8192, timeout=180)


# ── Public API ────────────────────────────────────────────────────────────────

async def fuse(
    prompt: str,
    panel: Optional[list[PanelModel]] = None,
    judge_backend: str = "m3",      # "m3" = free MiniMax, "ca" = Claude A
    synth_backend: str = "ca",      # "ca" = Claude A subscription, "pioneer" = scarce
    return_analysis: bool = False,
) -> str | dict:
    """
    Full async fusion pipeline.

    Args:
        prompt:          The question/task to fuse over.
        panel:           List of PanelModel configs. Defaults to budget_panel().
        judge_backend:   Which backend runs the structured analysis step.
        synth_backend:   Which backend writes the final answer. "ca" = Claude A (free).
        return_analysis: If True, return dict with panel_responses, analysis, answer.

    Returns:
        Final synthesized answer string, or full dict if return_analysis=True.
    """
    if panel is None:
        panel = budget_panel()

    # Step 1: dispatch panel in parallel
    tasks = [_call_one_async(m, prompt) for m in panel]
    panel_responses: list[tuple[str, str]] = await asyncio.gather(*tasks)

    # Step 2: judge produces structured analysis
    analysis_json = _judge_via_m3(prompt, list(panel_responses))

    # Step 3: synthesize final answer
    if synth_backend == "m3":
        from src.m3 import complete as m3_complete
        synth_prompt = _SYNTH_TEMPLATE.format(prompt=prompt, analysis=analysis_json)
        answer = m3_complete(synth_prompt, system=_SYNTH_SYSTEM, max_tokens=8192, timeout=180)
    else:
        answer = _synthesize_via_subprocess(prompt, analysis_json, backend=synth_backend)

    if return_analysis:
        return {
            "panel_responses": dict(panel_responses),
            "analysis": analysis_json,
            "answer": answer,
        }
    return answer


def fuse_sync(
    prompt: str,
    panel: Optional[list[PanelModel]] = None,
    judge_backend: str = "m3",
    synth_backend: str = "ca",
    return_analysis: bool = False,
) -> str | dict:
    """Synchronous wrapper for fuse(). Use in non-async contexts."""
    return asyncio.run(fuse(
        prompt, panel=panel,
        judge_backend=judge_backend,
        synth_backend=synth_backend,
        return_analysis=return_analysis,
    ))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main(argv=None):
    import argparse
    import sys

    p = argparse.ArgumentParser(prog="fusion", description=__doc__.splitlines()[1].strip())
    p.add_argument("prompt", help="Question or task to fuse over")
    p.add_argument("--panel", choices=["budget", "frontier"], default="budget")
    p.add_argument("--synth", choices=["ca", "cb", "pioneer", "m3"], default="ca",
                   help="Backend for final synthesis (default: ca = Claude A subscription)")
    p.add_argument("--show-analysis", action="store_true",
                   help="Print structured judge analysis before final answer")
    args = p.parse_args(argv)

    stdin_ctx = ""
    if not sys.stdin.isatty():
        stdin_ctx = sys.stdin.read().strip()
    full_prompt = f"{args.prompt}\n\nContext:\n{stdin_ctx}" if stdin_ctx else args.prompt

    panel = budget_panel() if args.panel == "budget" else frontier_panel()
    result = fuse_sync(full_prompt, panel=panel, synth_backend=args.synth, return_analysis=args.show_analysis)

    if args.show_analysis and isinstance(result, dict):
        print("=== PANEL RESPONSES ===")
        for mid, resp in result["panel_responses"].items():
            print(f"\n--- {mid} ---\n{resp[:500]}...")
        print("\n=== JUDGE ANALYSIS ===")
        print(result["analysis"])
        print("\n=== FINAL ANSWER ===")
        print(result["answer"])
    else:
        print(result if isinstance(result, str) else result["answer"])


if __name__ == "__main__":
    main()
