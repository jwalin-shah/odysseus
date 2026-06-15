import json
import os
import tempfile
from typing import Dict

_POLICIES_DIR = os.path.join(os.path.expanduser('~'), '.approval_policies')


def _get_owner_path(owner: str) -> str:
    return os.path.join(_POLICIES_DIR, f"{owner}.json")


def load_approval_policy(owner: str) -> Dict[str, str]:
    path = _get_owner_path(owner)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
            return {}
    except (json.JSONDecodeError, IOError, OSError):
        return {}


def save_approval_decision(owner: str, action_key: str, decision: str) -> None:
    if decision not in ('always', 'never'):
        raise ValueError(f"decision must be 'always' or 'never', got: {decision!r}")
    os.makedirs(_POLICIES_DIR, exist_ok=True)
    path = _get_owner_path(owner)
    policy = load_approval_policy(owner)
    policy[action_key] = decision
    dir_name = os.path.dirname(path) or '.'
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=f".{owner}.", suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(policy, f, ensure_ascii=False, sort_keys=True)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise
