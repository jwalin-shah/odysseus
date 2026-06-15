def build_action_summary(tool: str, args: dict) -> str:
    """Render a compact, human-readable one-line summary of a proposed harness action."""
    if not args:
        return f"{tool}()"
    parts = []
    for key, value in args.items():
        parts.append(f"{key}={value}")
    return f"{tool}({', '.join(parts)})"
