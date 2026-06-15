def format_confirmation_prompt(action_name: str, action_args: dict) -> str:
    lines = [f"Approve {action_name}?"]
    for key, value in action_args.items():
        lines.append(f"  {key}: {value}")
    lines.append("[y/N] ")
    return "\n".join(lines)


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


# --- Risk tier classification for write actions ---

# Paths that are considered sensitive. Writing to (or under) any of these
# is treated as high-risk regardless of the tool name.
_SENSITIVE_PATH_TOKENS = (
    "/etc/", "/etc/passwd", "/etc/shadow", "/etc/sudoers", "/etc/hosts",
    "/boot/", "/sys/", "/proc/", "/dev/",
    "/usr/", "/sbin/", "/bin/", "/lib/", "/lib64/",
    "/var/log/", "/var/lib/", "/var/run/",
    "/root/", "/.ssh/", "/.aws/", "/.gnupg/", "/.config/",
    "c:\\windows", "c:\\program files", "c:\\programdata",
)

# Tools whose default behavior is to talk to the outside world. Even
# when the call looks innocent (e.g. a short email body) we want a
# human to confirm before we fire it off.
_EXTERNAL_SEND_TOOLS = frozenset({
    "send_email", "send_mail", "smtp_send",
    "send_sms", "send_message", "send_notification",
    "http_post", "http_put", "http_request", "api_call", "fetch",
    "webhook", "publish", "upload", "ftp_upload", "scp",
    "post_to_slack", "slack_post", "discord_post",
    "tweet", "post_tweet", "mastodon_post",
})

# Tools that are inherently destructive. They bypass path checks because
# the harm comes from the verb, not the destination.
_DESTRUCTIVE_TOOLS = frozenset({
    "rm", "rm_rf", "delete", "delete_file", "delete_record",
    "drop_table", "drop_database", "truncate", "purge",
    "format", "mkfs", "dd", "wipe", "shred",
    "exec", "execute", "run_command", "shell", "bash", "cmd",
})

# Verbs inside an args blob (e.g. a shell command string) that signal
# destruction even when the tool name itself is neutral.
_DESTRUCTIVE_VERB_PATTERNS = (
    "rm -rf", "rm -fr", "rm -r ", "rmdir", "del /", "del /f",
    "drop table", "drop database", "truncate table",
    ":(){:|:&};:", "mkfs", "wipefs", "shred ",
    "format c:", "format d:",
    "git push --force", "git push -f", "git reset --hard",
    "dd if=", ":>|", "chmod 777", "chown -r",
)

# Locations that are clearly scratch / throwaway space. Writing here is
# almost always safe and gets the lowest tier.
_TEMP_PATH_PREFIXES = ("/tmp/", "/var/tmp/", "/dev/shm/", "\\temp\\", "\\tmp\\")


def _normalize_path(args: dict) -> str:
    """Pull a filesystem path out of common arg names, lowercased."""
    for key in ("path", "file", "filename", "filepath", "target", "destination", "dest", "url"):
        if key in args and args[key] is not None:
            return str(args[key]).lower()
    return ""


def _normalize_command(args: dict) -> str:
    """Pull a shell command out of common arg names, lowercased."""
    for key in ("command", "cmd", "shell_command", "script", "code"):
        if key in args and args[key] is not None:
            return str(args[key]).lower()
    return ""


def classify_write_action(tool_name: str, args: dict) -> str:
    """Classify a harness write tool call as 'high', 'medium', or 'low' risk.

    The tier is bumped up by:
      * sensitive filesystem paths (system dirs, credential stores, ...),
      * destructive verbs (rm -rf, drop table, format, force-push, ...),
      * external sends (email, HTTP POST, webhook, upload, ...).
    """
    args = args or {}
    tool = (tool_name or "").lower().strip()
    path = _normalize_path(args)
    command = _normalize_command(args)

    # 1. Destructive tools are always high risk.
    if tool in _DESTRUCTIVE_TOOLS:
        return "high"

    # 2. Destructive verbs hidden in a command string.
    if command:
        for pat in _DESTRUCTIVE_VERB_PATTERNS:
            if pat in command:
                return "high"

    # 3. Sensitive path targets.
    if path:
        # Exact sensitive file matches
        if path in _SENSITIVE_PATH_TOKENS:
            return "high"
        # Prefix / substring matches against directory tokens
        for token in _SENSITIVE_PATH_TOKENS:
            if token.endswith("/") and path.startswith(token):
                return "high"
            if token in path and token != path:
                return "high"

    # 4. External send tools default to medium risk.
    if tool in _EXTERNAL_SEND_TOOLS:
        return "medium"

    # 5. Writing to a known scratch/temp directory is low risk.
    if tool.startswith("write") or tool in {"create_file", "save_file", "edit_file", "append_file"}:
        if path and any(path.startswith(p) for p in _TEMP_PATH_PREFIXES):
            return "low"
        # Writing to a persistent (non-temp) location needs a glance.
        if path:
            return "medium"
        return "low"

    # 6. Unknown tools with a sensitive path caught above; otherwise low.
    return "low"


assert classify_write_action('write_file', {'path': '/etc/passwd'}) == 'high'
assert classify_write_action('write_file', {'path': '/tmp/notes.md'}) == 'low'
assert classify_write_action('send_email', {'to': 'a@b.com'}) == 'medium'
