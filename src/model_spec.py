"""
Model capability registry + deterministic router.

What each model is good at, optimal call params, quirks from actual testing.
Router is pure Python — no LLM in the selection path.

Sources:
  - MiniMax M3 blog (2026-06-01): benchmarks, thinking toggle, MSA architecture
  - Anthropic model cards
  - Our own testing: m3_forever.py, m3lab 992 missions
  - TokenRouter docs

Usage:
  spec = REGISTRY["tokenrouter/MiniMax-M3"]
  params = spec.call_params()        # API kwargs, already correct
  model = select("coding", "free")   # deterministic routing
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelSpec:
    id: str                      # canonical ID e.g. "tokenrouter/MiniMax-M3"
    provider: str                # "tokenrouter" | "anthropic" | "openai" | "local"
    api_model_name: str          # the model name string for the API call
    context_window: int          # tokens
    cost_tier: str               # "free" | "cheap" | "medium" | "expensive"

    strengths: list[str]         # ordered: most important first
    weaknesses: list[str]
    best_for: list[str]          # task type strings
    avoid_for: list[str]

    benchmarks: dict[str, float] # {"SWE-Bench-Pro": 0.59, ...}

    # Quirks: non-obvious call requirements that cause silent failures without them
    quirks: dict[str, Any] = field(default_factory=dict)

    def call_params(self, task_type: str = "general") -> dict:
        """
        Returns the correct API params for this model.
        Deterministic: task_type only adjusts max_tokens, not model selection.
        """
        base = {
            "model": self.api_model_name,
            "max_tokens": self.quirks.get("required_max_tokens", 4096),
        }
        # M3 thinking: off for fast tasks, on for complex reasoning
        if self.quirks.get("thinking_toggle") and task_type in ("classify", "extract", "format"):
            base["thinking"] = {"type": "disabled"}
        return base

    def strip_response(self, raw: str) -> str:
        """Strip model-specific artifacts from raw API response."""
        if self.quirks.get("strip_think_block") and "</think>" in raw:
            return raw.split("</think>", 1)[1].strip()
        return raw.strip()


# ─── Registry ─────────────────────────────────────────────────────────────────

REGISTRY: dict[str, ModelSpec] = {

    "tokenrouter/MiniMax-M3": ModelSpec(
        id="tokenrouter/MiniMax-M3",
        provider="tokenrouter",
        api_model_name="MiniMax-M3",
        context_window=1_000_000,
        cost_tier="free",  # until 2026-06-17, then paid
        strengths=[
            "long-horizon agentic tasks (doesn't give up, tested 147 submissions on one task)",
            "coding: SWE-Bench Pro 59%, Terminal-Bench 66%, MCP Atlas 74.2%",
            "1M context — full repo + logs + paper in one window",
            "native multimodal — image/video input without adapter",
            "CUDA kernel / systems programming",
            "paper reproduction (ran 12h, 18 commits autonomously)",
        ],
        weaknesses=[
            "empty output if max_tokens < ~32k (thinking eats budget, outputs nothing after </think>)",
            "slower than Claude for simple extraction tasks",
            "thinking block must be stripped from response manually",
            "free tier ends 2026-06-17",
        ],
        best_for=["coding", "agentic", "long-horizon", "multimodal", "systems", "research"],
        avoid_for=["simple-classify", "latency-sensitive", "short-qa"],
        benchmarks={
            "SWE-Bench-Pro": 0.590,
            "Terminal-Bench-2.1": 0.660,
            "SWE-fficiency": 0.348,
            "KernelBench-Hard": 0.288,
            "MCP-Atlas": 0.742,
            "PostTrainBench": 0.37,
        },
        quirks={
            "required_max_tokens": 65536,  # CRITICAL: < this causes empty output
            "strip_think_block": True,      # response starts with <think>...</think>
            "thinking_toggle": True,        # can pass thinking={"type":"disabled"} for speed
            "timeout_seconds": 600,         # long thinking needs long timeout
            "finish_reason_length_means_empty": True,  # finish=length → empty after think block
            "priority_tier": "service_tier=priority",  # for stable latency (contact sales)
            "free_tier_deadline": "2026-06-17",
        },
    ),

    "tokenrouter/deepseek-v4-pro": ModelSpec(
        id="tokenrouter/deepseek-v4-pro",
        provider="tokenrouter",
        api_model_name="deepseek/deepseek-v4-pro",
        context_window=128_000,
        cost_tier="cheap",
        strengths=[
            "strong coder, especially Python and data science",
            "MoE architecture — fast for coding tasks",
            "good at following structured output formats",
        ],
        weaknesses=[
            "weaker on agentic multi-step tasks vs M3",
            "no native multimodal",
            "context window 128k vs M3's 1M",
        ],
        best_for=["coding", "structured-output", "data-analysis"],
        avoid_for=["multimodal", "very-long-context"],
        benchmarks={},
        quirks={
            "required_max_tokens": 8192,
            "strip_think_block": True,  # also a thinking model
            "timeout_seconds": 120,
        },
    ),

    "anthropic/claude-sonnet-4-6": ModelSpec(
        id="anthropic/claude-sonnet-4-6",
        provider="anthropic",
        api_model_name="claude-sonnet-4-6",
        context_window=200_000,
        cost_tier="medium",
        strengths=[
            "best balance of speed + quality for most tasks",
            "strong at code review, explanation, refactoring",
            "reliable structured output (JSON, markdown)",
            "our current interactive session model",
        ],
        weaknesses=[
            "not free — burns quota on every call",
            "weaker than Opus on hard multi-step reasoning",
        ],
        best_for=["code-review", "explanation", "refactoring", "qa", "structured-output"],
        avoid_for=["bulk-parallelism"],  # costs add up fast
        benchmarks={
            "SWE-Bench-Verified": 0.727,  # from anthropic model card
        },
        quirks={
            "required_max_tokens": 8192,
            "timeout_seconds": 60,
            "use_messages_api": True,  # not completions
        },
    ),

    "anthropic/claude-opus-4-8": ModelSpec(
        id="anthropic/claude-opus-4-8",
        provider="anthropic",
        api_model_name="claude-opus-4-8",
        context_window=200_000,
        cost_tier="expensive",
        strengths=[
            "highest quality reasoning — best for architecture decisions",
            "complex multi-step planning",
            "PostTrainBench: 0.42 (highest across models)",
        ],
        weaknesses=[
            "expensive: ~5x Sonnet cost",
            "slower than Sonnet",
        ],
        best_for=["architecture", "complex-planning", "research-synthesis", "hard-debugging"],
        avoid_for=["bulk", "simple-tasks", "routine-coding"],
        benchmarks={
            "Terminal-Bench-2.1": 0.680,
            "PostTrainBench": 0.42,
        },
        quirks={
            "required_max_tokens": 16384,
            "timeout_seconds": 120,
            "use_messages_api": True,
            "extended_thinking": True,  # supports budget_tokens param
        },
    ),

    "anthropic/claude-haiku-4-5": ModelSpec(
        id="anthropic/claude-haiku-4-5",
        provider="anthropic",
        api_model_name="claude-haiku-4-5-20251001",
        context_window=200_000,
        cost_tier="cheap",
        strengths=[
            "fastest Claude — sub-second latency for short prompts",
            "cheapest — good for high-volume classification",
            "reliable at extraction, formatting, routing decisions",
        ],
        weaknesses=[
            "not for complex reasoning or multi-step agentic",
            "misses nuance on ambiguous tasks",
        ],
        best_for=["classify", "extract", "format", "simple-qa", "routing"],
        avoid_for=["complex-coding", "research", "multi-step-agentic"],
        benchmarks={},
        quirks={
            "required_max_tokens": 2048,
            "timeout_seconds": 30,
            "use_messages_api": True,
        },
    ),

    "local/pi": ModelSpec(
        id="local/pi",
        provider="local",
        api_model_name="pi",  # CLI binary
        context_window=200_000,
        cost_tier="free",  # uses whichever provider key pi is configured with
        strengths=[
            "provider-agnostic: routes to M3, Claude, Gemini, etc. via pi config",
            "local — no network overhead for context setup",
            "integrates with skills/ and hooks/",
        ],
        weaknesses=[
            "adds ~200ms CLI overhead vs direct API",
            "output parsing needs additional stripping",
        ],
        best_for=["interactive", "skill-execution", "provider-agnostic"],
        avoid_for=["bulk-parallel"],  # CLI subprocess overhead at scale
        benchmarks={},
        quirks={
            "invoke_via": "subprocess",
            "binary": "pi",
            "timeout_seconds": 300,
        },
    ),

    "openai/codex": ModelSpec(
        id="openai/codex",
        provider="openai",
        api_model_name="codex",  # CLI binary, uses o4-mini or o3
        context_window=200_000,
        cost_tier="medium",
        strengths=[
            "best CLI agent for repo-aware coding tasks",
            "built-in file editing, git, shell execution",
            "AGENTS.md / CODEX_WORKPAD.md integration",
            "async task execution with worktrees",
        ],
        weaknesses=[
            "requires openai API key",
            "slower for single-function tasks vs direct M3 call",
        ],
        best_for=["repo-wide-refactor", "multi-file-impl", "git-aware-coding"],
        avoid_for=["single-function", "research", "multimodal"],
        benchmarks={},
        quirks={
            "invoke_via": "subprocess",
            "binary": "codex",
            "use_worktrees": True,
            "supports_async": True,
        },
    ),
}


# ─── Deterministic router ─────────────────────────────────────────────────────

# Task type → ordered list of model IDs (best → fallback)
_ROUTING_TABLE: dict[str, list[str]] = {
    "coding":           ["tokenrouter/MiniMax-M3", "tokenrouter/deepseek-v4-pro",
                         "anthropic/claude-sonnet-4-6"],
    "agentic":          ["tokenrouter/MiniMax-M3", "anthropic/claude-opus-4-8"],
    "long-horizon":     ["tokenrouter/MiniMax-M3"],
    "code-review":      ["anthropic/claude-sonnet-4-6", "tokenrouter/MiniMax-M3"],
    "classify":         ["anthropic/claude-haiku-4-5", "anthropic/claude-sonnet-4-6"],
    "extract":          ["anthropic/claude-haiku-4-5", "anthropic/claude-sonnet-4-6"],
    "research":         ["tokenrouter/MiniMax-M3", "anthropic/claude-opus-4-8"],
    "multimodal":       ["tokenrouter/MiniMax-M3"],
    "architecture":     ["anthropic/claude-opus-4-8", "anthropic/claude-sonnet-4-6"],
    "systems":          ["tokenrouter/MiniMax-M3"],
    "simple-qa":        ["anthropic/claude-haiku-4-5"],
    "repo-wide-refactor": ["openai/codex", "tokenrouter/MiniMax-M3"],
    "general":          ["tokenrouter/MiniMax-M3", "anthropic/claude-sonnet-4-6"],
}

_BUDGET_TIERS = {"free": {"free"}, "cheap": {"free", "cheap"}, "any": {"free", "cheap", "medium", "expensive"}}


def select(task_type: str, budget: str = "any") -> ModelSpec:
    """
    Deterministic model selection. No LLM. Returns first model in routing
    table that matches task_type and is within budget.

    Args:
        task_type: one of the keys in _ROUTING_TABLE
        budget: "free" | "cheap" | "any"

    Returns:
        ModelSpec of selected model

    Raises:
        ValueError: if no model available for task + budget
    """
    allowed_tiers = _BUDGET_TIERS.get(budget, _BUDGET_TIERS["any"])
    candidates = _ROUTING_TABLE.get(task_type, _ROUTING_TABLE["general"])
    for model_id in candidates:
        spec = REGISTRY.get(model_id)
        if spec and spec.cost_tier in allowed_tiers:
            return spec
    raise ValueError(f"No model for task={task_type!r} budget={budget!r}")


def select_id(task_type: str, budget: str = "any") -> str:
    """Like select() but returns the model ID string."""
    return select(task_type, budget).id


def describe(model_id: str) -> str:
    """One-paragraph human-readable description for a model."""
    spec = REGISTRY.get(model_id)
    if not spec:
        return f"Unknown model: {model_id}"
    bench_str = ", ".join(f"{k}={v:.0%}" for k, v in spec.benchmarks.items()) or "none recorded"
    return (
        f"{spec.id} ({spec.cost_tier}, {spec.context_window//1000}k ctx)\n"
        f"  Best for: {', '.join(spec.best_for[:4])}\n"
        f"  Avoid for: {', '.join(spec.avoid_for[:3])}\n"
        f"  Benchmarks: {bench_str}\n"
        f"  Quirks: {', '.join(str(k) for k in spec.quirks)}"
    )


def routing_table_str() -> str:
    """Print the full routing table for debugging."""
    lines = ["TASK TYPE → MODEL (TIER)"]
    for task, models in _ROUTING_TABLE.items():
        picks = [f"{m} ({REGISTRY[m].cost_tier})" for m in models if m in REGISTRY]
        lines.append(f"  {task:<25} → {picks[0] if picks else 'none'}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(routing_table_str())
    print()
    for model_id in list(REGISTRY)[:3]:
        print(describe(model_id))
        print()
