"""Reverse the order of words in a sentence."""


def string_missions_sentence_word_reverser(sentence):
    """Reverse the order of words in a sentence.

    The input is split on any whitespace runs, the resulting list of
    words is reversed, and the words are joined back together with a
    single space. Empty / whitespace-only input or non-string input
    yields an empty string.

    Args:
        sentence: A string containing words separated by spaces, or
            ``None`` / a non-string value.

    Returns:
        A string with the words in reverse order, separated by single
        spaces. Returns ``""`` when there are no words to reverse.
    """
    # Guard against non-string / None input so the helper never raises
    # an unexpected exception on bad data.
    if not isinstance(sentence, str):
        return ""

    # ``str.split()`` with no arguments splits on any whitespace and
    # discards empty tokens, which collapses runs of spaces, tabs and
    # newlines as well as trimming leading / trailing whitespace.
    words = sentence.split()
    if not words:
        return ""

    # ``reversed`` returns an iterator, so we avoid building an extra
    # list. The join collapses everything to single-space separation.
    return " ".join(reversed(words))


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    samples = [
        "Hello World",
        "The quick brown fox jumps over the lazy dog",
        "   leading and trailing   spaces   ",
        "",
        "   ",
        "single",
        "a b c d e",
    ]
    for s in samples:
        print(f"{s!r} -> {string_missions_sentence_word_reverser(s)!r}")