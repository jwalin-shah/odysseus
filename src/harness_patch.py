def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Approval gate for HarnessResult actions requiring confirmation.

    Behavior:
      * If ``result.needs_approval`` is False, return ``result`` unchanged.
      * If ``result.needs_approval`` is True and ``confirmed`` is False,
        return ``result`` unchanged so the caller can render an approval UI
        from ``result.approval_payload``.
      * If ``result.needs_approval`` is True and ``confirmed`` is True, look
        up the function named in ``approval_payload["fn"]`` on
        ``src.inbox_tool``, invoke it with the remaining payload entries as
        kwargs, and return the final ``HarnessResult``.

    The expected approval payload shape is::

        {"platform": "imessage",
         "action":   "send",
         "to":       "mom",
         "body":     "...",
         "fn":       "send_imessage"}

    ``"fn"`` selects the function on ``inbox_tool``; ``"platform"`` and
    ``"action"`` are routing/metadata and are NOT forwarded as kwargs.
    Everything else in the payload is passed to the resolved function as a
    keyword argument, so the producer of ``approval_payload`` is responsible
    for matching the target function's signature.
    """
    # Nothing pending: pass through (covers needs_approval=False and idempotent re-calls).
    if not result.needs_approval:
        return result

    # Awaiting user confirmation: pass through so the caller can show the approval UI.
    if not confirmed:
        return result

    payload = dict(result.approval_payload or {})
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content="Approval payload is missing 'fn' (function name to execute).",
            action_taken="approval_execute_failed",
            needs_approval=False,
            approval_payload={},
        )

    # Local import: keeps the module importable even if inbox_tool is unavailable
    # at import time, and surfaces a clear error path below if it's still missing.
    from src import inbox_tool

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Cannot execute: function '{fn_name}' not found on src.inbox_tool.",
            action_taken="approval_execute_failed",
            needs_approval=False,
            approval_payload={},
        )

    # Strip routing/metadata keys; forward the rest as kwargs to the function.
    metadata_keys = {"fn", "platform", "action"}
    call_kwargs = {k: v for k, v in payload.items() if k not in metadata_keys}

    try:
        output = fn(**call_kwargs)
    except TypeError as exc:
        # Most likely cause: payload kwargs don't match the function's signature.
        return HarnessResult(
            content=(
                f"Failed to execute {fn_name} with kwargs {call_kwargs!r}: {exc}. "
                "Check that approval_payload matches the function signature."
            ),
            action_taken="approval_execute_failed",
            needs_approval=False,
            approval_payload={},
        )
    except Exception as exc:  # noqa: BLE001 - surface any execution error to the caller
        return HarnessResult(
            content=f"Error while executing {fn_name}: {exc}",
            action_taken="approval_execute_failed",
            needs_approval=False,
            approval_payload={},
        )

    # Normalize the function's return value into a string content field.
    if isinstance(output, str):
        content = output
    elif output is None:
        content = f"Executed {fn_name} successfully."
    else:
        content = str(output)

    return HarnessResult(
        content=content,
        action_taken=f"approved_{payload.get('action', 'execute')}",
        needs_approval=False,
        approval_payload={},
    )
