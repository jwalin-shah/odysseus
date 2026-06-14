import os
import sys

# Ensure the parent directory (project root) is on sys.path so we can
# import the implementation module regardless of where pytest is run.
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from dept_inventory import dept_inventory


def test_basic_aggregation():
    records = [
        ("Grocery", "apple", 10),
        ("Electronics", "laptop", 5),
    ]
    result = dept_inventory(records)
    assert result[("Grocery", "apple")] == 10
    assert result[("Electronics", "laptop")] == 5
    assert len(result) == 2


def test_duplicate_aggregation():
    records = [
        ("Grocery", "apple", 10),
        ("Grocery", "apple", 20),
    ]
    result = dept_inventory(records)
    assert result[("Grocery", "apple")] == 30


def test_empty_input():
    assert dept_inventory([]) == {}


def test_none_input():
    assert dept_inventory(None) == {}


def test_invalid_records_are_skipped():
    records = [
        ("Grocery", "apple", 10),
        ("Bad",),                       # too short
        "not a record",                 # wrong type
        ("Grocery", "pear", "five"),    # bad quantity -> skipped
        ("Grocery", "pear", 5),         # good
    ]
    result = dept_inventory(records)
    assert result[("Grocery", "apple")] == 10
    assert result[("Grocery", "pear")] == 5
    assert len(result) == 2


def test_numeric_string_quantities():
    records = [
        ("Grocery", "apple", "10"),
        ("Grocery", "apple", "20"),
    ]
    result = dept_inventory(records)
    assert result[("Grocery", "apple")] == 30


def test_integration_workflow():
    """Realistic end-to-end style workflow combining multiple departments."""
    records = [
        ("Grocery", "apple", 10),
        ("Grocery", "banana", 5),
        ("Electronics", "laptop", 2),
        ("Grocery", "apple", 20),       # duplicate of earlier
        ("Clothing", "shirt", 15),
        ("Electronics", "phone", 8),
    ]
    pairs = dept_inventory(records)
    assert pairs[("Grocery", "apple")] == 30
    assert pairs[("Grocery", "banana")] == 5
    assert pairs[("Electronics", "laptop")] == 2
    assert pairs[("Clothing", "shirt")] == 15
    assert pairs[("Electronics", "phone")] == 8
    assert len(pairs) == 5