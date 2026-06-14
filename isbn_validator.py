"""ISBN-10 and ISBN-13 validator.

Implements standard validation:
- ISBN-10: 10 characters, first 9 are digits, last is digit or 'X'/'x'.
  Sum of (10 - i) * digit for i in 0..9 must be divisible by 11.
- ISBN-13: 13 digits, weighted sum (alternating 1, 3) must be divisible by 10.
"""


def _clean(isbn):
    """Remove hyphens and spaces from the input string."""
    return isbn.replace('-', '').replace(' ', '')


def _is_valid_isbn10(isbn):
    """Validate an ISBN-10 string (must be exactly 10 chars after cleaning)."""
    if len(isbn) != 10:
        return False
    # First 9 chars must be digits
    if not isbn[:9].isdigit():
        return False
    # Last char must be digit, 'X', or 'x'
    last = isbn[9]
    if not (last.isdigit() or last == 'X' or last == 'x'):
        return False
    total = 0
    for i, ch in enumerate(isbn):
        if i == 9 and (ch == 'X' or ch == 'x'):
            value = 10
        else:
            value = int(ch)
        total += (10 - i) * value
    return total % 11 == 0


def _is_valid_isbn13(isbn):
    """Validate an ISBN-13 string (must be exactly 13 digits after cleaning)."""
    if len(isbn) != 13:
        return False
    if not isbn.isdigit():
        return False
    total = 0
    for i, ch in enumerate(isbn):
        digit = int(ch)
        if i % 2 == 0:
            total += digit
        else:
            total += digit * 3
    return total % 10 == 0


def is_valid_isbn(isbn):
    """Return True if `isbn` is a valid ISBN-10 or ISBN-13.

    Accepts strings with hyphens or spaces. Non-string inputs return False.
    """
    if not isinstance(isbn, str):
        return False
    cleaned = _clean(isbn)
    if len(cleaned) == 10:
        return _is_valid_isbn10(cleaned)
    if len(cleaned) == 13:
        return _is_valid_isbn13(cleaned)
    return False


if __name__ == '__main__':
    samples = [
        '0306406152',
        '123456789X',
        '9780306406157',
        '978-0-306-40615-7',
        '1234567890',
        'not-an-isbn',
        '',
    ]
    for s in samples:
        print(f"{s!r:30} -> {is_valid_isbn(s)}")