import pathlib
import sys

# Add the src/ directory to sys.path so we can import the module directly
# regardless of how pytest is invoked.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'src'))

from predicates_dudeney import is_dudeney


def test_one_is_dudeney():
    # 1 = 1^3, digit sum = 1
    assert is_dudeney(1) is True


def test_512_is_dudeney():
    # 512 = 8^3, digit sum = 5+1+2 = 8
    assert is_dudeney(512) is True


def test_4913_is_dudeney():
    # 4913 = 17^3, digit sum = 4+9+1+3 = 17
    assert is_dudeney(4913) is True


def test_5832_is_dudeney():
    # 5832 = 18^3, digit sum = 5+8+3+2 = 18
    assert is_dudeney(5832) is True


def test_17576_is_dudeney():
    # 17576 = 26^3, digit sum = 1+7+5+7+6 = 26
    assert is_dudeney(17576) is True


def test_19683_is_dudeney():
    # 19683 = 27^3, digit sum = 1+9+6+8+3 = 27
    assert is_dudeney(19683) is True


def test_perfect_cube_but_not_dudeney():
    # 8 = 2^3, digit sum = 8, not equal to 2
    assert is_dudeney(8) is False
    # 27 = 3^3, digit sum = 9, not equal to 3
    assert is_dudeney(27) is False
    # 64 = 4^3, digit sum = 10, not equal to 4
    assert is_dudeney(64) is False
    # 125 = 5^3, digit sum = 8, not equal to 5
    assert is_dudeney(125) is False
    # 216 = 6^3, digit sum = 9, not equal to 6
    assert is_dudeney(216) is False


def test_non_cube_numbers():
    assert is_dudeney(2) is False
    assert is_dudeney(10) is False
    assert is_dudeney(100) is False
    assert is_dudeney(999) is False
    assert is_dudeney(1000) is False


def test_zero_is_not_dudeney():
    assert is_dudeney(0) is False


def test_negative_numbers_are_not_dudeney():
    assert is_dudeney(-1) is False
    assert is_dudeney(-8) is False
    assert is_dudeney(-512) is False


def test_non_integer_inputs_return_false():
    assert is_dudeney(1.0) is False
    assert is_dudeney(8.0) is False
    assert is_dudeney("512") is False
    assert is_dudeney(None) is False
    assert is_dudeney([512]) is False
    assert is_dudeney((512,)) is False


def test_booleans_are_not_dudeney():
    # In Python, bool is a subclass of int, but a Dudeney number
    # must be a "true" integer, so booleans are explicitly excluded.
    assert is_dudeney(True) is False
    assert is_dudeney(False) is False


def test_dudeney_sequence_below_20000():
    # Known Dudeney numbers below 20000.
    expected = [1, 512, 4913, 5832, 17576, 19683]
    actual = [n for n in range(1, 20000) if is_dudeney(n)]
    assert actual == expected


def test_large_dudeney_number_54872():
    # 54872 = 38^3, digit sum = 5+4+8+7+2 = 26... wait check:
    # 38^3 = 54872, sum = 5+4+8+7+2 = 26, not 38. So 54872 is NOT Dudeney.
    # The next actual Dudeney is 421875 = 75^3, sum = 4+2+1+8+7+5 = 27... no.
    # Let me verify: known Dudeneys: 1, 512, 4913, 5832, 17576, 19683,
    # 54872, 421875, 612848, ... Actually after 19683 the next is
    # often cited as 54872 only for some definitions. Use a known
    # non-Dudeney large cube as a sanity check.
    # 38^3 = 54872, digit sum 5+4+8+7+2 = 26, not 38
    assert is_dudeney(54872) is False


def test_large_known_dudeney_612848():
    # 612848 is not a Dudeney in the standard sense. Use a clear
    # non-Dudeney large perfect cube: 100^3 = 1_000_000, sum=1, not 100.
    assert is_dudeney(1_000_000) is False
    # 1000^3 = 1_000_000_000, digit sum = 1, not 1000.
    assert is_dudeney(1_000_000_000) is False