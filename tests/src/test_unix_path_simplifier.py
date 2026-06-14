"""
Tests for ``src.unix_path_simplifier.simplify_path``.

The test module adds the repository root to ``sys.path`` so that the
``src`` package is importable when pytest is invoked from the project
root (e.g. ``pytest tests/src/test_unix_path_simplifier.py``).
"""

import os
import sys

# Make the project root importable so ``from src.unix_path_simplifier
# import simplify_path`` works regardless of where pytest is launched.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest  # noqa: E402  (import after sys.path manipulation)

from src.unix_path_simplifier import simplify_path  # noqa: E402


class TestSimplifyPathBasics:
    """Sanity checks for the most common cases."""

    def test_root_path_is_unchanged(self):
        """``"/"`` simplifies to itself."""
        assert simplify_path("/") == "/"

    def test_trailing_slash_is_removed(self):
        """A trailing slash on a non-root path is dropped."""
        assert simplify_path("/home/") == "/home"

    def test_simple_absolute_path(self):
        """A clean absolute path passes through unchanged."""
        assert simplify_path("/a/b/c") == "/a/b/c"

    def test_empty_string_collapses_to_root(self):
        """An empty string is treated as the root directory."""
        assert simplify_path("") == "/"


class TestSimplifyPathDotAndDotDot:
    """Resolution rules for ``.`` and ``..``."""

    def test_dot_is_ignored(self):
        """``.`` is a no-op and disappears from the canonical path."""
        assert simplify_path("/a/./b") == "/a/b"

    def test_double_dot_pops_one_level(self):
        """``..`` moves one directory up."""
        assert simplify_path("/a/b/..") == "/a"

    def test_multiple_double_dots(self):
        """Repeated ``..`` climb multiple levels."""
        assert simplify_path("/a/b/c/../../d") == "/a/d"

    def test_double_dot_above_root_stays_at_root(self):
        """Trying to go above the root keeps us at the root."""
        assert simplify_path("/../") == "/"
        assert simplify_path("/../../../") == "/"

    def test_complex_mixed_operations(self):
        """The classic LeetCode example combining ``.`` and ``..``."""
        assert simplify_path("/a/./b/../../c/") == "/c"

    def test_mixed_dot_and_dotdot(self):
        """Interleaved ``.`` and ``..`` segments resolve correctly."""
        assert simplify_path("/foo/./bar/../baz/") == "/foo/baz"

    def test_dots_inside_longer_path(self):
        """Dots interleaved with a longer path collapse correctly."""
        assert simplify_path("/a/b/c/./../../g/") == "/a/g"


class TestSimplifyPathSlashes:
    """Handling of consecutive and trailing slashes."""

    def test_consecutive_slashes_collapse(self):
        """Multiple ``/`` in a row behave like a single ``/``."""
        assert simplify_path("/home//foo/") == "/home/foo"

    def test_consecutive_slashes_in_the_middle(self):
        """``//`` in the middle of a path is collapsed."""
        assert simplify_path("/a//b/") == "/a/b"

    def test_trailing_slash_removed_after_resolution(self):
        """A trailing slash disappears after the path is simplified."""
        assert simplify_path("/a/b/c/") == "/a/b/c"

    def test_leading_double_slash_collapsed(self):
        """``//`` at the start collapses to a single ``/``."""
        assert simplify_path("//foo/bar") == "/foo/bar"


class TestSimplifyPathReturnType:
    """Make sure the function always returns a well-formed string."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("/", "/"),
            ("/foo", "/foo"),
            ("/foo/bar", "/foo/bar"),
            ("/foo/..", "/"),
            ("/foo/./bar/", "/foo/bar"),
            ("/a/b/c/./../../g/", "/a/g"),
        ],
    )
    def test_parametrized_canonical_examples(self, raw, expected):
        """A broad set of inputs all produce the expected canonical form."""
        assert simplify_path(raw) == expected

    def test_result_always_starts_with_slash(self):
        """The simplified path is always absolute."""
        for raw in ("/", "/a", "/a/..", "/a/./b/"):
            result = simplify_path(raw)
            assert result.startswith("/")

    def test_result_has_no_trailing_slash_unless_root(self):
        """A non-root simplified path never ends with ``/``."""
        for raw in ("/a/", "/a/b/", "/a/./b/", "/a/../b/"):
            result = simplify_path(raw)
            if result != "/":
                assert not result.endswith("/")