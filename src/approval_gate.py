"""Approval gate logic for action policies."""


def evaluate_approval_required(action_kind: str, policy: dict) -> bool:
    """Return True if the given action kind requires explicit user approval.

    The policy dict is expected to contain boolean flags named
    ``require_approval_<action_kind>s`` (e.g. ``require_approval_writes``).
    If the corresponding flag is missing, the action is treated as not
    requiring approval.
    """
    flag_name = f"require_approval_{action_kind}s"
    return bool(policy.get(flag_name, False))
