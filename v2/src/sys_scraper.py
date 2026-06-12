import subprocess
import json
import os
import sys
from pathlib import Path

def fetch_agy_quota():
    """
    Runs the native Swift OCR visual scraper to fetch the live Antigravity quota.
    """
    try:
        proc = subprocess.run(
            ["python3", "live_status.py", "--json"],
            cwd="/Users/jwalinshah/projects/platform/systems/quota-core/src",
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        # The visual scraper may print status logs before the JSON block
        stdout = proc.stdout
        json_start = stdout.find('{')
        if json_start == -1:
            return None
            
        payload = stdout[json_start:]
        data = json.loads(payload)
        
        # The OCR scraper returns quotas keyed by model tab
        agy_tab = data.get("quotas", {}).get("Models", {})
        
        # We need the lowest remaining percentage
        pcts = []
        for quota_text in agy_tab.get("bottom", []):
            try:
                pct = int(quota_text.replace('%', '').strip())
                pcts.append(pct)
            except ValueError:
                pass
                
        if pcts:
            return min(pcts)
        return None
        
    except Exception as e:
        sys.stderr.write(f"Failed to fetch AGY quota via OCR: {e}\n")
        return None

def sync_to_sqlite(pct_remaining):
    """
    Initializes the V2 SQLite database with the live quota percentage.
    """
    if pct_remaining is None:
        sys.stderr.write("No valid quota found to sync.\n")
        return False
        
    db_path = os.environ.get("ODY_QUOTA_STATE", "/Users/jwalinshah/projects/odysseus/v2/data/quota.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # In V2, we track tokens/usage. A percentage needs to be mapped to a budget.
    # For now, we will simply store the 'limit' as 100, and 'used' as (100 - pct_remaining)
    # This allows `ody-quota deduct` to work on a 0-100 scale.
    
    # We call sys_quota via subprocess to initialize it
    quota_cli = Path(__file__).parent.parent / ".venv" / "bin" / "ody-quota"
    if not quota_cli.exists():
        # Fallback to direct python call if shim isn't built yet
        quota_cli = ["python3", str(Path(__file__).parent / "sys_quota.py")]
    else:
        quota_cli = [str(quota_cli)]
        
    cmd = quota_cli + [
        "init",
        "--db", db_path,
        "--limit", "100", # Max percentage
    ]
    
    subprocess.run(cmd, check=True)
    
    # Now deduct the used amount to set the current state
    used_amount = 100 - pct_remaining
    if used_amount > 0:
        deduct_cmd = quota_cli + [
            "deduct",
            "--db", db_path,
            "--amount", str(used_amount)
        ]
        subprocess.run(deduct_cmd, check=True)
        
    print(f"✅ V2 SQLite Quota synced! Set to {pct_remaining}% remaining.")
    return True

if __name__ == "__main__":
    print("Fetching live AGY quota via OCR...")
    pct = fetch_agy_quota()
    if pct is not None:
        sync_to_sqlite(pct)
    else:
        sys.exit(1)
