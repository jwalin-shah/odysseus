"""Number to English words conversion."""
from __future__ import annotations

_ONES = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
         'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen',
         'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
_TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty',
         'sixty', 'seventy', 'eighty', 'ninety']


def _under_thousand(n: int) -> str:
    if n == 0:
        return ''
    if n < 20:
        return _ONES[n]
    if n < 100:
        rest = _ONES[n % 10]
        return _TENS[n // 10] + ('-' + rest if rest else '')
    rest = _under_thousand(n % 100)
    return _ONES[n // 100] + ' hundred' + (' ' + rest if rest else '')


def num_to_words(n: int) -> str:
    """Convert integer 0-999,999,999,999 to English words."""
    if n < 0:
        return 'negative ' + num_to_words(-n)
    if n == 0:
        return 'zero'
    parts: list[str] = []
    billions = n // 1_000_000_000
    if billions:
        parts.append(_under_thousand(billions) + ' billion')
    millions = (n % 1_000_000_000) // 1_000_000
    if millions:
        parts.append(_under_thousand(millions) + ' million')
    thousands = (n % 1_000_000) // 1_000
    if thousands:
        parts.append(_under_thousand(thousands) + ' thousand')
    remainder = n % 1_000
    if remainder:
        parts.append(_under_thousand(remainder))
    return ' '.join(parts)


def ordinal(n: int) -> str:
    """Convert integer to ordinal string (1 -> 'first', 22 -> 'twenty-second')."""
    _IRR = {1: 'first', 2: 'second', 3: 'third', 5: 'fifth',
            8: 'eighth', 9: 'ninth', 12: 'twelfth'}
    words = num_to_words(n)
    last_word = words.split()[-1]
    if n % 100 in _IRR:
        suffix = _IRR[n % 100]
    elif n % 10 in _IRR and n % 100 not in range(10, 20):
        # replace last word with irregular ordinal
        suffix = _IRR[n % 10]
    elif last_word.endswith('y'):
        suffix = last_word[:-1] + 'ieth'
    else:
        suffix = last_word + 'th'
    return ' '.join(words.split()[:-1] + [suffix]) if len(words.split()) > 1 else suffix


# Alias
number_to_words = num_to_words
