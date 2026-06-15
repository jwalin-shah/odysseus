_WRITE_ACTIONS = frozenset({
    "write_file",
    "edit_file",
    "create_document",
    "update_document",
    "edit_document",
})


def is_write_action(action_name: str) -> bool:
    """Return True when the given harness action is a write action that
    must pass through the approval gate."""
    return action_name in _WRITE_ACTIONS


def format_confirmation_prompt(action_name: str, action_args: dict) -> str:
    lines = [f"Approve {action_name}?"]
    for key, value in action_args.items():
        lines.append(f"  {key}: {value}")
    lines.append("[y/N] ")
    return "\n".join(lines)


assert is_write_action('write_file') is True
assert is_write_action('edit_file') is True
assert is_write_action('read_file') is False
