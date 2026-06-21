"""sys-checkpoint: The Context Compressor.

Takes raw text from stdin or a file, compresses it into dense markdown,
respecting a token budget to prevent quota blowout on expensive models.
"""
from __future__ import annotations

import argparse
import sys


def compress(text: str, max_chars: int) -> str:
    """ODYSSEUS-CHECKPOINT: extractive compression by sentence + word budget.

    Walks the input sentence-by-sentence, joining sentences greedily until
    adding the next would exceed max_chars, then returns the joined prefix.
    Sentences are split on '.', '!', '?' boundaries and the trailing
    whitespace is trimmed. If the first sentence alone exceeds max_chars,
    truncate it to max_chars.
    """
    if not text or not text.strip():
        return ""
    if max_chars <= 0:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    # Split on sentence-ending punctuation. The split keeps the delimiters
    # via a positive lookbehind so we can re-join with a single space.
    import re
    parts = re.split(r"(?<=[.!?])\s+", text)
    out: list[str] = []
    total = 0
    for p in parts:
        candidate_len = (total + len(p) + (1 if out else 0))
        if candidate_len > max_chars:
            break
        out.append(p)
        total = candidate_len
    if not out:
        return text[:max_chars]
    return " ".join(out)


def mock_cheap(text: str, max_chars: int) -> str:
    """Mock-cheap handler: returns a fixed string, ignoring input."""
    return "mock-cheap: fixed response"


def main() -> int:
    """Main entry point for the sys-checkpoint CLI."""
    parser = argparse.ArgumentParser(
        prog="sys_checkpoint",
        description="Compress raw text into dense markdown",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=100,
        help="Maximum output tokens (1 token ≈ 4 chars)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="dummy-mock",
        help="Compression model to use (default: dummy-mock for local extractive compression)",
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Optional input file (reads from stdin if not provided)",
    )

    args = parser.parse_args()

    if args.input_file:
        with open(args.input_file, "r") as f:
            raw_text = f.read()
    else:
        raw_text = sys.stdin.read()

    if not raw_text or not raw_text.strip():
        print("No content to compress")
        return 0

    # Convert token budget to character budget (1 token ≈ 4 chars)
    max_chars = args.max_tokens * 4

    if args.model == "mock-cheap":
        compressed = mock_cheap(raw_text, max_chars)
    else:
        compressed = compress(raw_text, max_chars)

    print(compressed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
