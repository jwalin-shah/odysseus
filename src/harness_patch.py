def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result.

    The approval payload is expected to look like:
        {"platform": "imessage",
         "action":   "send",
         "to":       "mom",
         "body":     "...",
         "fn":       "send_imessage"}
    Anything in the payload except the metadata keys (fn, action, platform) is passed
    as kwargs to the looked-up function on src.inbox_tool.
    """
    # Nothing to gate, or caller hasn't approved yet -> hand the result back as-is.
    if not result.needs_approval or not confirmed:
        return result

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload is missing the function name ('fn').",
            action_taken=result.action_taken,
            needs_approval=False,
        )

    # Late import keeps this patch self-contained without changing the top-level imports.
    import src.inbox_tool as inbox_tool

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Unknown inbox_tool function: {fn_name!r}.",
            action_taken=result.action_taken,
            needs_approval=False,
        )

    # Strip the descriptive metadata; the rest are real arguments for the callee.
    _META = {"fn", "action", "platform"}
    call_kwargs = {k: v for k, v in payload.items() if k not in _META}

    try:
        outcome = fn(**call_kwargs)
    except Exception as exc:  # surface the error to the caller instead of raising
        return HarnessResult(
            content=f"Action '{fn_name}' failed: {exc}",
            action_taken=result.action_taken,
            needs_approval=False,
        )

    return HarnessResult(
        content=f"Action '{fn_name}' completed: {outcome}",
        action_taken=result.action_taken,
        needs_approval=False,
    )
