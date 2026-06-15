import json
import datetime
import os


def record_approval_audit(decision: str, action: dict, log_path: str) -> None:
    """Append a single audit-log line capturing the decision, action summary, and timestamp."""
    timestamp = datetime.datetime.now().isoformat()
    action_summary = json.dumps(action, sort_keys=True)
    log_line = f"{timestamp} | decision={decision} | action={action_summary}\n"
    
    # Ensure the directory exists
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(log_line)
