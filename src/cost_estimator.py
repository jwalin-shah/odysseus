# Global pricing table mapping model_id to (input_price_per_1k, output_price_per_1k) in USD
_PRICING_TABLE = {}


def register_model_pricing(model_id: str, input_price_per_1k: float, output_price_per_1k: float) -> None:
    """Add or overwrite the per-1k-token USD pricing for a model in the global pricing table.

    Args:
        model_id: The unique identifier of the model.
        input_price_per_1k: Price in USD per 1,000 input tokens.
        output_price_per_1k: Price in USD per 1,000 output tokens.
    """
    _PRICING_TABLE[model_id] = (input_price_per_1k, output_price_per_1k)


def get_model_pricing(model_id: str):
    """Retrieve the per-1k-token USD pricing tuple for a model.

    Args:
        model_id: The unique identifier of the model.

    Returns:
        A tuple of (input_price_per_1k, output_price_per_1k), or None if not found.
    """
    return _PRICING_TABLE.get(model_id)
