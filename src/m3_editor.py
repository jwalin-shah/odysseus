"""
m3_editor.py — M3-powered code editor via SEARCH/REPLACE blocks.

Gives M3 (free TokenRouter model) actual write capability: M3 outputs structured
SEARCH/REPLACE blocks, Python applies them. Near-zero cost for straightforward edits.

Edit block format M3 produces:
    <<<SEARCH path/to/file.py
    exact text to find
    ===
    replacement text
    >>>END

Usage:
    from src.m3_editor import m3_edit
    result = m3_edit("add a docstring to greet()", files_context=["src/foo.py"])

    # CLI
    python3 src/m3_editor.py "fix the off-by-one in range()" src/algo.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

_BLOCK_RE = re.compile(
    r"<<<SEARCH\s+(\S+)\n(.*?)\n===\n(.*?)\n>>>END",
    re.DOTALL,
)

_M3_SYSTEM = """\
You are a code editor. When asked to make changes, output SEARCH/REPLACE blocks in this exact format:

<<<SEARCH path/to/file
[exact text from the file to replace — must match character-for-character including whitespace]
===
[new replacement text]
>>>END

Rules:
- SEARCH text must match the file exactly (whitespace and indentation included)
- One block per logical change; multiple blocks allowed
- No prose before the first block or between blocks
- After all >>>END markers you may add a brief explanation of what changed and why
- If you cannot make the change safely (e.g. cannot find the exact text), explain why after the blocks\
"""

_MAX_FILE_LINES = 200


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_edit_blocks(text: str) -> list[dict]:
    """Parse M3's SEARCH/REPLACE output into structured edit dicts.

    Returns list of {"file": str, "search": str, "replace": str}.
    """
    blocks = []
    for match in _BLOCK_RE.finditer(text):
        blocks.append({
            "file": match.group(1).strip(),
            "search": match.group(2),
            "replace": match.group(3),
        })
    return blocks


# ---------------------------------------------------------------------------
# Applier
# ---------------------------------------------------------------------------

def apply_edits(
    blocks: list[dict],
    base_dir: Optional[str] = None,
    dry_run: bool = False,
) -> list[dict]:
    """Apply SEARCH/REPLACE blocks to files on disk.

    Args:
        blocks:   Output of parse_edit_blocks().
        base_dir: Resolve relative paths against this directory (default: cwd).
        dry_run:  Check matches without writing anything.

    Returns list of {"file", "status": "applied"/"not_found"/"error", "detail"}.
    """
    base = Path(base_dir or os.getcwd())
    results = []

    for block in blocks:
        file_path = Path(block["file"])
        if not file_path.is_absolute():
            file_path = base / file_path

        try:
            if not file_path.exists():
                results.append({
                    "file": block["file"],
                    "status": "not_found",
                    "detail": f"File does not exist: {file_path}",
                })
                continue

            original = file_path.read_text(encoding="utf-8")
            search = block["search"]

            if search not in original:
                # Try stripping trailing whitespace per line (common M3 quirk)
                search_stripped = "\n".join(l.rstrip() for l in search.splitlines())
                original_stripped = "\n".join(l.rstrip() for l in original.splitlines())
                if search_stripped in original_stripped:
                    # Rebuild with stripped version
                    idx = original_stripped.index(search_stripped)
                    # Map back to original (approximate — line-level only)
                    orig_lines = original.splitlines(keepends=True)
                    srch_lines = search.splitlines()
                    # Find the matching line range
                    for i in range(len(orig_lines) - len(srch_lines) + 1):
                        chunk = "".join(orig_lines[i:i + len(srch_lines)])
                        if "\n".join(l.rstrip() for l in chunk.splitlines()) == search_stripped:
                            before = "".join(orig_lines[:i])
                            after = "".join(orig_lines[i + len(srch_lines):])
                            new_content = before + block["replace"] + "\n" + after
                            if not dry_run:
                                file_path.write_text(new_content, encoding="utf-8")
                            results.append({
                                "file": block["file"],
                                "status": "applied" if not dry_run else "would_apply",
                                "detail": "matched after stripping trailing whitespace",
                            })
                            break
                    else:
                        results.append({
                            "file": block["file"],
                            "status": "not_found",
                            "detail": "SEARCH text not found in file (even after whitespace normalisation)",
                        })
                else:
                    results.append({
                        "file": block["file"],
                        "status": "not_found",
                        "detail": "SEARCH text not found in file",
                    })
                continue

            new_content = original.replace(search, block["replace"], 1)
            if not dry_run:
                file_path.write_text(new_content, encoding="utf-8")

            results.append({
                "file": block["file"],
                "status": "applied" if not dry_run else "would_apply",
                "detail": f"replaced {len(search)} chars with {len(block['replace'])} chars",
            })

        except Exception as exc:
            results.append({
                "file": block["file"],
                "status": "error",
                "detail": str(exc),
            })

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def m3_edit(
    prompt: str,
    files_context: Optional[list[str]] = None,
    dry_run: bool = False,
    base_dir: Optional[str] = None,
) -> dict:
    """Ask M3 to edit code, then apply the resulting SEARCH/REPLACE blocks.

    Args:
        prompt:        Natural-language edit instruction.
        files_context: Up to 3 file paths to include as context for M3.
        dry_run:       Parse and check blocks but don't write files.
        base_dir:      Base directory for resolving relative file paths.

    Returns:
        {
          "response": raw M3 output,
          "edits_attempted": int,
          "edits_applied": int,
          "results": [{"file", "status", "detail"}, ...],
        }
    """
    # Build context from files
    context_parts = []
    if files_context:
        for fpath in (files_context or [])[:3]:
            p = Path(fpath)
            if not p.is_absolute() and base_dir:
                p = Path(base_dir) / p
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
                snippet = "\n".join(lines[:_MAX_FILE_LINES])
                if len(lines) > _MAX_FILE_LINES:
                    snippet += f"\n... ({len(lines) - _MAX_FILE_LINES} more lines)"
                context_parts.append(f"<file path=\"{fpath}\">\n{snippet}\n</file>")
            except Exception as exc:
                context_parts.append(f"<file path=\"{fpath}\" error=\"{exc}\" />")

    full_prompt = prompt
    if context_parts:
        full_prompt = "\n".join(context_parts) + "\n\n" + prompt

    # Call M3
    sys.path.insert(0, str(Path(__file__).parent))
    from m3 import complete as m3_complete  # noqa: PLC0415

    raw = m3_complete(full_prompt, system=_M3_SYSTEM, max_tokens=4096, timeout=120)

    # Strip <think> blocks (M3 reasoning output)
    if "</think>" in raw:
        raw_clean = raw.split("</think>", 1)[1].strip()
    else:
        raw_clean = raw

    blocks = parse_edit_blocks(raw_clean)
    results = apply_edits(blocks, base_dir=base_dir, dry_run=dry_run) if blocks else []

    applied = sum(1 for r in results if r["status"] in ("applied", "would_apply"))

    return {
        "response": raw_clean,
        "edits_attempted": len(blocks),
        "edits_applied": applied,
        "results": results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(prog="m3_editor", description=__doc__.splitlines()[1].strip())
    p.add_argument("prompt", help="Edit instruction in plain English")
    p.add_argument("files", nargs="*", help="File(s) to include as context (up to 3)")
    p.add_argument("--dry-run", action="store_true", help="Check edits without writing")
    p.add_argument("--base-dir", default=os.getcwd(), help="Base directory for file paths")
    args = p.parse_args(argv)

    result = m3_edit(
        args.prompt,
        files_context=args.files or None,
        dry_run=args.dry_run,
        base_dir=args.base_dir,
    )

    print(f"\nM3 response:\n{result['response']}\n")
    print(f"Edits: {result['edits_applied']}/{result['edits_attempted']} applied")
    for r in result["results"]:
        print(f"  [{r['status']}] {r['file']}: {r['detail']}")

    return 0 if result["edits_attempted"] == 0 or result["edits_applied"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
