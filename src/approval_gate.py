def format_confirmation_prompt(action_name: str, action_args: dict) -> str:
    lines = [f"Approve {action_name}?"]
    for key, value in action_args.items():
        lines.append(f"  {key}: {value}")
    lines.append("[y/N] ")
    return "\n".join(lines)


def format_write_prompt(action: str, target: str, preview: str) -> str:
    lines = [f"About to {action} {target}:"]
    lines.append("  Preview:")
    for preview_line in preview.split("\n"):
        lines.append(f"    {preview_line}")
    lines.append("[y/N]")
    return "\n".join(lines)


assert 'write_file' in format_write_prompt('write_file', '/tmp/a.txt', 'hello')
assert '/tmp/a.txt' in format_write_prompt('write_file', '/tmp/a.txt', 'hello')
assert format_write_prompt('edit_file', 'p.py', 'x=1').endswith('[y/N]')
