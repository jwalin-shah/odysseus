import sys
import os
import pytest

# Ensure both repo root and src directory are on sys.path
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'src'))

from missions_recursive_josephus_survivor_locator import josephus_survivor


def test_josephus_survivor_7_3_returns_3():
	"""AC1: josephus_survivor(7, 3) returns the integer 3."""
	assert josephus_survivor(7, 3) == 3


def test_josephus_survivor_1_1_returns_0():
	"""AC2: josephus_survivor(1, 1) returns the integer 0."""
	assert josephus_survivor(1, 1) == 0


def test_josephus_survivor_10_2_returns_4():
	"""AC3: josephus_survivor(10, 2) returns the integer 4."""
	assert josephus_survivor(10, 2) == 4


def test_josephus_survivor_n_zero_raises_value_error():
	"""EC1: josephus_survivor(0, k) raises ValueError (no people to eliminate)."""
	with pytest.raises(ValueError):
		josephus_survivor(0, 1)


def test_josephus_survivor_negative_n_raises_value_error():
	"""EC2: josephus_survivor(-1, k) raises ValueError."""
	with pytest.raises(ValueError):
		josephus_survivor(-1, 1)


def test_josephus_survivor_k_zero_raises_value_error():
	"""EC3: josephus_survivor(n, 0) raises ValueError (invalid step)."""
	with pytest.raises(ValueError):
		josephus_survivor(5, 0)


def test_josephus_survivor_n_1_k_5_returns_0():
	"""EC4: josephus_survivor(1, 5) returns 0 (sole person survives any step)."""
	assert josephus_survivor(1, 5) == 0
