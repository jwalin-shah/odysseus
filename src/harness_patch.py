def confirm_and_execute(result: HarnessResult, confirmed: bool = False) -> HarnessResult:
    """Gate a HarnessResult behind user approval.

    - If ``result.needs_approval`` is False, the result is returned unchanged
      (nothing to gate).
    - If ``result.needs_approval`` is True and ``confirmed`` is False, the
      result is returned unchanged so the caller can present an approval UI
      to the user.
    - If ``confirmed`` is True, the function named in
      ``result.approval_payload['fn']`` is looked up on ``src.inbox_tool`` and
      invoked with the remaining payload items as keyword arguments. The
      returned value is wrapped in a new ``HarnessResult`` with
      ``needs_approval=False``.
    """
    # Nothing to gate when no approval is required.
    if not result.needs_approval:
        return result

    # Caller hasn't confirmed yet; leave the result intact for the UI.
    if not confirmed:
        return result

    payload = result.approval_payload
    fn_name = payload.get("fn")
    if not fn_name:
        return HarnessResult(
            content=(
                f"Approval payload missing 'fn'; cannot execute "
                f"{result.action_taken!r}."
            ),
            action_taken=result.action_taken,
            needs_approval=False,
        )

    # Local import keeps the harness importable even if inbox_tool fails to
    # load, and avoids any potential circular-import surprises.
    from src import inbox_tool

    fn = getattr(inbox_tool, fn_name, None)
    if fn is None or not callable(fn):
        return HarnessResult(
            content=f"Function {fn_name!r} not found on src.inbox_tool.",
            action_taken=result.action_taken,
            needs_approval=False,
        )

    # Everything except the metadata keys is forwarded as kwargs to fn.
    # ('fn' is the dispatch key; 'platform'/'action' are descriptive only.)
    reserved = {"fn", "platform", "action"}
    kwargs = {k: v for k, v in payload.items() if k not in reserved}

    try:
        exec_result = fn(**kwargs)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the caller
        return HarnessResult(
            content=f"Execution of {fn_name} failed: {exc}",
            action_taken=result.action_taken,
            needs_approval=False,
        )

    content = exec_result if isinstance(exec_result, str) else str(exec_result)

    return HarnessResult(
        content=content,
        action_taken=result.action_taken,
        needs_approval=False,
    )
