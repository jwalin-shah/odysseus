def classify_action_risk(action: str) -> str:
    """
    Classify a named harness action as 'read' or 'write'.

    Read actions only observe state without mutating external systems.
    Write actions mutate external state and therefore require approval.

    Unknown actions default to 'write' (fail-secure) so that any unrecognized
    action is treated as potentially mutating and routed through the gate.

    Examples:
        classify_action_risk('read') == 'read'
        classify_action_risk('send') == 'write'
        classify_action_risk('calendar_create') == 'write'
    """
    if not isinstance(action, str):
        return 'write'

    normalized = action.strip().lower()
    if not normalized:
        return 'write'

    # Verbs that indicate mutation of external state.
    # Checked first so that, e.g., 'send_email' is not misread as a read.
    write_verbs = (
        'send', 'create', 'update', 'delete', 'write', 'post',
        'put', 'patch', 'remove', 'destroy', 'add', 'modify',
        'change', 'set', 'drop', 'truncate', 'insert', 'upsert',
        'approve', 'reject', 'cancel', 'submit', 'publish',
        'forward', 'reply', 'transfer', 'pay', 'charge',
    )

    # Verbs that indicate read-only observation.
    read_verbs = (
        'read', 'get', 'list', 'view', 'fetch', 'query', 'search',
        'check', 'inspect', 'observe', 'monitor', 'retrieve',
        'describe', 'show', 'count', 'find', 'lookup', 'select',
    )

    for verb in write_verbs:
        # Match either as a whole token (separated by non-alphanumeric)
        # or as a suffix/prefix that clearly indicates the action kind.
        # Using substring keeps the heuristic simple and matches
        # conventions like 'calendar_create', 'send_email', 'post_message'.
        if verb in normalized:
            return 'write'

    for verb in read_verbs:
        if verb in normalized:
            return 'read'

    # Fail-secure: unknown actions require approval.
    return 'write'
