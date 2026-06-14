"""Tests for :mod:`string_missions_pascal_to_snake`."""

from __future__ import annotations

import os
import sys

# Make the ``src`` directory importable when the tests are run from
# the project root without installing the package.
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, os.pardir, "src"))

import pytest

from string_missions_pascal_to_snake import string_missions_pascal_to_snake


class TestPascalToSnake:
    """Tests for :func:`string_missions_pascal_to_snake`."""

    def test_basic_pascal_case(self):
        assert string_missions_pascal_to_snake("PascalCase") == "pascal_case"

    def test_camel_case(self):
        assert string_missions_pascal_to_snake("camelCase") == "camel_case"

    def test_empty_string(self):
        assert string_missions_pascal_to_snake("") == ""

    def test_single_uppercase_letter(self):
        assert string_missions_pascal_to_snake("A") == "a"

    def test_single_lowercase_letter(self):
        assert string_missions_pascal_to_snake("a") == "a"

    def test_all_lowercase_is_preserved(self):
        assert string_missions_pascal_to_snake("hello") == "hello"

    def test_all_uppercase_acronym(self):
        assert string_missions_pascal_to_snake("ABC") == "abc"

    def test_acronym_followed_by_word(self):
        assert (
            string_missions_pascal_to_snake("HTTPSConnection")
            == "https_connection"
        )

    def test_xml_http_request(self):
        assert (
            string_missions_pascal_to_snake("XMLHttpRequest")
            == "xml_http_request"
        )

    def test_already_snake_case_is_preserved(self):
        assert (
            string_missions_pascal_to_snake("already_snake_case")
            == "already_snake_case"
        )

    def test_lowercase_with_trailing_uppercase(self):
        assert string_missions_pascal_to_snake("testA") == "test_a"

    def test_lowercase_followed_by_acronym(self):
        assert string_missions_pascal_to_snake("testAB") == "test_ab"

    def test_digit_before_uppercase_inserts_boundary(self):
        assert string_missions_pascal_to_snake("Hello2World") == "hello2_world"

    def test_existing_underscore_and_digit_are_kept(self):
        assert string_missions_pascal_to_snake("Version1_0") == "version1_0"

    def test_multiple_short_words(self):
        assert (
            string_missions_pascal_to_snake("ThisIsATest")
            == "this_is_a_test"
        )

    def test_leading_underscore_is_preserved(self):
        assert (
            string_missions_pascal_to_snake("_privateField")
            == "_private_field"
        )

    def test_non_string_input_raises_type_error(self):
        with pytest.raises(TypeError):
            string_missions_pascal_to_snake(123)  # type: ignore[arg-type]

    def test_none_input_raises_type_error(self):
        with pytest.raises(TypeError):
            string_missions_pascal_to_snake(None)  # type: ignore[arg-type]

    def test_list_input_raises_type_error(self):
        with pytest.raises(TypeError):
            string_missions_pascal_to_snake(["PascalCase"])  # type: ignore[arg-type]