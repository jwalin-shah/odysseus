def _extract_contact(text: str) -> Optional[str]:
    """Extract a contact name from text.

    First tries a prepositional match (e.g. "to Sarah", "from John",
    "with Alex"). If that fails, falls back to the first bare
    capitalized token that isn't a platform word or a common
    sentence-initial word.
    """
    # First try: prepositional contact (to/from/with)
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # Fallback: bare capitalized name not after a preposition
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() in _SKIP_WORDS:
            continue
        if w in ('The', 'A', 'An', 'I', 'My',
                 'What', 'Who', 'When', 'Where', 'How',
                 'Did', 'Does'):
            continue
        return w
    return None
