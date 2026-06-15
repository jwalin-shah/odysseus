def action_requires_approval(risk: str, policy: dict) -> bool:
    """Return True if the action risk level requires approval per policy."""
    require_approval_for = policy.get('require_approval_for', [])
    return risk in require_approval_for
