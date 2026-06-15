def _extract_contact(text):
    """Extract a contact name from a user message.

    Primary path: a name following a preposition (to/from/with).
    Fallback: any capitalized word that isn't a platform name or a
    common function/question word.
    """
    # Existing prepositional match: "to Sarah", "from John", "with Alex"
    _PREP_RE = re.compile(
        r'\b(?:to|from|with|by|for)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        re.IGNORECASE,
    )
    m = _PREP_RE.search(text)
    if m:
        return m.group(1)

    # Fallback: bare capitalized name not after a preposition
    # e.g. "what did Sarah say" -> "Sarah"
    _BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
    _SKIP_WORDS = {
        'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'slack',
        'telegram', 'signal', 'discord', 'teams', 'messenger',
        'twitter', 'facebook', 'instagram', 'linkedin', 'github',
    }
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() in _SKIP_WORDS:
            continue
        if w in ('The', 'A', 'An', 'I', 'My', 'What', 'Who',
                 'When', 'Where', 'How', 'Did', 'Does',
                 'Is', 'Was', 'Were', 'Are', 'To', 'From', 'With'):
            continue
        return w

    return None
