def apply_approval_policy(request: dict, policy: dict) -> dict:
    """Apply approval policy to a request.

    Returns a decision dict if the request's action_key matches a stored
    'always'/'never' entry, else None to force a CLI prompt.
    """
    action_key = request.get('action_key')
    decision = policy.get(action_key)

    if decision == 'always':
        return {'allow': True}
    elif decision == 'never':
        return {'allow': False}
    return None
