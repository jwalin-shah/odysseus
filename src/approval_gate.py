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
