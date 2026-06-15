from __future__ import annotations


# Pricing table: (usd_per_1m_input_tokens, usd_per_1m_output_tokens)
# Source: representative public pricing for common OpenAI models.
# Values are in USD per 1 million tokens.
_PRICING_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-2024-05-13": (5.00, 15.00),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-4-32k": (60.00, 120.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "gpt-3.5-turbo-0125": (0.50, 1.50),
    "gpt-3.5-turbo-instruct": (1.50, 2.00),
    "o1-preview": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o1": (15.00, 60.00),
    "o3-mini": (1.10, 4.40),
    "text-embedding-3-small": (0.02, 0.02),
    "text-embedding-3-large": (0.13, 0.13),
    "text-embedding-ada-002": (0.10, 0.10),
}

# Default pricing applied when the requested model is not in the table.
_DEFAULT_PRICING: tuple[float, float] = (1.00, 3.00)


def model_pricing(model_name: str) -> tuple[float, float]:
    """
    Return the (input, output) token pricing for a given model.

    Parameters
    ----------
    model_name : str
        The name of the model (e.g., "gpt-4o", "gpt-4o-mini").

    Returns
    -------
    tuple[float, float]
        A 2-tuple of (usd_per_1m_input_tokens, usd_per_1m_output_tokens).
        Unknown models return sensible defaults of (1.00, 3.00).
    """
    if not isinstance(model_name, str):
        raise TypeError(f"model_name must be a str, got {type(model_name).__name__}")

    # Normalize: strip whitespace, lower-case for case-insensitive lookup.
    key = model_name.strip().lower()
    if not key:
        return _DEFAULT_PRICING

    return _PRICING_TABLE.get(key, _DEFAULT_PRICING)
