"""Tests for :mod:`src.src_parser`."""

import os
import sys

# Make the project root importable so ``from src.src_parser ...`` works
# regardless of where pytest is invoked from.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir)
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from src.src_parser import parse_source


# ---------------------------------------------------------------------------
# Basic structural tests
# ---------------------------------------------------------------------------

def test_empty_source_returns_empty_structure():
    result = parse_source("")
    assert isinstance(result, dict)
    assert result["docstring"] is None
    assert result["imports"] == []
    assert result["functions"] == []
    assert result["classes"] == []
    assert result["line_count"] == 0
    assert result["char_count"] == 0
    assert "error" not in result


def test_whitespace_only_source_is_handled_gracefully():
    result = parse_source("   \n\n  \n")
    assert result["imports"] == []
    assert result["functions"] == []
    assert result["classes"] == []
    assert "error" not in result


# ---------------------------------------------------------------------------
# Docstring handling
# ---------------------------------------------------------------------------

def test_module_docstring_is_extracted():
    source = '"""Module docstring."""\n'
    result = parse_source(source)
    assert result["docstring"] == "Module docstring."


# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

def test_parses_import_statements():
    source = (
        "import os\n"
        "import sys\n"
        "from collections import OrderedDict\n"
        "from . import helper\n"
    )
    result = parse_source(source)
    assert "os" in result["imports"]
    assert "sys" in result["imports"]
    assert "collections.OrderedDict" in result["imports"]
    assert "helper" in result["imports"]
    assert len(result["imports"]) == 4


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def test_parses_function_with_arguments():
    source = (
        "def greet(name, greeting='hi'):\n"
        "    \"\"\"Greet.\"\"\"\n"
        "    return f'{greeting}, {name}'\n"
    )
    result = parse_source(source)
    assert len(result["functions"]) == 1
    fn = result["functions"][0]
    assert fn["name"] == "greet"
    assert fn["line"] == 1
    assert fn["args"] == ["name", "greeting"]
    # Plain (non-async) functions should not carry the ``async`` flag.
    assert "async" not in fn


def test_parses_async_function():
    source = "async def fetch(url):\n    pass\n"
    result = parse_source(source)
    assert len(result["functions"]) == 1
    fn = result["functions"][0]
    assert fn["name"] == "fetch"
    assert fn["args"] == ["url"]
    assert fn.get("async") is True


def test_parses_nested_functions():
    source = (
        "def outer():\n"
        "    def inner():\n"
        "        pass\n"
        "    return inner\n"
    )
    result = parse_source(source)
    names = [f["name"] for f in result["functions"]]
    assert "outer" in names
    assert "inner" in names


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

def test_parses_classes_with_bases():
    source = (
        "class Animal:\n"
        "    pass\n"
        "\n"
        "class Dog(Animal):\n"
        "    \"\"\"A dog.\"\"\"\n"
        "    pass\n"
    )
    result = parse_source(source)
    assert len(result["classes"]) == 2

    animal = result["classes"][0]
    assert animal["name"] == "Animal"
    assert animal["bases"] == []
    assert animal["line"] == 1

    dog = result["classes"][1]
    assert dog["name"] == "Dog"
    assert dog["bases"] == ["Animal"]
    assert dog["line"] == 4


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_syntax_error_is_captured_in_result():
    result = parse_source("def broken(:\n")
    assert "error" in result
    assert isinstance(result["error"], str)
    # Even when parsing fails, the structural lists are still present.
    assert result["functions"] == []
    assert result["classes"] == []


def test_non_string_input_raises_type_error():
    with pytest.raises(TypeError):
        parse_source(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_source(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        parse_source(["def foo(): pass"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Line / character counts
# ---------------------------------------------------------------------------

def test_line_and_char_counts():
    source = "a\nb\nc\n"
    result = parse_source(source)
    assert result["line_count"] == 3
    assert result["char_count"] == 6


def test_single_line_source_counts_as_one_line():
    result = parse_source("x = 1")
    assert result["line_count"] == 1
    assert result["char_count"] == 5


# ---------------------------------------------------------------------------
# End-to-end test using a realistic module
# ---------------------------------------------------------------------------

def test_full_module_is_parsed_end_to_end():
    source = (
        '"""Example module."""\n'
        "\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def load(path):\n"
        "    return Path(path).read_text()\n"
        "\n"
        "class Loader:\n"
        "    def __init__(self, path):\n"
        "        self.path = path\n"
    )
    result = parse_source(source)

    assert result["docstring"] == "Example module."
    assert "json" in result["imports"]
    assert "pathlib.Path" in result["imports"]

    function_names = [f["name"] for f in result["functions"]]
    assert "load" in function_names
    assert "__init__" in function_names

    class_names = [c["name"] for c in result["classes"]]
    assert "Loader" in class_names
    assert "error" not in result