def format_approval_prompt(action: str, params: dict, owner: str) -> str:
    lines = [
        "=== APPROVAL REQUIRED ===",
        f"Action:    {action}",
        f"Owner:     {owner}",
        "Parameters:",
    ]
    for key, value in params.items():
        lines.append(f"  - {key}: {value}")
    lines.append("")
    lines.append("Approve this action? [y/N]: ")
    return "\n".join(lines)
