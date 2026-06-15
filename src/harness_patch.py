def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate a pending approval action.

    - If ``result.needs_approval`` is False, return it unchanged.
    - If ``result.needs_approval`` is True and ``confirmed`` is False, return
      it unchanged so the caller can surface an approval UI.
    - If ``result.needs_approval`` is True and ``confirmed`` is True, look up
      the target function in :mod:`src.inbox_tool` by name (taken from the
      ``"fn"`` key in ``approval_payload``), invoke it with the remaining
      payload entries as kwargs, and return a final ``HarnessResult``
      describing the outcome.

    Expected ``approval_payload`` shape::

        {"platform": "imessage", "action": "send",
         "to": "mom", "body": "...", "fn": "send_imessage"}
    """
    # Nothing to gate, or caller hasn't confirmed yet — pass through as-is.
    if not result.needs_approval or not confirmed:
        return result

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")

    if not fn_name:
        return HarnessResult(
            content="Approval payload is missing 'fn'; cannot execute.",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    # Resolve the target function dynamically from inbox_tool.
    # (Add ``import src.inbox_tool as inbox_tool`` at the top of harness.py
    # to avoid the function-local import if you prefer module-level.)
    import src.inbox_tool as inbox_tool
    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Function '{fn_name}' not found in inbox_tool.",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    # Dispatch/metadata keys are not passed to the target function;
    # everything else in the payload is forwarded as a kwarg.
    _DISPATCH_KEYS = {"fn", "action", "platform"}
    kwargs = {k: v for k, v in payload.items() if k not in _DISPATCH_KEYS}

    try:
        fn_result = fn(**kwargs)
    except TypeError as e:
        # Most likely a kwargs/signature mismatch.
        return HarnessResult(
            content=f"Bad arguments for {fn_name}: {e}",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )
    except Exception as e:
        return HarnessResult(
            content=f"Error executing {fn_name}: {e}",
            action_taken="error",
            needs_approval=False,
            approval_payload={},
        )

    action = payload.get("action", "execute")
    platform = payload.get("platform", "")

    if fn_result is None or fn_result == "":
        body = f"{action.capitalize()} on {platform} complete." if platform else f"{action.capitalize()} complete."
    else:
        body = f"{action.capitalize()} on {platform}: {fn_result}" if platform else f"{action.capitalize()}: {fn_result}"

    return HarnessResult(
        content=body,
        action_taken=action,
        needs_approval=False,
        approval_payload={},
    )
