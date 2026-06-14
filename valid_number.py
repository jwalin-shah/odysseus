def is_valid_number(s: str) -> bool:
    if not s:
        return False

    # States for the number state machine
    START = 0       # initial, nothing seen
    SIGN = 1        # saw + or -
    INT = 2         # reading integer digits
    DOT = 3         # saw decimal point, no fractional digits yet
    FRAC = 4        # reading fractional digits
    EXP = 5         # saw e/E
    EXP_SIGN = 6    # saw sign after e/E
    EXP_DIGIT = 7   # reading exponent digits

    state = START

    for c in s:
        if c.isdigit():
            if state in (START, SIGN):
                state = INT
            elif state in (DOT, FRAC):
                state = FRAC
            elif state in (EXP, EXP_SIGN):
                state = EXP_DIGIT
            # INT and EXP_DIGIT remain
        elif c in ('+', '-'):
            if state == START:
                state = SIGN
            elif state == EXP:
                state = EXP_SIGN
            else:
                return False
        elif c == '.':
            if state in (START, SIGN, INT):
                state = DOT
            else:
                return False
        elif c in ('e', 'E'):
            if state in (INT, FRAC):
                state = EXP
            else:
                return False
        else:
            return False

    # Accepting end states: must have consumed a valid number body
    return state in (INT, FRAC, DOT, EXP_DIGIT)