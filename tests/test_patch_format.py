"""Tests for the M3 patch pipeline: diff validation, dry-run, and JSON fallback.

Covers:
- validate_unified_diff: accept well-formed diffs, reject structural faults
- json_payload_to_diff: round-trips through difflib
- dry_run_patch: `patch --dry-run` succeeds on regenerated diffs for the three
  v2 target files (v2/src/sys_quota.py, v2/src/sys_router.py, v2/src/sys_map.py)
- parse_m3_response: new Format 0 (diff fence) and Format 0b (JSON payload)
"""
from __future__ import annotations

import difflib
import json
import textwrap
from pathlib import Path
from unittest.mock import patch as mock_patch

import pytest

from src.patch_validator import (
    DiffValidationError,
    dry_run_patch,
    json_payload_to_diff,
    validate_unified_diff,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent


def _make_diff(rel_path: str, find_text: str, replace_text: str) -> str:
    """Generate a unified diff string by applying find→replace to a repo file."""
    file_path = REPO_ROOT / rel_path
    original = file_path.read_text(encoding="utf-8")
    assert find_text in original, f"find_text not in {rel_path}"
    new_content = original.replace(find_text, replace_text, 1)
    lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
        )
    )
    assert lines, f"find and replace are identical — no diff for {rel_path}"
    return "".join(lines)


# ---------------------------------------------------------------------------
# validate_unified_diff — structural checks
# ---------------------------------------------------------------------------

class TestValidateUnifiedDiff:
    def test_accepts_well_formed_single_hunk(self):
        diff = textwrap.dedent("""\
            --- a/foo.py
            +++ b/foo.py
            @@ -1,3 +1,3 @@
             line one
            -line two
            +line TWO
             line three
        """)
        validate_unified_diff(diff)  # must not raise

    def test_accepts_multi_hunk(self):
        diff = textwrap.dedent("""\
            --- a/foo.py
            +++ b/foo.py
            @@ -1,3 +1,3 @@
             line one
            -old
            +new
             line three
            @@ -10,3 +10,3 @@
             ctx a
            -bad
            +good
             ctx b
        """)
        validate_unified_diff(diff)

    def test_rejects_missing_minus_header(self):
        diff = textwrap.dedent("""\
            +++ b/foo.py
            @@ -1,2 +1,2 @@
            -old
            +new
             ctx
        """)
        with pytest.raises(DiffValidationError, match="'--- '"):
            validate_unified_diff(diff)

    def test_rejects_missing_plus_header(self):
        diff = textwrap.dedent("""\
            --- a/foo.py
            @@ -1,2 +1,2 @@
            -old
            +new
             ctx
        """)
        with pytest.raises(DiffValidationError, match="'\\+\\+\\+ '"):
            validate_unified_diff(diff)

    def test_rejects_no_hunks(self):
        diff = textwrap.dedent("""\
            --- a/foo.py
            +++ b/foo.py
            just some text without any hunk headers
        """)
        with pytest.raises(DiffValidationError, match="no @@ hunk"):
            validate_unified_diff(diff)

    def test_rejects_invalid_body_prefix(self):
        diff = textwrap.dedent("""\
            --- a/foo.py
            +++ b/foo.py
            @@ -1,2 +1,2 @@
            bare line without prefix
            +new
        """)
        with pytest.raises(DiffValidationError, match="Invalid hunk body prefix"):
            validate_unified_diff(diff)

    def test_rejects_old_count_mismatch(self):
        # hunk claims 3 old lines but body only has 2
        diff = textwrap.dedent("""\
            --- a/foo.py
            +++ b/foo.py
            @@ -1,3 +1,2 @@
             ctx
            -removed
        """)
        with pytest.raises(DiffValidationError, match="declares 3 old lines"):
            validate_unified_diff(diff)

    def test_rejects_new_count_mismatch(self):
        # old_count=2 matches body (ctx + removed = 2), new_count=3 but body has 2
        diff = textwrap.dedent("""\
            --- a/foo.py
            +++ b/foo.py
            @@ -1,2 +1,3 @@
             ctx
            -removed
            +added
        """)
        with pytest.raises(DiffValidationError, match="declares 3 new lines"):
            validate_unified_diff(diff)

    def test_accepts_hunk_with_no_newline_marker(self):
        diff = textwrap.dedent("""\
            --- a/foo.py
            +++ b/foo.py
            @@ -1,1 +1,1 @@
            -old
            \\ No newline at end of file
            +new
            \\ No newline at end of file
        """)
        validate_unified_diff(diff)

    def test_accepts_count_omitted_means_one(self):
        # @@ -5 +5 @@ means -5,1 +5,1
        diff = textwrap.dedent("""\
            --- a/foo.py
            +++ b/foo.py
            @@ -5 +5 @@
            -old
            +new
        """)
        validate_unified_diff(diff)


# ---------------------------------------------------------------------------
# json_payload_to_diff
# ---------------------------------------------------------------------------

class TestJsonPayloadToDiff:
    def test_produces_valid_unified_diff(self, tmp_path):
        target = tmp_path / "example.py"
        target.write_text("def foo():\n    return 1\n")
        payload = {"path": "example.py", "find": "return 1", "replace": "return 2"}
        diff_text = json_payload_to_diff(payload, str(tmp_path))
        validate_unified_diff(diff_text)
        assert "--- a/example.py" in diff_text
        assert "+++ b/example.py" in diff_text
        assert "-    return 1" in diff_text
        assert "+    return 2" in diff_text

    def test_raises_on_find_not_found(self, tmp_path):
        target = tmp_path / "example.py"
        target.write_text("def foo():\n    return 1\n")
        payload = {"path": "example.py", "find": "return 99", "replace": "return 0"}
        with pytest.raises(ValueError, match="not found verbatim"):
            json_payload_to_diff(payload, str(tmp_path))

    def test_raises_on_identical_find_replace(self, tmp_path):
        target = tmp_path / "example.py"
        target.write_text("def foo():\n    return 1\n")
        payload = {"path": "example.py", "find": "return 1", "replace": "return 1"}
        with pytest.raises(ValueError, match="identical"):
            json_payload_to_diff(payload, str(tmp_path))

    def test_raises_on_missing_file(self, tmp_path):
        payload = {"path": "nonexistent.py", "find": "x", "replace": "y"}
        with pytest.raises(FileNotFoundError):
            json_payload_to_diff(payload, str(tmp_path))


# ---------------------------------------------------------------------------
# dry_run_patch on real v2 target files
# ---------------------------------------------------------------------------

V2_TARGETS = [
    (
        "v2/src/sys_quota.py",
        '"""Return current epoch seconds, optionally shifted for tests."""',
        '"""Return current epoch time in seconds, optionally shifted for tests."""',
    ),
    (
        "v2/src/sys_router.py",
        "MOCK_MODELS = {",
        "MOCK_MODELS = {  # registry",
    ),
    (
        "v2/src/sys_map.py",
        '"""sys-map: stateless AST repo map CLI (pure stdlib)."""',
        '"""sys-map: stateless read-only AST repo map CLI (pure stdlib)."""',
    ),
]


@pytest.mark.parametrize("rel_path,find_text,replace_text", V2_TARGETS)
def test_dry_run_patch_v2_targets(rel_path, find_text, replace_text):
    """patch --dry-run must succeed on a freshly generated diff for each target."""
    diff_text = _make_diff(rel_path, find_text, replace_text)

    # Structural validation first
    validate_unified_diff(diff_text)

    # Then dry-run with the real patch binary
    ok, msg = dry_run_patch(diff_text, str(REPO_ROOT))
    assert ok, f"patch --dry-run failed for {rel_path}: {msg}"


# ---------------------------------------------------------------------------
# parse_m3_response: Format 0 (diff fence) and Format 0b (JSON payload)
# ---------------------------------------------------------------------------

class TestParseMm3ResponseDiffFormats:
    def _valid_diff_text(self):
        return textwrap.dedent("""\
            --- a/v2/src/sys_quota.py
            +++ b/v2/src/sys_quota.py
            @@ -16,3 +16,3 @@
             def _now():
            -    \"\"\"Return current epoch seconds, optionally shifted for tests.\"\"\"
            +    \"\"\"Return current epoch time in seconds, optionally shifted for tests.\"\"\"
                 return time.time() + float(os.environ.get("ODY_MOCK_TIME_OFFSET_HOURS", 0)) * 3600
        """)

    def _minimal_m3_response(self, diff_text: str) -> str:
        return (
            f"```diff\n{diff_text}```\n\n"
            "TEST_FILE: tests/test_example.py\n"
            "TEST_CONTENT:\n"
            "def test_nothing():\n"
            "    assert True\n"
        )

    def test_parses_valid_diff_fence(self):
        from src.bg_implementer import parse_m3_response

        diff_text = self._valid_diff_text()
        response = self._minimal_m3_response(diff_text)
        result = parse_m3_response(response)

        assert result is not None
        assert result["file_path"] == "v2/src/sys_quota.py"
        assert result["unified_diff"] is not None
        assert len(result["edits"]) == 1
        assert result["edits"][0]["unified_diff"] is not None

    def test_rejects_malformed_diff_fence_falls_through(self):
        """A malformed diff fence is ignored; if no other format matches → None."""
        from src.bg_implementer import parse_m3_response

        bad_diff = textwrap.dedent("""\
            --- a/foo.py
            +++ b/foo.py
            @@ -1,99 +1,1 @@
            +only one line
        """)
        response = (
            f"```diff\n{bad_diff}```\n\n"
            "TEST_FILE: tests/test_example.py\n"
            "TEST_CONTENT:\n"
            "def test_nothing():\n"
            "    assert True\n"
        )
        result = parse_m3_response(response)
        # Malformed diff falls through; no other format → None
        assert result is None

    def test_parses_json_payload_fallback(self):
        from src.bg_implementer import parse_m3_response

        payload = json.dumps({
            "path": "v2/src/sys_quota.py",
            "find": "QUOTA_EXHAUSTED_EXIT = 75",
            "replace": "QUOTA_EXHAUSTED_EXIT = 75  # EX_TEMPFAIL",
        })
        response = (
            f"{payload}\n\n"
            "TEST_FILE: tests/test_example.py\n"
            "TEST_CONTENT:\n"
            "def test_nothing():\n"
            "    assert True\n"
        )
        result = parse_m3_response(response)

        assert result is not None
        assert result["file_path"] == "v2/src/sys_quota.py"
        assert "json_payload" in result["edits"][0]

    def test_cannot_patch_sentinel(self):
        from src.bg_implementer import parse_m3_response

        assert parse_m3_response("CANNOT_PATCH") is None
        assert parse_m3_response("  CANNOT_PATCH  ") is None
