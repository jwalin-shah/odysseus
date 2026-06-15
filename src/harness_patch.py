def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result.

    The approval_payload is expected to contain:
        {"platform": ..., "action": "send"|"create"|"delete", ..., "fn": "send_imessage"}
    The "fn" key names a callable in src.inbox_tool; remaining keys are forwarded as kwargs.
    """
    # No approval required, or caller hasn't confirmed yet — just hand it back.
    if not result.needs_approval or not confirmed:
        return result

    payload = dict(result.approval_payload)
    fn_name = payload.pop("fn", None)
    action = payload.pop("action", None) or "executed"

    if not fn_name:
        return HarnessResult(
            content="Approval payload missing 'fn' — cannot execute pending action.",
            action_taken="approval_failed",
            needs_approval=False,
        )

    # Resolve the function by name from inbox_tool.
    try:
        import src.inbox_tool as inbox_tool
    except ImportError:
        return HarnessResult(
            content="inbox_tool module is not importable.",
            action_taken="approval_failed",
            needs_approval=False,
        )

    fn = getattr(inbox_tool, fn_name, None)
    if not callable(fn):
        return HarnessResult(
            content=f"Unknown action function on inbox_tool: {fn_name!r}",
            action_taken="approval_failed",
            needs_approval=False,
        )

    # Execute the pending action.
    try:
        output = fn(**payload)
    except TypeError as e:
        # Wrong kwargs (signature mismatch) — surface a clear error.
        return HarnessResult(
            content=f"Bad arguments for {fn_name}: {e}",
            action_taken=f"{action}_failed",
            needs_approval=False,
        )
    except Exception as e:
        return HarnessResult(
            content=f"Action {fn_name} failed: {e}",
            action_taken=f"{action}_failed",
            needs_approval=False,
        )

    return HarnessResult(
        content=str(output) if output is not None else f"{action} completed.",
        action_taken=action,
        needs_approval=False,
    )
