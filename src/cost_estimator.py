"""Cost estimator utilities for trajectory logs."""
from __future__ import annotations


def parse_log_entry(entry: dict) -> tuple[str, int, int]:
    """Extract (model, input_tokens, output_tokens) from a trajectory entry.

    Accepts several common key shapes found in LLM trajectory logs:
      * Top-level keys: ``input_tokens``/``output_tokens`` (Anthropic style)
        or ``prompt_tokens``/``completion_tokens`` (OpenAI style).
      * Nested inside ``usage``, ``token_usage``, ``tokens``, or
        ``token_counts`` sub-dicts, which may use either naming convention.
      * Shorthand keys ``input``/``output`` when nothing else is available.

    Missing token counts default to ``0``.
    """
    model = entry.get("model", "")

    # Collect candidate dicts: the entry itself plus common nested containers.
    containers: list[dict] = [entry]
    for key in ("usage", "token_usage", "tokens", "token_counts"):
        nested = entry.get(key)
        if isinstance(nested, dict):
            containers.append(nested)

    input_tokens = 0
    output_tokens = 0
    input_found = False
    output_found = False

    for container in containers:
        if not input_found:
            for key in ("input_tokens", "prompt_tokens", "input"):
                if key in container:
                    input_tokens = container[key]
                    input_found = True
                    break
        if not output_found:
            for key in ("output_tokens", "completion_tokens", "output"):
                if key in container:
                    output_tokens = container[key]
                    output_found = True
                    break
        if input_found and output_found:
            break

    return (str(model), int(input_tokens), int(output_tokens))
