"""T9 multi-tap keypad encoder.

Converts text into the sequence of key presses required on a classic
multi-tap mobile phone keypad. Letters are normalised to lowercase
before encoding, spaces map to 0, and digits are passed through
unchanged. Characters that have no keypad representation are skipped.
"""


def t9_keypad_encoder(text):
    """Return the multi-tap keypad encoding of *text*.

    Parameters
    ----------
    text : str
        Input text to encode. May contain letters, digits, spaces and
        punctuation. Uppercase letters are normalised to lowercase.

    Returns
    -------
    str
        Concatenated keypad key presses. Empty string in -> empty
        string out.
    """
    if not text:
        return ""

    keypad = {
        'a': '2', 'b': '22', 'c': '222',
        'd': '3', 'e': '33', 'f': '333',
        'g': '4', 'h': '44', 'i': '444',
        'j': '5', 'k': '55', 'l': '555',
        'm': '6', 'n': '66', 'o': '666',
        'p': '7', 'q': '77', 'r': '777', 's': '7777',
        't': '8', 'u': '88', 'v': '888',
        'w': '9', 'x': '99', 'y': '999', 'z': '9999',
    }

    result = []
    for char in text.lower():
        if char in keypad:
            result.append(keypad[char])
        elif char == ' ':
            result.append('0')
        elif char.isdigit():
            result.append(char)
        # Any other character is silently ignored.

    return ''.join(result)