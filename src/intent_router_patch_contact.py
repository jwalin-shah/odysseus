def _extract_contact(text: str) -> str | None:
    """Extract a contact name from user text.

    Tries a prepositional match first (e.g. "to Sarah", "from John"),
    then falls back to any capitalized token that isn't a platform name
    or a common sentence-initial word.
    """
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # Fallback: bare capitalized name not after a preposition
    _BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
    _SKIP_WORDS = {
        'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'message',
        'sunday', 'monday', 'tuesday', 'wednesday', 'thursday',
        'friday', 'saturday', 'today', 'tomorrow', 'yesterday',
    }

    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() not in _SKIP_WORDS and w not in (
            'The', 'A', 'An', 'I', 'My', 'What', 'Who',
            'When', 'Where', 'How', 'Did', 'Does',
        ):
            return w
    return None
