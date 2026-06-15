"""Approval gate prompt formatting for pending write actions."""


def format_approval_prompt(action_name: str, payload: dict) -> str:
    """Build a human-readable multi-line CLI prompt for a pending write action.

    The prompt names the action and lists each key/value pair in the payload
    so the user can review what will be executed before approving.

    Args:
        action_name: Identifier of the action awaiting approval.
        payload: Mapping of parameter names to their proposed values.

    Returns:
        A formatted multi-line string ending with the ``[y/N]`` confirmation
        prompt.
    """
    lines = [f"Pending action: {action_name}"]

    if payload:
        lines.append("Parameters:")
        for key, value in payload.items():
            lines.append(f"  - {key}: {value}")

    lines.append("")
    lines.append("Approve this action? [y/N]")

    return "\n".join(lines)
