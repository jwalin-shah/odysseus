def number_to_words(n: int) -> str:
    """Convert an integer (0-999,999,999) to its English word representation."""
    if n < 0 or n >= 1_000_000_000:
        raise ValueError("n must be between 0 and 999,999,999")

    ones = [
        '', 'one', 'two', 'three', 'four', 'five',
        'six', 'seven', 'eight', 'nine'
    ]
    teens = [
        'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen',
        'sixteen', 'seventeen', 'eighteen', 'nineteen'
    ]
    tens = [
        '', '', 'twenty', 'thirty', 'forty', 'fifty',
        'sixty', 'seventy', 'eighty', 'ninety'
    ]

    if n == 0:
        return 'zero'

    def under_thousand(num):
        if num == 0:
            return ''
        if num < 10:
            return ones[num]
        if num < 20:
            return teens[num - 10]
        if num < 100:
            if num % 10 == 0:
                return tens[num // 10]
            return tens[num // 10] + ' ' + ones[num % 10]
        if num % 100 == 0:
            return ones[num // 100] + ' hundred'
        return ones[num // 100] + ' hundred ' + under_thousand(num % 100)

    remainder_words = under_thousand(n % 1000)
    thousands = n // 1000

    if thousands == 0:
        return remainder_words

    thousands_words = under_thousand(thousands) + ' thousand'
    if remainder_words:
        return thousands_words + ' ' + remainder_words
    return thousands_words