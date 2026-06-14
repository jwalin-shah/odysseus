import argparse
import sys
import os
import json
from pathlib import Path

DEFAULT_QUOTA_FILE = "/Users/jwalinshah/projects/platform/systems/quota-core/data/quota-live.json"

MOCK_MODELS = {
    "dummy-mock": "Mock MiniMax Response",
}


from typing import Optional

def pick_premium_tier(providers: dict) -> Optional[str]:
    """Returns the best premium tier (claude-a, claude-b, pioneer) or None if all are exhausted."""
    # Priority 1: Claude-A (Premium)
    ca = providers.get("ca", {}).get("quotas", {})
    if ca.get("weekly_pct_remaining", 0) > 10 and ca.get("session_pct_remaining", 100) > 10:
        return "claude-a"

    # Priority 2: Claude-B (Premium)
    cb = providers.get("cb", {}).get("quotas", {})
    if cb.get("weekly_pct_remaining", 0) > 10 and cb.get("session_pct_remaining", 100) > 10:
        return "claude-b"

    # Priority 3: Pioneer (Pro Legacy)
    pioneer = providers.get("pioneer", {})
    if pioneer.get("status") == "VERIFIED" and pioneer.get("used_pct", 100) < 90:
        return "pioneer"

    return None

def get_best_model():
    """
    Waterfall Routing Algorithm:
    Reads quota state from SYS_QUOTA_STATE env var (or default path) at
    call time, then falls through ca -> cb -> pioneer -> codex.
    """
    quota_path = Path(os.environ.get("SYS_QUOTA_STATE", DEFAULT_QUOTA_FILE))

    if not quota_path.exists():
        sys.stderr.write(
            f"Warning: {quota_path} not found. Falling back to free compute.\n"
        )
        return "codex"

    try:
        with open(quota_path) as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(
            f"Warning: Failed to parse {quota_path}: {e}. Falling back to free compute.\n"
        )
        return "codex"

    providers = data.get("providers", {})
    premium = pick_premium_tier(providers)
    if premium:
        return premium

    # Fallback: Free Compute
    return "codex"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="V2 LLM Router with Quota Pre-flight")
    parser.add_argument(
        "--model",
        required=False,
        default="auto",
        help="The model to route the request to. 'auto' uses waterfall routing.",
    )
    return parser.parse_args(argv)


def main():
    args = parse_args()
    sys.stdin.read()  # consume stdin (prompt not used in routing logic)

    model = args.model

    # Explicit mock model override
    if model in MOCK_MODELS:
        print(MOCK_MODELS[model])
        return 0

    # Waterfall routing
    if model == "auto":
        model = get_best_model()

    print(f"Routed to {model} successfully")
    return 0
