def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """If result.needs_approval and not confirmed, return it unchanged (caller shows approval UI).
    If confirmed=True, look up the function in inbox_tool by name from approval_payload["fn"],
    invoke it with the remaining payload keys as kwargs, and return the final result.

    Expected approval_payload shape (example):
        {"platform": "imessage", "action": "send",
         "to": "mom", "body": "...", "fn": "send_imessage"}
    Keys in {"platform", "action", "fn"} are dispatch metadata and not forwarded
    as function arguments; everything else is passed as **kwargs.
    """
    # Nothing to do if there's no pending approval, or the user hasn't confirmed yet —
    # the caller is expected to render the approval UI and re-invoke us with confirmed=True.
    if not result.needs_approval or not confirmed:
        return result

    # Local import keeps this patch self-contained and avoids forcing a top-level
    # module reference on the rest of the file.
    import src.inbox_tool as inbox_tool

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")

    if not fn_name:
        return HarnessResult(
            content="Error: approval payload missing 'fn' (cannot resolve action).",
            action_taken="approval_error",
        )

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None:
        return HarnessResult(
            content=f"Error: function '{fn_name}' not found in src.inbox_tool.",
            action_taken="approval_error",
        )

    # Strip dispatch metadata; everything else is treated as a function argument.
    _META_KEYS = {"platform", "action", "fn"}
    kwargs = {k: v for k, v in payload.items() if k not in _META_KEYS}

    try:
        output = fn(**kwargs)
    except TypeError as e:
        # Most likely a kwarg name mismatch — surface a useful error to the caller.
        return HarnessResult(
            content=f"Error: {fn_name} rejected arguments {sorted(kwargs)}: {e}",
            action_taken="execution_error",
        )
    except Exception as e:
        return HarnessResult(
            content=f"Error executing {fn_name}: {e}",
            action_taken="execution_error",
        )

    return HarnessResult(
        content=str(output),
        action_taken=payload.get("action", "executed"),
        needs_approval=False,
        approval_payload={},
    )
