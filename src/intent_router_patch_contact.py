import re

_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
_SKIP_WORDS = {
    'imessage', 'whatsapp', 'gmail', 'slack', 'teams', 'telegram',
    'signal', 'sms', 'email', 'mail', 'message', 'messages',
    'discord', 'facebook', 'instagram', 'twitter', 'linkedin',
    'youtube', 'tiktok', 'snapchat',
}

_QUESTION_WORDS = {'The', 'A', 'An', 'I', 'My', 'What', 'Who', 'When', 'Where', 'How', 'Did', 'Does'}


def _extract_contact(text):
    """Extract a contact name from the text.

    First tries the prepositional form (to/from/with <Name>) via _CONTACT_RE.
    Falls back to the first bare capitalized word that isn't a platform
    name or a question/stop word, so patterns like "what did Sarah say"
    resolve to "Sarah".
    """
    # Existing: match after prepositions (to/from/with)
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # Fallback: bare capitalized name not after a preposition
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w in _QUESTION_WORDS:
            continue
        if w.lower() in _SKIP_WORDS:
            continue
        return w

    return None
