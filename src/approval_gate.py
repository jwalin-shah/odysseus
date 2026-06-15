"""Approval gate for CLI confirmations."""


def parse_cli_response(raw: str) -> str:
    """Parses a raw CLI confirmation response into one of 'approve', 'deny', or 'abort'.

    Recognized affirmative responses (case-insensitive, whitespace-trimmed):
        - 'y', 'yes'         -> 'approve'
        - 'n', 'no'          -> 'deny'
        - 'q', 'quit', 'abort' -> 'abort'

    Args:
        raw: The raw input string from the CLI.

    Returns:
        One of the canonical strings: 'approve', 'deny', or 'abort'.

    Raises:
        TypeError: If ``raw`` is not a string.
        ValueError: If ``raw`` is not a recognized confirmation response.
    """
    if not isinstance(raw, str):
        raise TypeError(f"Expected str, got {type(raw).__name__}")

    cleaned = raw.strip().lower()

    if cleaned in ("y", "yes"):
        return "approve"
    if cleaned in ("n", "no"):
        return "deny"
    if cleaned in ("q", "quit", "abort"):
        return "abort"

    raise ValueError(f"Invalid CLI response: {raw!r}")
