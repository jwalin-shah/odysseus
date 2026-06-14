"""T9 multi-tap keypad encoder.

Encodes letters into the digit sequences you would type on a classic
mobile-phone keypad. A separator is inserted between two consecutive
characters that live on the same key so the encoding is unambiguous.

Keypad layout::

    2 -> ABC        6 -> MNO
    3 -> DEF        7 -> PQRS
    4 -> GHI        8 -> TUV
    5 -> JKL        9 -> WXYZ
    0 -> <space>
"""


T9_KEYMAP = {
    'a': '2',  'b': '22',  'c': '222',
    'd': '3',  'e': '33',  'f': '333',
    'g': '4',  'h': '44',  'i': '444',
    'j': '5',  'k': '55',  'l': '555',
    'm': '6',  'n': '66',  'o': '666',
    'p': '7',  'q': '77',  'r': '777',  's': '7777',
    't': '8',  'u': '88',  'v': '888',
    'w': '9',  'x': '99',  'y': '999',  'z': '9999',
    ' ': '0',
}


def t9_keypad_encoder(text, separator=' '):
    """Return the T9 multi-tap encoding of ``text``.

    Parameters
    ----------
    text : str
        The string to encode. Letters are matched case-insensitively.
        Characters not present in the keymap (digits, punctuation, etc.)
        are silently dropped.
    separator : str, optional
        Token inserted between two consecutive characters that share
        the same key. Defaults to a single space.

    Returns
    -------
    str
        The encoded digit string. Returns an empty string if ``text``
        is empty, ``None``, or contains only unknown characters.
    """
    if not text:
        return ''

    pieces = []
    previous_key = None
    for ch in text.lower():
        if ch not in T9_KEYMAP:
            continue
        encoding = T9_KEYMAP[ch]
        key = encoding[0]
        if previous_key is not None and previous_key == key:
            pieces.append(separator)
        pieces.append(encoding)
        previous_key = key
    return ''.join(pieces)