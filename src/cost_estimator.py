def entry_output_tokens(entry: dict) -> int:
    """Extracts the output/completion token count from a trajectory log entry.

    Checks for 'output_tokens' first, then falls back to 'completion_tokens'.
    Returns 0 when neither key is present.
    """
    return entry.get('output_tokens', entry.get('completion_tokens', 0))
