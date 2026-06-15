import time
from typing import Optional, Callable


def format_confirmation_prompt(action_name: str, action_args: dict) -> str:
    lines = [f"Approve {action_name}?"]
    for key, value in action_args.items():
        lines.append(f"  {key}: {value}")
    lines.append("[y/N] ")
    return "\n".join(lines)


def summarize_write_intent(tool_name: str, args: dict) -> str:
    """Produce a single human-readable sentence describing a write action.

    Suitable for display in a confirmation prompt.
    """
    if not args:
        return f"About to perform {tool_name}."

    target_keys = {"path", "file", "filename", "target", "destination", "url"}
    recipient_keys = {"to", "address", "recipient", "cc", "bcc"}
    subject_keys = {"subject", "title"}
    body_keys = {"body", "message", "content", "text", "data"}

    remaining = set(args.keys())
    ordered = []
    for group in (target_keys, recipient_keys, subject_keys, body_keys):
        for key in args:
            if key in group and key in remaining:
                ordered.append(key)
                remaining.discard(key)
    for key in args:
        if key in remaining:
            ordered.append(key)
            remaining.discard(key)

    parts = []
    for key in ordered:
        value = args[key]
        if key in target_keys:
            parts.append(f"to {key} {value!r}")
        elif key in recipient_keys:
            parts.append(f"to {value!r}")
        elif key in subject_keys:
            parts.append(f"with {key} {value!r}")
        elif key in body_keys:
            parts.append(f"with {key} {value!r}")
        else:
            parts.append(f"{key}={value!r}")

    return f"About to call {tool_name} ({'; '.join(parts)})."


_APPROVE_RESPONSES = frozenset({
    "y", "yes", "yeah", "yep", "yup", "ya",
    "ok", "okay", "k",
    "sure", "alright", "allright",
    "true", "t",
    "1",
    "approve", "approved", "accept", "accepted",
    "go", "proceed", "continue", "do it", "doit",
    "yessir", "yeppers", "aye", "affirmative", "roger",
    "yeah sure", "yes please",
})

_DENY_RESPONSES = frozenset({
    "n", "no", "nope", "nah", "na", "nay",
    "false", "f",
    "0",
    "deny", "denied", "reject", "rejected", "refuse", "refused",
    "stop", "cancel", "abort", "halt",
    "negative", "no way", "nuh-uh", "no thanks",
})


def parse_confirmation(raw: str) -> str:
    """Normalize a free-form CLI confirmation response.

    Returns 'approve' for yes-like inputs (y/yes/ok/sure/...), 'deny' for
    no-like inputs (n/no/nope/stop/...), and 'unknown' for anything that
    isn't a clear yes or no (including empty/whitespace, punctuation only,
    or ambiguous words like 'maybe').
    """
    if raw is None:
        return "unknown"
    text = str(raw).strip().lower()
    if not text:
        return "unknown"
    # Strip trailing punctuation/symbols ("yes!", "y.", "n?", "no,", ...)
    # but keep the word content intact so multi-word answers like
    # "yes please" or "no thanks" still match.
    normalized = "".join(ch for ch in text if not ch in ".,!?;:'\"")
    normalized = " ".join(normalized.split())
    if not normalized:
        return "unknown"
    if normalized in _APPROVE_RESPONSES:
        return "approve"
    if normalized in _DENY_RESPONSES:
        return "deny"
    return "unknown"


assert parse_confirmation('y') == 'approve'
assert parse_confirmation('N') == 'deny'
assert parse_confirmation('maybe') == 'unknown'


def record_approval_audit_event(event_type: str, action_kind: str, owner: str, decision: str) -> dict:
    """Build a structured audit record for an approval gate decision.

    Captures the event type, the kind of action that was gated, the owner
    (actor) making the decision, the decision itself, and a wall-clock
    timestamp taken at the moment the event is recorded.
    """
    return {
        "event_type": event_type,
        "action_kind": action_kind,
        "owner": owner,
        "decision": decision,
        "timestamp": time.time(),
    }


assert record_approval_audit_event('confirm', 'send', 'alice', 'approve')['decision'] == 'approve'
assert record_approval_audit_event('confirm', 'send', 'alice', 'approve')['action_kind'] == 'send'
assert 'timestamp' in record_approval_audit_event('confirm', 'send', 'alice', 'deny')


def gate_write_action(tool_name: str, args: dict, input_fn=None) -> bool:
    """Top-level entry point that gates a write action behind user approval.

    Classifies the action (read-only tools pass through without prompting),
    summarizes the intent, prompts the user, and returns True only when the
    user issues an 'approve' decision. 'deny', 'edit', and any non-approving
    or unrecognized input all return False.
    """
    if input_fn is None:
        input_fn = input

    # --- Classify: read-only tools are safe and require no confirmation ---
    read_only_tools = frozenset({
        "read_file", "read", "get", "list", "list_dir", "ls",
        "search", "find", "query", "fetch", "view", "show",
        "info", "status", "check", "exists", "stat",
        "cat", "head", "tail", "grep", "wc", "diff",
    })
    normalized_name = (tool_name or "").lower()
    is_read_only = (
        normalized_name in read_only_tools
        or normalized_name.startswith("read_")
        or normalized_name.startswith("get_")
        or normalized_name.startswith("list_")
        or normalized_name.startswith("search_")
        or normalized_name.startswith("fetch_")
    )
    if is_read_only:
        return True

    # --- Summarize ---
    summary = summarize_write_intent(tool_name, args)

    # --- Prompt the user ---
    prompt = f"{summary}\nApprove this action? [y/n/edit] "
    response = input_fn(prompt)

    # --- Decide ---
    decision = parse_confirmation(response)
    return decision == "approve"


def prompt_cli_confirmation(write_intent: dict, input_provider: Optional[Callable[[str], str]] = None) -> str:
    """Display a formatted confirmation prompt to the CLI and return the raw user response string.

    Renders the fields of ``write_intent`` as a readable summary, asks the
    user to approve, and returns whatever the input provider yields
    unchanged. The caller is responsible for interpreting the response
    (e.g. via ``parse_confirmation``).
    """
    if input_provider is None:
        input_provider = input

    # --- Build a readable prompt from the write intent ---
    lines = ["Pending action:"]
    if write_intent:
        for key, value in write_intent.items():
            lines.append(f"  {key}: {value}")
    lines.append("Approve this action? [y/N] ")
    prompt = "\n".join(lines)

    # --- Hand off to the input provider and return the raw response ---
    return input_provider(prompt)
