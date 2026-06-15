def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result."""
    if not result.needs_approval or not confirmed:
        return result

    # Lazy import to avoid touching the top-level import block in harness.py.
    from src import inbox_tool

    payload = result.approval_payload
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload missing 'fn' field.",
            action_taken="approval_error",
            needs_approval=False,
        )

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None:
        return HarnessResult(
            content=f"Function '{fn_name}' not found in inbox_tool.",
            action_taken="approval_error",
            needs_approval=False,
        )

    # Build kwargs from payload (drop the dispatch key itself).
    kwargs = {k: v for k, v in payload.items() if k != "fn"}

    try:
        output = fn(**kwargs)
    except Exception as exc:
        return HarnessResult(
            content=f"Execution failed for {fn_name}: {exc}",
            action_taken="approval_error",
            needs_approval=False,
        )

    return HarnessResult(
        content=str(output) if output is not None else "Action completed.",
        action_taken=f"executed:{fn_name}",
        needs_approval=False,
    )
