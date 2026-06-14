"""Tests for :mod:`chemical_formula_parser`."""

import os
import sys

import pytest

# Ensure the project root is importable regardless of how pytest is invoked.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir)
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from chemical_formula_parser import parse_chemical_formula  # noqa: E402


class TestTrivialInputs:
    def test_none_returns_empty_dict(self):
        assert parse_chemical_formula(None) == {}

    def test_empty_string_returns_empty_dict(self):
        assert parse_chemical_formula("") == {}

    def test_whitespace_only_returns_empty_dict(self):
        assert parse_chemical_formula("   \t\n  ") == {}

    def test_non_string_input_raises_type_error(self):
        with pytest.raises(TypeError):
            parse_chemical_formula(123)
        with pytest.raises(TypeError):
            parse_chemical_formula(["H2O"])


class TestSimpleFormulas:
    def test_single_element_no_count(self):
        assert parse_chemical_formula("H") == {"H": 1}

    def test_single_element_with_count(self):
        assert parse_chemical_formula("H2") == {"H": 2}
        assert parse_chemical_formula("O2") == {"O": 2}
        assert parse_chemical_formula("N2") == {"N": 2}

    def test_water(self):
        assert parse_chemical_formula("H2O") == {"H": 2, "O": 1}

    def test_sodium_chloride(self):
        assert parse_chemical_formula("NaCl") == {"Na": 1, "Cl": 1}

    def test_carbon_dioxide(self):
        assert parse_chemical_formula("CO2") == {"C": 1, "O": 2}

    def test_glucose(self):
        assert parse_chemical_formula("C6H12O6") == {
            "C": 6,
            "H": 12,
            "O": 6,
        }

    def test_sulfuric_acid(self):
        assert parse_chemical_formula("H2SO4") == {
            "H": 2,
            "S": 1,
            "O": 4,
        }

    def test_two_letter_element_no_count(self):
        assert parse_chemical_formula("He") == {"He": 1}
        assert parse_chemical_formula("Fe") == {"Fe": 1}

    def test_two_letter_element_with_count(self):
        assert parse_chemical_formula("Fe2O3") == {"Fe": 2, "O": 3}

    def test_multidigit_subscript(self):
        assert parse_chemical_formula("C12H22O11") == {
            "C": 12,
            "H": 22,
            "O": 11,
        }


class TestParentheses:
    def test_parentheses_no_subscript(self):
        assert parse_chemical_formula("(OH)") == {"O": 1, "H": 1}

    def test_parentheses_with_subscript(self):
        assert parse_chemical_formula("(OH)2") == {"O": 2, "H": 2}

    def test_calcium_hydroxide(self):
        assert parse_chemical_formula("Ca(OH)2") == {
            "Ca": 1,
            "O": 2,
            "H": 2,
        }

    def test_aluminum_sulfate(self):
        assert parse_chemical_formula("Al2(SO4)3") == {
            "Al": 2,
            "S": 3,
            "O": 12,
        }

    def test_calcium_nitrate(self):
        assert parse_chemical_formula("Ca(NO3)2") == {
            "Ca": 1,
            "N": 2,
            "O": 6,
        }

    def test_ammonium_phosphate(self):
        assert parse_chemical_formula("(NH4)3PO4") == {
            "N": 3,
            "H": 12,
            "P": 1,
            "O": 4,
        }

    def test_ammonium_sulfate(self):
        assert parse_chemical_formula("(NH4)2SO4") == {
            "N": 2,
            "H": 8,
            "S": 1,
            "O": 4,
        }


class TestWhitespace:
    def test_spaces_inside_formula_are_ignored(self):
        assert parse_chemical_formula("H 2 O") == {"H": 2, "O": 1}

    def test_leading_and_trailing_whitespace(self):
        assert parse_chemical_formula("  C6H12O6  ") == {
            "C": 6,
            "H": 12,
            "O": 6,
        }

    def test_tabs_and_newlines(self):
        assert parse_chemical_formula("Ca\t(OH)2\n") == {
            "Ca": 1,
            "O": 2,
            "H": 2,
        }


class TestErrors:
    def test_invalid_character_raises(self):
        with pytest.raises(ValueError):
            parse_chemical_formula("H2O!")

    def test_unmatched_open_paren_raises(self):
        with pytest.raises(ValueError):
            parse_chemical_formula("Ca(OH")

    def test_unmatched_close_paren_raises(self):
        with pytest.raises(ValueError):
            parse_chemical_formula("Ca)OH")

    def test_leading_digit_raises(self):
        with pytest.raises(ValueError):
            parse_chemical_formula("2H2O")

    def test_lone_lowercase_raises(self):
        with pytest.raises(ValueError):
            parse_chemical_formula("h2o")