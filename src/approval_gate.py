"""Harness write approval prompt rendering."""


def format_approval_prompt(summary: dict) -> str:
    """Render a multi-line CLI prompt for approving a harness write action.

    The prompt lists the tool, target (when provided), and presents three
    choices to the operator: approve, deny, or remember. When the summary
    is empty, sensible placeholders are used so the prompt is never blank.
    """
    tool = summary.get("tool", "unknown_tool")
    target = summary.get("target", "<unspecified>")
    action = summary.get("action", "write")

    lines = [
        "Harness Write Action — Approval Required",
        "----------------------------------------",
        f"Action: {action}",
        f"Tool:   {tool}",
        f"Target: {target}",
        "",
        "Choose how to proceed:",
        "  [A]pprove  - allow this write to proceed",
        "  [D]eny     - reject this write",
        "  [R]emember - approve and remember the policy for next time",
        "",
        "Your choice [A/d/r]: ",
    ]
    return "\n".join(lines)
