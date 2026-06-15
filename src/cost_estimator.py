"""Cost estimation utilities for LLM API calls.

Provides per-token USD pricing for various language models so that the
estimated cost of a request can be computed from token counts.
"""

from __future__ import annotations

# Per-token USD pricing for supported language models.
# Keys are model identifiers; values map to per-token rates for input
# (prompt) and output (completion) tokens.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {
        "input_per_token": 0.000_000_15,
        "output_per_token": 0.000_000_60,
    },
    "gpt-4o": {
        "input_per_token": 0.000_002_50,
        "output_per_token": 0.000_010_00,
    },
    "claude-haiku": {
        "input_per_token": 0.000_000_80,
        "output_per_token": 0.000_004_00,
    },
    "claude-sonnet": {
        "input_per_token": 0.000_003_00,
        "output_per_token": 0.000_015_00,
    },
}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, dict[str, float]] | None = None,
) -> float:
    """Estimate the USD cost of an LLM call given token counts.

    Parameters
    ----------
    model:
        The model identifier; must be a key in ``pricing``.
    input_tokens:
        Number of prompt (input) tokens consumed.
    output_tokens:
        Number of completion (output) tokens generated.
    pricing:
        Optional pricing table. Defaults to :data:`MODEL_PRICING`.

    Returns
    -------
    float
        Estimated cost in USD.

    Raises
    ------
    KeyError
        If ``model`` is not present in the pricing table.
    """
    table = pricing if pricing is not None else MODEL_PRICING
    if model not in table:
        raise KeyError(f"Unknown model: {model!r}")
    rates = table[model]
    return (
        input_tokens * rates["input_per_token"]
        + output_tokens * rates["output_per_token"]
    )


__all__ = ["MODEL_PRICING", "estimate_cost"]
