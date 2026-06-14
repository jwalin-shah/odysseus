def keith_number_predicate(n):
    """Return True if n is a Keith number, False otherwise.

    A Keith number is a number that appears in a recurrence sequence
    where the initial terms are the digits of the number and each
    subsequent term is the sum of the previous k terms (where k is
    the number of digits of the original number).

    For example, 197 is a Keith number because starting with 1, 9, 7:
        1, 9, 7, 17, 33, 57, 107, 197, ...
    The number 197 appears in this sequence.
    """
    if n < 10:
        return False

    digits = [int(d) for d in str(n)]
    k = len(digits)

    sequence = digits[:]
    while sequence[-1] < n:
        next_val = sum(sequence[-k:])
        sequence.append(next_val)

    return sequence[-1] == n