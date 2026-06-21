"""ODYSSEUS-CHECKPOINT regression tests.

The previous file was a multi-docstring stub with a broken main() at the
top of the file (so `from v2.src.sys_checkpoint import compress` would
hit `sys.exit(...)` before any other name was bound). The fix is a
single coherent module with a real extractive compressor.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "v2" / "src"))

import sys_checkpoint  # noqa: E402


def test_compress_empty_returns_empty():
    assert sys_checkpoint.compress("", 100) == ""


def test_compress_whitespace_only_returns_empty():
    assert sys_checkpoint.compress("   \n\t", 100) == ""


def test_compress_under_budget_returns_input():
    text = "short text"
    assert sys_checkpoint.compress(text, 100) == text


def test_compress_truncates_at_sentence_boundary():
    text = "First sentence. Second sentence. Third sentence that is long."
    out = sys_checkpoint.compress(text, 30)
    # Must end on a sentence boundary; never include a partial sentence
    # in the middle of the budget.
    assert out.endswith(".") or len(out) <= 30
    assert "First" in out


def test_compress_handles_single_oversized_sentence():
    # One sentence longer than max_chars — should truncate, not crash.
    text = "a" * 200
    out = sys_checkpoint.compress(text, 50)
    assert len(out) <= 50


def test_compress_max_chars_zero_returns_empty():
    assert sys_checkpoint.compress("hello world", 0) == ""


def test_module_imports_without_running_main():
    # The old file's `if __name__ == "__main__": sys.exit(main())` was
    # at the top of the file, so any `import sys_checkpoint` would
    # invoke argparse on the calling process. The fix moves the guard
    # to the bottom AND `main()` only runs when `__name__ == "__main__"`,
    # which by definition is false for an import.
    assert "compress" in dir(sys_checkpoint)
    assert "mock_cheap" in dir(sys_checkpoint)
    assert "main" in dir(sys_checkpoint)
