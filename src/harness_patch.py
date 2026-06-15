def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, execute the pending action and return the final result.

    The approval_payload is expected to look like:
        {"platform": "imessage", "action": "send",
         "to": "mom", "body": "...", "fn": "send_imessage"}

    'fn' names a callable in src.inbox_tool; remaining keys are passed as kwargs.
    """
    # No pending action, or user hasn't approved yet -> just hand it back.
    if not result.needs_approval or not confirmed:
        return result

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload is missing the 'fn' reference.",
            action_taken="error",
        )

    # Lazy import so we resolve the function by string name without forcing
    # inbox_tool to be imported as a module at the top of harness.py.
    from src import inbox_tool

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None:
        return HarnessResult(
            content=f"Unknown action function '{fn_name}' in inbox_tool.",
            action_taken="error",
        )

    # Pass through everything except the control/metadata keys as kwargs.
    control_keys = {"fn", "platform", "action"}
    kwargs = {k: v for k, v in payload.items() if k not in control_keys}

    try:
        output = fn(**kwargs)
    except TypeError as e:
        # Wrong signature for the named function.
        return HarnessResult(
            content=f"Failed to call {fn_name} with {list(kwargs)}: {e}",
            action_taken="error",
        )
    except Exception as e:
        # Underlying tool raised (network, permission, etc.).
        return HarnessResult(
            content=f"Execution of {fn_name} failed: {e}",
            action_taken="error",
        )

    return HarnessResult(
        content=str(output),
        action_taken=payload.get("action", "executed"),
    )
