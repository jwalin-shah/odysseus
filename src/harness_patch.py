def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate write-class actions behind a user approval step.

    Behavior:
      - If result.needs_approval is False (or payload is empty), return result unchanged.
      - If result.needs_approval is True and confirmed is False, return result unchanged
        so the caller can render its approval UI.
      - If confirmed is True, look up the action function in `src.inbox_tool` by the
        name stored in result.approval_payload["fn"], invoke it with the remaining
        payload keys as kwargs, and return a new HarnessResult describing the outcome.

    Expected approval_payload shape:
        {
            "platform": "imessage",
            "action":   "send",
            "to":       "mom",
            "body":     "...",
            "fn":       "send_imessage",
        }
    The keys "fn", "action", and "platform" are treated as metadata; everything else
    is forwarded as kwargs to the resolved function.
    """
    # Nothing pending -> nothing to do.
    if not result.needs_approval or not result.approval_payload:
        return result

    # Approval required but not yet granted -> hand back to caller for UI.
    if not confirmed:
        return result

    # User confirmed -> resolve and invoke the action function.
    from src import inbox_tool  # local import to keep module load order safe

    payload = result.approval_payload
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload missing 'fn'; cannot execute pending action.",
            action_taken="approval_error",
            needs_approval=False,
        )

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Unknown inbox_tool function: {fn_name!r}.",
            action_taken="approval_error",
            needs_approval=False,
        )

    # Forward everything except metadata keys as kwargs.
    kwargs = {
        k: v for k, v in payload.items() if k not in ("fn", "action", "platform")
    }

    try:
        output = fn(**kwargs)
    except TypeError as e:
        return HarnessResult(
            content=f"Bad arguments for {fn_name}: {e}",
            action_taken="approval_error",
            needs_approval=False,
        )
    except Exception as e:
        return HarnessResult(
            content=f"Error executing {fn_name}: {e}",
            action_taken="error",
            needs_approval=False,
        )

    action = payload.get("action", "action")
    platform = payload.get("platform", "")
    action_taken = f"{platform}_{action}" if platform else action
    content = str(output) if output is not None else f"{action_taken} completed."

    return HarnessResult(
        content=content,
        action_taken=action_taken,
        needs_approval=False,
    )
