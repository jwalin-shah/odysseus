from __future__ import annotations

MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {
        "input": 0.00015,
        "output": 0.0006,
    },
    "gpt-4o": {
        "input": 0.005,
        "output": 0.015,
    },
    "gpt-3.5-turbo": {
        "input": 0.0005,
        "output": 0.0015,
    },
    "default": {
        "input": 0.001,
        "output": 0.002,
    },
}


def lookup_pricing(model: str, table: dict | None = None) -> dict[str, float]:
    """Return the per-token pricing dict for a model.

    Falls back to MODEL_PRICING['default'] when the model is unknown
    or missing from the provided table.
    """
    if table is None:
        table = MODEL_PRICING
    return table.get(model, MODEL_PRICING["default"])
