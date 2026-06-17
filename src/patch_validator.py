"""patch_validator.py — Unified-diff validator and applier for the M3 patch pipeline.

Three-layer safety model:
1. Structural validation: --- a/+++ b/ headers, @@ hunk headers with exact
   count matching, every body line prefixed with ' ', '+', or '-'.
2. Pre-apply dry-run via `patch --dry-run -p1` against the on-disk file.
3. JSON fallback: {path, find, replace} payload reconstructed into a
   well-formed unified diff via difflib before applying.
"""
from __future__ import annotations

import difflib
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Tuple

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_MINUS_HEADER_RE = re.compile(r"^--- ")
_PLUS_HEADER_RE = re.compile(r"^\+\+\+ ")


class DiffValidationError(ValueError):
    """Raised when a unified diff is structurally invalid."""


def validate_unified_diff(diff_text: str) -> None:
    """Assert that diff_text is a well-formed unified diff.

    Checks:
    - Presence of '--- ' and '+++ ' file headers.
    - At least one '@@ -a,b +c,d @@' hunk header.
    - Every hunk-body line prefixed with ' ', '+', '-', or '\\' (no-newline marker).
    - Old-line count (context + removed) and new-line count (context + added)
      exactly match the values declared in each hunk header.

    Raises DiffValidationError on any fault.
    """
    lines = diff_text.splitlines()

    has_minus = any(_MINUS_HEADER_RE.match(l) for l in lines)
    has_plus = any(_PLUS_HEADER_RE.match(l) for l in lines)
    if not has_minus:
        raise DiffValidationError("Missing '--- ' file header")
    if not has_plus:
        raise DiffValidationError("Missing '+++ ' file header")

    hunk_count = 0
    i = 0
    while i < len(lines):
        m = _HUNK_RE.match(lines[i])
        if not m:
            i += 1
            continue

        hunk_count += 1
        old_count = int(m.group(2)) if m.group(2) is not None else 1
        new_count = int(m.group(4)) if m.group(4) is not None else 1
        hunk_line = lines[i]
        i += 1

        body_old = 0
        body_new = 0
        while i < len(lines):
            line = lines[i]
            if _HUNK_RE.match(line) or _MINUS_HEADER_RE.match(line):
                break
            if not line:
                # Blank line in body — counts as context in some diff tools.
                body_old += 1
                body_new += 1
            elif line[0] == " ":
                body_old += 1
                body_new += 1
            elif line[0] == "-":
                body_old += 1
            elif line[0] == "+":
                body_new += 1
            elif line[0] == "\\":
                pass  # "\ No newline at end of file"
            else:
                raise DiffValidationError(
                    f"Invalid hunk body prefix {line[0]!r} in line: {line[:80]!r}"
                )
            i += 1

        if body_old != old_count:
            raise DiffValidationError(
                f"Hunk '{hunk_line}' declares {old_count} old lines "
                f"but body contains {body_old}"
            )
        if body_new != new_count:
            raise DiffValidationError(
                f"Hunk '{hunk_line}' declares {new_count} new lines "
                f"but body contains {body_new}"
            )

    if hunk_count == 0:
        raise DiffValidationError("Diff contains no @@ hunk headers")


def dry_run_patch(diff_text: str, base_dir: str) -> Tuple[bool, str]:
    """Run `patch --dry-run -p1` against diff_text rooted at base_dir.

    Returns (success, output) where output combines stdout + stderr.
    Returns (False, reason) when the `patch` binary is not available.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".patch", delete=False, encoding="utf-8"
    ) as f:
        f.write(diff_text)
        patch_file = f.name

    try:
        result = subprocess.run(
            ["patch", "--dry-run", "-p1", "--input", patch_file],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return False, "patch binary not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "patch --dry-run timed out after 30s"
    finally:
        Path(patch_file).unlink(missing_ok=True)


def json_payload_to_diff(payload: Dict[str, str], base_dir: str) -> str:
    """Reconstruct a unified diff from a JSON {path, find, replace} payload.

    Reads the on-disk file at base_dir/payload['path'], applies a single
    exact-text substitution, and produces a unified diff via difflib.

    Raises:
        KeyError: if payload is missing 'path', 'find', or 'replace'.
        FileNotFoundError: if the target file does not exist.
        ValueError: if the 'find' text does not appear in the file.
    """
    rel_path: str = payload["path"]
    find_text: str = payload["find"]
    replace_text: str = payload["replace"]

    file_path = Path(base_dir) / rel_path
    original = file_path.read_text(encoding="utf-8")

    if find_text not in original:
        raise ValueError(
            f"'find' text not found verbatim in {rel_path}"
        )

    new_content = original.replace(find_text, replace_text, 1)

    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
    )
    if not diff_lines:
        raise ValueError(
            f"'find' and 'replace' are identical — no diff produced for {rel_path}"
        )

    return "".join(diff_lines)


def apply_unified_diff(diff_text: str, base_dir: str) -> Tuple[bool, str]:
    """Validate, dry-run, then apply a unified diff.

    Returns (success, message).
    """
    try:
        validate_unified_diff(diff_text)
    except DiffValidationError as exc:
        return False, f"Structural validation failed: {exc}"

    ok, msg = dry_run_patch(diff_text, base_dir)
    if not ok:
        return False, f"Dry-run rejected diff: {msg}"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".patch", delete=False, encoding="utf-8"
    ) as f:
        f.write(diff_text)
        patch_file = f.name

    try:
        result = subprocess.run(
            ["patch", "-p1", "--input", patch_file],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, "Applied successfully"
        return False, f"Apply failed: {(result.stdout + result.stderr).strip()}"
    except FileNotFoundError:
        return False, "patch binary not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "patch apply timed out after 30s"
    finally:
        Path(patch_file).unlink(missing_ok=True)
