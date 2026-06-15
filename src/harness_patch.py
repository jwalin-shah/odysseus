def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result."""
    # Not gated, or caller hasn't approved yet -> bubble the result back as-is.
    if not result.needs_approval or not confirmed:
        return result

    # Local import: keeps the patch self-contained and avoids depending on which
    # write-action functions are re-exported at module top-level.
    from src import inbox_tool

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")

    if not fn_name:
        return HarnessResult(
            content="Approval payload missing 'fn' (function name); cannot execute.",
            action_taken=result.action_taken,
            needs_approval=False,
        )

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None:
        return HarnessResult(
            content=f"Unknown action function '{fn_name}' on src.inbox_tool.",
            action_taken=result.action_taken,
            needs_approval=False,
        )

    # Forward every payload field except the metadata keys as kwargs to the action.
    # e.g. {"platform":"imessage","action":"send","to":"mom","body":"...","fn":"send_imessage"}
    #      -> send_imessage(to="mom", body="...")
    _meta = {"platform", "action", "fn"}
    kwargs = {k: v for k, v in payload.items() if k not in _meta}

    try:
        outcome = fn(**kwargs)
    except Exception as exc:  # surface the failure to the caller; do not raise
        return HarnessResult(
            content=f"Action '{fn_name}' failed: {exc}",
            action_taken=result.action_taken,
            needs_approval=False,
        )

    return HarnessResult(
        content=str(outcome) if outcome is not None else f"Action '{fn_name}' executed.",
        action_taken=result.action_taken,
        needs_approval=False,
    )
