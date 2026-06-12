"""sys-checkpoint: The Context Compressor.

Takes raw text from stdin or a file, compresses it into dense markdown,
respecting a token budget to prevent quota blowout on expensive models.
"""
import sys
import argparse


"""sys-checkpoint: The Context Compressor.

Takes raw text from stdin or a file, compresses it into dense markdown,
respecting a token budget to prevent quota blowout on expensive models.
"""
import sys
import argparse


"""sys-checkpoint: The Context Compressor.

Takes raw text from stdin or a file, compresses it into dense markdown,
respecting a token budget to prevent quota blowout on expensive models.
"""
import sys
import argparse


"""sys-checkpoint: The Context Compressor.

Takes raw text from stdin or a file, compresses it into dense markdown,
respecting a token budget to prevent quota blowout on expensive models.
"""
import sys
import argparse


def compress(text, max_chars):
    ...

def mock_cheap(text, max_chars):
    """Mock-cheap handler: returns a fixed string, ignoring input."""
    return "mock-cheap: fixed response"
def main():
    """Main entry point for the sys-checkpoint CLI."""
    ...
    # Convert token budget to character budget (1 token ≈ 4 chars)
    max_chars = args.max_tokens * 4

    # Dispatch to appropriate handler
    if args.model == "mock-cheap":
        compressed = mock_cheap(raw_text, max_chars)
    else:
        compressed = compress(raw_text, max_chars)
    ...
def main():
    """Main entry point for the sys-checkpoint CLI."""
    parser = argparse.ArgumentParser(...)
    ...
    if args.model == "mock-cheap":
        compressed = mock_cheap(raw_text, max_chars)
    else:
        compressed = compress(raw_text, max_chars)

    print(compressed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
def main():
    """Main entry point for the sys-checkpoint CLI."""
    parser = argparse.ArgumentParser(...)
def mock_cheap(text, max_chars):
    """Mock-cheap handler: returns a fixed string, ignoring input."""
    return "mock-cheap: fixed response"
def main():
    """Main entry point for the sys-checkpoint CLI."""
    ...
    # Convert token budget to character budget (1 token ≈ 4 chars)
    max_chars = args.max_tokens * 4

    # Dispatch to appropriate handler
    if args.model == "mock-cheap":
        compressed = mock_cheap(raw_text, max_chars)
    else:
        compressed = compress(raw_text, max_chars)
    ...
def main():
    """Main entry point for the sys-checkpoint CLI."""
    parser = argparse.ArgumentParser(
        prog="sys-checkpoint",
        description="Compress raw text into dense markdown"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=100,
        help="Maximum output tokens (1 token ≈ 4 chars)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="dummy-mock",
        help="Compression model to use (default: dummy-mock for local extractive compression)"
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Optional input file (reads from stdin if not provided)"
    )

    args = parser.parse_args()

    # Read input from file or stdin
    if args.input_file:
        with open(args.input_file, 'r') as f:
            raw_text = f.read()
    else:
        raw_text = sys.stdin.read()

    # Handle empty input
    if not raw_text or not raw_text.strip():
        print("No content to compress")
        return 0

    # Convert token budget to character budget (1 token ≈ 4 chars)
    max_chars = args.max_tokens * 4

    # Dispatch to appropriate handler
    if args.model == "mock-cheap":
        compressed = mock_cheap(raw_text, max_chars)
    else:
        compressed = compress(raw_text, max_chars)

    print(compressed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
def main():
    """Main entry point for the sys-checkpoint CLI."""
    parser = argparse.ArgumentParser(
        prog="sys-checkpoint",
        description="Compress raw text into dense markdown"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=100,
        help="Maximum output tokens (1 token ≈ 4 chars)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="dummy-mock",
        help="Compression model to use (default: dummy-mock for local extractive compression)"
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Optional input file (reads from stdin if not provided)"
    )

    args = parser.parse_args()

    # Read input from file or stdin
    if args.input_file:
        with open(args.input_file, 'r') as f:
            raw_text = f.read()
    else:
        raw_text = sys.stdin.read()

    # Handle empty input
    if not raw_text or not raw_text.strip():
        print("No content to compress")
        return 0

    # Convert token budget to character budget (1 token ≈ 4 chars)
    max_chars = args.max_tokens * 4

    # Compress based on model (for now, only dummy-mock is implemented)
    compressed = compress(raw_text, max_chars)

    print(compressed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
