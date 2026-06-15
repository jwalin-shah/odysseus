def format_action_preview(action: str, payload: dict) -> str:
    """Build a human-readable single-string summary of a pending harness action.

    Args:
        action: The name of the action to be performed (e.g. 'send', 'calendar_create').
        payload: A mapping of parameter names to their values for the action.

    Returns:
        A single string summarizing the action and its parameters.
    """
    if not payload:
        return action

    formatted_params = ", ".join(
        f"{key}={value}" for key, value in payload.items()
    )
    return f"{action}({formatted_params})"
