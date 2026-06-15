def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate a write action behind explicit user confirmation.

    Behavior:
      * If ``result.needs_approval`` is False, return ``result`` unchanged.
      * If ``result.needs_approval`` is True and ``confirmed`` is False,
        return ``result`` unchanged so the caller can surface an approval UI.
      * If ``result.needs_approval`` is True and ``confirmed`` is True,
        look up the action function on ``src.inbox_tool`` by name (via the
        ``fn`` key in ``approval_payload``), invoke it with the remaining
        payload keys as kwargs, and return a fresh ``HarnessResult``
        describing the outcome.
    """
    # Read-only or already-executed result: nothing pending, hand it back.
    if not result.needs_approval:
        return result
    # Pending approval but caller hasn't confirmed yet.
    if not confirmed:
        return result

    # Lazy import: keeps write-side modules off the read-only import path.
    from src import inbox_tool

    payload = result.approval_payload or {}
    fn_name = payload.get("fn")

    if not fn_name:
        return HarnessResult(
            content="Approval payload is missing the 'fn' dispatch key; cannot execute.",
            action_taken="confirm_and_execute:missing_fn",
            needs_approval=False,
            approval_payload={},
        )

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Unknown action function '{fn_name}' on src.inbox_tool.",
            action_taken=f"confirm_and_execute:unknown_fn:{fn_name}",
            needs_approval=False,
            approval_payload={},
        )

    # Rebuild kwargs from the payload, dropping the dispatch key.
    # Anything else (e.g. {"to": "mom", "body": "..."}) is forwarded as-is.
    kwargs = {k: v for k, v in payload.items() if k != "fn"}

    try:
        outcome = fn(**kwargs)
    except Exception as exc:  # noqa: BLE001 - surface failure to caller, don't bubble
        return HarnessResult(
            content=f"Action '{fn_name}' failed: {exc}",
            action_taken=f"confirm_and_execute:error:{fn_name}",
            needs_approval=False,
            approval_payload={},
        )

    return HarnessResult(
        content=str(outcome),
        action_taken=f"executed:{fn_name}",
        needs_approval=False,
        approval_payload={},
    )
