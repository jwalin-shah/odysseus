def _extract_contact(text: str) -> Optional[str]:
    """Extract a contact name from free-form text.

    First tries a prepositional match (e.g. "to Sarah", "from John", "with Alex").
    If that fails, falls back to the first capitalized word that isn't a platform
    name or a common English word (e.g. "what did Sarah say" -> "Sarah").
    """
    # 1) Existing prepositional match: to/from/with <Name>
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2) Fallback: bare capitalized name not after a preposition
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() in _SKIP_WORDS:
            continue
        if w in (
            'The', 'A', 'An', 'I', 'My',
            'What', 'Who', 'When', 'Where', 'How',
            'Did', 'Does', 'Do', 'Is', 'Are', 'Was', 'Were',
            'Have', 'Has', 'Had', 'Will', 'Would', 'Could', 'Should',
            'Can', 'May', 'Might', 'Shall', 'About', 'Tell', 'Show',
            'Send', 'Reply', 'Open', 'Read', 'Find', 'Get', 'Give',
        ):
            continue
        return w

    return None
