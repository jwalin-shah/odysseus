def format_approval_prompt(summary: str, details: dict) -> str:
    lines = []
    lines.append(f"Proposed action: {summary}")

    if details:
        lines.append("Details:")
        for key, value in details.items():
            lines.append(f"  {key}: {value}")

    lines.append("Do you approve? (y/n)")

    return "\n".join(lines)
