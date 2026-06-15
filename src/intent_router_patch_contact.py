# Module-level (place above _extract_contact)
_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
_SKIP_WORDS = {
    'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'text', 'signal',
    'telegram', 'slack', 'messenger', 'facebook', 'twitter', 'instagram',
    'linkedin', 'discord', 'teams', 'wechat', 'line', 'viber', 'skype',
}


def _extract_contact(text: str) -> str | None:
    # Primary: prepositional contact ("to Sarah", "from John")
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # Fallback: bare capitalized name not after a preposition
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() not in _SKIP_WORDS and w not in (
            'The', 'A', 'An', 'I', 'My', 'What', 'Who',
            'When', 'Where', 'How', 'Did', 'Does',
        ):
            return w

    return None
