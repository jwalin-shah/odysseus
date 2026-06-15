from difflib import SequenceMatcher


def summarize_diff(old: str, new: str) -> dict:
    """Summarize a text diff as a count of added and removed lines."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    matcher = SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    added = 0
    removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            added += j2 - j1
        if tag in ("delete", "replace"):
            removed += i2 - i1
    return {"added": added, "removed": removed}
