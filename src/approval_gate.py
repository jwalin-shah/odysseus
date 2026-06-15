def merge_approval_policy_defaults(policy: dict) -> dict:
    """Return a copy of the policy with safe defaults filled in for missing keys."""
    defaults = {
        'require_approval_for': ['write', 'destructive'],
        'allow_always': True,
    }
    result = dict(policy)
    for key, value in defaults.items():
        if key not in result:
            result[key] = value
    return result
