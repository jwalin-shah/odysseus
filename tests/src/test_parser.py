import os
import sys

# Make the project root importable so `from src.parser import parse` works
# when pytest is invoked from the repository root.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.parser import parse  # noqa: E402


class TestParseIni:
    def test_basic_sections(self):
        text = (
            "[sec1]\n"
            "a = 1\n"
            "b = 2\n"
            "[sec2]\n"
            "c = 3\n"
        )
        assert parse(text) == {
            "sec1": {"a": "1", "b": "2"},
            "sec2": {"c": "3"},
        }

    def test_comments_and_blank_lines(self):
        text = (
            "; leading semicolon comment\n"
            "# leading hash comment\n"
            "\n"
            "[sec]\n"
            "; comment inside section\n"
            "a = 1\n"
            "\n"
            "b = 2\n"
            "# trailing-style comment\n"
        )
        assert parse(text) == {"sec": {"a": "1", "b": "2"}}

    def test_repeated_section_merges_entries(self):
        text = (
            "[sec]\n"
            "a = 1\n"
            "[other]\n"
            "c = 3\n"
            "[sec]\n"
            "b = 2\n"
        )
        assert parse(text) == {
            "sec": {"a": "1", "b": "2"},
            "other": {"c": "3"},
        }

    def test_default_section_for_pre_section_keys(self):
        text = (
            "a = 1\n"
            "b = 2\n"
            "[sec]\n"
            "c = 3\n"
        )
        assert parse(text) == {
            "default": {"a": "1", "b": "2"},
            "sec": {"c": "3"},
        }

    def test_empty_input_returns_empty_dict(self):
        assert parse("") == {}

    def test_value_containing_equals_sign(self):
        text = (
            "[sec]\n"
            "url = http://example.com?a=1&b=2\n"
        )
        assert parse(text) == {
            "sec": {"url": "http://example.com?a=1&b=2"},
        }

    def test_whitespace_around_keys_and_values_is_stripped(self):
        text = (
            "[sec]\n"
            "  key1   =   value1  \n"
            "\tkey2\t=\tvalue2\t\n"
        )
        assert parse(text) == {
            "sec": {"key1": "value1", "key2": "value2"},
        }