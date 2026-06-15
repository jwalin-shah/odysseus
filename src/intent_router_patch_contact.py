def _extract_contact(text):
    """Extract a contact name from free-form text.

    Order of attempts:
      1. Prepositional match (e.g. "to Sarah", "from John", "with Mike").
      2. Fallback: any capitalized word that isn't a platform or stop word.
    """
    # 1. Prepositional match (existing behaviour).
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2. Fallback: bare capitalized name not after a preposition.
    _BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
    _SKIP_WORDS = {
        # Messaging / email platforms and channel words
        'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'text', 'slack',
        'telegram', 'signal', 'facebook', 'messenger', 'twitter', 'instagram',
        'discord', 'message', 'messages', 'mail', 'phone', 'call',
    }
    _STOP_WORDS = {
        'The', 'A', 'An', 'I', 'My',
        'What', 'Who', 'When', 'Where', 'How',
        'Did', 'Does', 'Do', 'Is', 'Was', 'Were', 'Are',
        'Send', 'Show', 'Get', 'Find', 'Tell', 'Reply',
    }

    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() not in _SKIP_WORDS and w not in _STOP_WORDS:
            return w
    return None
