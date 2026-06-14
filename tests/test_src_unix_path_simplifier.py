"""Pytest tests for ``src.src_unix_path_simplifier.simplify_path``."""
import os
import sys

# Make the ``src`` directory importable regardless of where pytest is run.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))

from src_unix_path_simplifier import simplify_path


def test_simple_absolute_path_is_unchanged():
    assert simplify_path("/home/user/documents") == "/home/user/documents"


def test_current_directory_components_are_removed():
    assert simplify_path("/a/./b/./c") == "/a/b/c"


def test_consecutive_slashes_are_collapsed():
    assert simplify_path("/a//b///c") == "/a/b/c"


def test_single_parent_directory_is_resolved():
    assert simplify_path("/a/b/../c") == "/a/c"


def test_multiple_parent_directories_are_resolved():
    assert simplify_path("/a/b/c/../../d") == "/a/d"


def test_trailing_slash_is_removed():
    assert simplify_path("/home/user/") == "/home/user"


def test_cannot_traverse_above_root_with_trailing_slash():
    # ".." at the root is dropped, leaving an empty stack -> root.
    assert simplify_path("/../") == "/"


def test_cannot_traverse_above_root_with_filename():
    # Even repeated ".." cannot escape the root; the remaining
    # component stays at the top level.
    assert simplify_path("/../../a") == "/a"


def test_complex_mixed_path():
    # Combines '.', '..', and duplicate slashes in one input.
    assert simplify_path("/a/./b/../../c/") == "/c"


def test_root_path_stays_root():
    assert simplify_path("/") == "/"


def test_deep_parent_traversal_collapses_to_root():
    # Walking up from /a/b/c more levels than exist should leave us at "/".
    assert simplify_path("/a/b/c/../../../") == "/"


def test_mixed_components_full_simplification():
    assert simplify_path("/a//./b/../c/./d//") == "/a/c/d"


def test_empty_string_input_returns_root():
    # An empty input is treated as the filesystem root.
    assert simplify_path("") == "/"