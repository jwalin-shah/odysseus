import argparse
import sys
import os
import json
from pathlib import Path

# The ground truth for quotas from the scraper engine
DEFAULT_QUOTA_FILE = "/Users/jwalinshah/projects/platform/systems/quota-core/data/quota-live.json"
QUOTA_LIVE_JSON = Path(os.environ.get("SYS_QUOTA_STATE", DEFAULT_QUOTA_FILE))

import argparse
import sys
import os
import json
from pathlib import Path

# The ground truth for quotas from the scraper engine
DEFAULT_QUOTA_FILE = "/Users/jwalinshah/projects/platform/systems/quota-core/data/quota-live.json"
QUOTA_LIVE_JSON = Path(os.environ.get("SYS_QUOTA_STATE", DEFAULT_QUOTA_FILE))

def get_best_model():
    """
    Waterfall Routing Algorithm:
    Uses real-time reset data from the scraper engine to prioritize premium accounts
    before falling back to free compute.
    """
    import subprocess
    try:
        subprocess.run(["ody-quota", "check"], check=True)
    except Exception as e:
        sys.stderr.write(f"Warning: ody-quota check failed: {e}\n")

    if not QUOTA_LIVE_JSON.exists():
        sys.stderr.write(f"Warning: {QUOTA_LIVE_JSON} not found. Falling back to free compute.\n")
        return "codex"

    try:
        with open(QUOTA_LIVE_JSON) as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to parse {QUOTA_LIVE_JSON}. Falling back to free compute.\n")
        return "codex"
        
    providers = data.get("providers", {})

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

    # Fallback: Free Compute (Codex / AGY)
    return "codex"

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="V2 LLM Router with Quota Pre-flight")
    parser.add_argument("--model", required=False, default="auto", help="The model to route the request to. 'auto' uses waterfall routing.")
    return parser.parse_args(argv)

def main():
    args = parse_args()
    prompt = sys.stdin.read()
def main():
    parser = argparse.ArgumentParser(description="V2 LLM Router with Quota Pre-flight")
    parser.add_argument("--model", required=False, default="auto", help="The model to route the request to. 'auto' uses waterfall routing.")
    
    args = parser.parse_args()
    prompt = sys.stdin.read()