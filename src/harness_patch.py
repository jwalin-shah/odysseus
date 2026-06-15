def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate execution of mutating actions on explicit user approval.

    Behavior:
      - If `result.needs_approval` is False: return `result` unchanged.
      - If `result.needs_approval` is True and `confirmed` is False: return
        `result` unchanged. The caller is expected to inspect
        `result.approval_payload`, surface an approval UI, and call this
        function again with `confirmed=True` once the user consents.
      - If `result.needs_approval` is True and `confirmed` is True: look up
        the function named in `result.approval_payload["fn"]` on
        `src.inbox_tool`, invoke it with the remaining payload fields as
        kwargs, and return a fresh `HarnessResult` describing the outcome.

    Expected approval_payload shape (set by route()):
        {
            "platform": "imessage" | "gmail" | "calendar" | ...,
            "action":   "send" | "create" | "delete" | ...,
            "fn":       "<callable name in src.inbox_tool>",
            ...        # other kwargs forwarded to the function
        }
    """
    # No approval required, or user has not yet confirmed -> pass through.
    if not result.needs_approval or not confirmed:
        return result

    # Resolve the function by name on the inbox_tool module.
    from src import inbox_tool  # local import keeps the patch self-contained

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")

    if not fn_name:
        return HarnessResult(
            content=f"Approval payload missing 'fn' field: {payload!r}",
            action_taken="error",
            needs_approval=False,
        )

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Function {fn_name!r} not found or not callable in src.inbox_tool",
            action_taken="error",
            needs_approval=False,
        )

    # Strip metadata keys; everything else is forwarded as a kwarg to `fn`.
    # Add to this set if you introduce more envelope-only fields later.
    _METADATA_KEYS = {"fn", "platform", "action"}
    call_kwargs = {k: v for k, v in payload.items() if k not in _METADATA_KEYS}

    try:
        output = fn(**call_kwargs)
    except TypeError as e:
        # Most likely a kwarg name mismatch between payload and function signature.
        return HarnessResult(
            content=(
                f"Error calling {fn_name}({', '.join(sorted(call_kwargs))}): "
                f"{e}. Check approval_payload keys match the function signature."
            ),
            action_taken="error",
            needs_approval=False,
        )
    except Exception as e:
        return HarnessResult(
            content=f"Error executing {fn_name}: {e!r}",
            action_taken="error",
            needs_approval=False,
        )

    return HarnessResult(
        content=str(output) if output is not None else f"{fn_name} completed.",
        action_taken=payload.get("action", "executed"),
        needs_approval=False,
        approval_payload={},
    )
