import os
import sys
import time
import json

def check_auth():
    token = os.environ.get("ODY_CALLER_TOKEN")
    if token != "mock_secure_orchestrator_token_123":
        print("Unauthorized", file=sys.stderr)
        sys.exit(1)

def check_rate_limit():
    rate_limit_file = os.environ.get("ODY_VAULT_STATE", "/tmp/ody_vault_rate_limit.json")
    now = time.time()
    
    # We must handle concurrent access carefully.
    # But for tests, standard read/write with a simple retry or using a lock file
    # is fine. We will use a simpler approach for now.
    
    data = {"timestamps": [], "locked": False}
    
    if os.path.exists(rate_limit_file):
        try:
            with open(rate_limit_file, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    if data.get("locked"):
        print("Rate limit exceeded. Locked down.", file=sys.stderr)
        sys.exit(1)
        
    timestamps = data.get("timestamps", [])
    timestamps = [t for t in timestamps if now - t <= 1.0]
    
    if len(timestamps) >= 5:
        data["locked"] = True
        with open(rate_limit_file, "w") as f:
            json.dump(data, f)
        print("Rate limit exceeded. Locked down.", file=sys.stderr)
        sys.exit(1)
        
    timestamps.append(now)
    data["timestamps"] = timestamps
    with open(rate_limit_file, "w") as f:
        json.dump(data, f)

def main():
    check_auth()
    check_rate_limit()
    
    # Handle normal operations here
    sys.exit(0)

if __name__ == "__main__":
    main()
