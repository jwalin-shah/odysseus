# Module-level additions (place near the existing _CONTACT_RE definition)

_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
_SKIP_WORDS = {
    # Platforms / channels
    'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'text', 'message',
    'messages', 'slack', 'discord', 'telegram', 'signal', 'facebook',
    'messenger', 'twitter', 'instagram', 'tiktok', 'snapchat',
    'linkedin', 'youtube', 'teams',
    # Time-ish words that often appear capitalized at sentence start
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
    'saturday', 'sunday', 'today', 'tomorrow', 'yesterday',
    'january', 'february', 'march', 'april', 'june', 'july',
    'august', 'september', 'october', 'november', 'december',
    # Common nouns that may appear capitalized after punctuation
    'Send', 'Tell', 'Show', 'Find', 'Get', 'Give', 'Read', 'Open',
}


def _extract_contact(text: str) -> str | None:
    """Return the contact name mentioned in *text*, or None.

    1. Prefer a name introduced by a preposition (to / from / with …).
    2. Fall back to the first capitalized token that is not a
       platform/channel word, time word, or question/sentence-start word.
    """
    # 1) Prepositional match: "to Sarah", "from John Smith", "with Dr. Lee"
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2) Fallback: bare capitalized name anywhere in the text
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() in _SKIP_WORDS:
            continue
        if w in ('The', 'A', 'An', 'I', 'My', 'What', 'Who', 'When',
                 'Where', 'How', 'Did', 'Does', 'Is', 'Was', 'Were',
                 'Have', 'Has', 'Had', 'Can', 'Could', 'Would', 'Should',
                 'Will', 'Shall', 'May', 'Might', 'Do'):
            continue
        return w
    return None
