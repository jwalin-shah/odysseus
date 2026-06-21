"""ODYSSEUS-PIPELINE-RCE: regression tests for the run_tests ast gate.

The previous implementation concatenated LLM-supplied test strings directly
into a `python -c <script>` subprocess. An LLM hallucination of a test like
`assert __import__('os').system('rm -rf /') == 0` would have run unchanged.
The fix gates every test string through an ast whitelist:

  - must be a single line (no \\n / \\r)
  - must start with `assert `
  - must be a single expression (ast.parse in 'eval' mode)
  - no Import / ImportFrom / FunctionDef / ClassDef / Lambda
  - no Call to exec / eval / __import__ / compile / open / system / popen / subprocess
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make scripts/ importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from m3_pipeline import run_tests  # noqa: E402


# ── positives: must pass through ────────────────────────────────────────────


def test_valid_assert_passes_gate():
    ok, msg = run_tests(
        "odysseus", "fenwick_tree.py", ["assert FenwickTree(3).prefix_sum(0) == 0"]
    )
    assert ok, f"valid assert rejected: {msg}"


def test_multiple_valid_asserts_pass_gate():
    ok, msg = run_tests(
        "odysseus",
        "fenwick_tree.py",
        [
            "assert FenwickTree(3).n == 3",
            "assert 1 + 1 == 2",
        ],
    )
    assert ok, f"valid asserts rejected: {msg}"


def test_empty_test_list_passes():
    ok, msg = run_tests("odysseus", "fenwick_tree.py", [])
    assert ok and msg == "no tests"


# ── negatives: must be rejected at the gate (no subprocess launched) ────────


def test_dunder_import_rejected():
    ok, msg = run_tests(
        "odysseus",
        "fenwick_tree.py",
        ['assert __import__("os").system("echo pwn") == 0'],
    )
    assert not ok
    assert "dangerous call" in msg


def test_eval_rejected():
    ok, msg = run_tests(
        "odysseus", "fenwick_tree.py", ['assert eval("1+1") == 2']
    )
    assert not ok
    assert "dangerous call" in msg


def test_open_rejected():
    ok, msg = run_tests(
        "odysseus",
        "fenwick_tree.py",
        ['assert open("/etc/passwd") is not None'],
    )
    assert not ok
    assert "dangerous call" in msg


def test_multiline_rejected():
    ok, msg = run_tests(
        "odysseus", "fenwick_tree.py", ["assert True\nimport os"]
    )
    assert not ok
    assert "multi-line" in msg


def test_non_assertion_rejected():
    ok, msg = run_tests("odysseus", "fenwick_tree.py", ['print("hi")'])
    assert not ok
    assert "non-assertion" in msg


def test_lambda_rejected():
    ok, msg = run_tests(
        "odysseus", "fenwick_tree.py", ["assert (lambda: 1)() == 1"]
    )
    assert not ok
    assert "Lambda" in msg


def test_subprocess_call_rejected():
    ok, msg = run_tests(
        "odysseus",
        "fenwick_tree.py",
        ['assert subprocess.run(["ls"]) is not None'],
    )
    assert not ok
    assert "dangerous" in msg and "subprocess" in msg


def test_compile_call_rejected():
    ok, msg = run_tests(
        "odysseus", "fenwick_tree.py", ['assert compile("1", "<x>", "eval") is not None']
    )
    assert not ok
    assert "dangerous call" in msg
