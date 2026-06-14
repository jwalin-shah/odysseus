def sentence_word_reverser(text):
    """Reverse the order of words in a sentence.

    Args:
        text (str): The input sentence whose words should be reversed.

    Returns:
        str: A new string containing the words of ``text`` in reverse order,
        separated by a single space. Returns an empty string for input that
        contains no words (empty string or whitespace-only input).

    Raises:
        TypeError: If ``text`` is not a string.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"sentence_word_reverser expected a string, got {type(text).__name__}"
        )

    if not text.strip():
        return ""

    words = text.split()
    return " ".join(reversed(words))


if __name__ == "__main__":
    # Simple manual demo
    samples = [
        "Hello world",
        "The quick brown fox jumps over the lazy dog",
        "   leading and trailing   spaces   ",
        "single",
        "",
        "   ",
    ]
    for s in samples:
        print(f"{s!r} -> {sentence_word_reverser(s)!r}")