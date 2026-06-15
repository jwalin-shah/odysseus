def format_confirmation_prompt(action_name: str, action_args: dict) -> str:
    lines = [f"Approve {action_name}?"]
    for key, value in action_args.items():
        lines.append(f"  {key}: {value}")
    lines.append("[y/N] ")
    return "\n".join(lines)
