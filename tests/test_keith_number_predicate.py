from keith_number_predicate import keith_number_predicate


def test_14_is_keith():
    """14 is a well-known Keith number: 1, 4, 5, 9, 14"""
    assert keith_number_predicate(14) is True


def test_19_is_keith():
    """19 is a Keith number: 1, 9, 10, 19"""
    assert keith_number_predicate(19) is True


def test_28_is_keith():
    """28 is a Keith number: 2, 8, 10, 18, 28"""
    assert keith_number_predicate(28) is True


def test_47_is_keith():
    """47 is a Keith number: 4, 7, 11, 18, 29, 47"""
    assert keith_number_predicate(47) is True


def test_61_is_keith():
    """61 is a Keith number: 6, 1, 7, 8, 15, 23, 38, 61"""
    assert keith_number_predicate(61) is True


def test_75_is_keith():
    """75 is a Keith number: 7, 5, 12, 17, 29, 46, 75"""
    assert keith_number_predicate(75) is True


def test_197_is_keith():
    """197 is a Keith number: 1, 9, 7, 17, 33, 57, 107, 197"""
    assert keith_number_predicate(197) is True


def test_742_is_keith():
    """742 is a Keith number: 7, 4, 2, 13, 19, 34, 66, 119, 219, 404, 742"""
    assert keith_number_predicate(742) is True


def test_1537_is_keith():
    """1537 is a Keith number: 1,5,3,7,16,31,57,111,215,414,797,1537"""
    assert keith_number_predicate(1537) is True


def test_2208_is_keith():
    """2208 is a Keith number: 2,2,0,8,12,22,42,84,160,308,594,1146,2208"""
    assert keith_number_predicate(2208) is True


def test_known_keith_numbers():
    """A list of verified Keith numbers should all return True."""
    known_keith = [14, 19, 28, 47, 61, 75, 197, 742, 1537, 2208]
    for n in known_keith:
        assert keith_number_predicate(n) is True, f"{n} should be a Keith number"


def test_non_keith_numbers():
    """Numbers that are not Keith numbers should return False."""
    non_keith = [10, 11, 12, 13, 15, 16, 17, 18, 20, 100, 1000, 1103]
    for n in non_keith:
        assert keith_number_predicate(n) is False, f"{n} should not be a Keith number"


def test_single_digit_not_keith():
    """Single digit numbers are not Keith numbers."""
    for n in range(1, 10):
        assert keith_number_predicate(n) is False, f"{n} should not be a Keith number"


def test_zero_and_negative():
    """Zero and negative numbers are not Keith numbers."""
    assert keith_number_predicate(0) is False
    assert keith_number_predicate(-1) is False
    assert keith_number_predicate(-100) is False