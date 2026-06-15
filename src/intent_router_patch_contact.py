import re

_CONTACT_RE = re.compile(
    r'\b(?:to|from|with|about|for)\s+([A-Z][a-z]+)\b',
    re.IGNORECASE,
)

# Fallback: any capitalized token, used when no prepositional contact is found
_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')

# Platform / channel words that look like proper nouns but are not contacts
_SKIP_WORDS = {
    'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'text',
    'message', 'messages', 'chat', 'chats', 'telegram', 'signal',
    'slack', 'discord', 'facebook', 'instagram', 'twitter',
    'snapchat', 'google', 'apple', 'microsoft', 'outlook', 'yahoo',
}

# Common sentence-initial / interrogative words that get capitalized
_SKIP_PROPER = {
    'The', 'A', 'An', 'I', 'My', 'What', 'Who', 'When',
    'Where', 'How', 'Did', 'Does', 'Is', 'Are', 'Was', 'Were',
    'Can', 'Could', 'Would', 'Should', 'Will', 'Do', 'Have', 'Has',
}


def _extract_contact(text):
    """Return the most likely contact name in *text*, or None.

    Strategy:
      1. Prefer a capitalized name that follows a preposition
         (e.g. "message Sarah", "to John").
      2. Otherwise fall back to the first capitalized token that
         isn't a platform/channel word or a sentence-initial word.
    """
    # 1. Prepositional match (e.g. "to Sarah", "from John")
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2. Fallback: bare capitalized name anywhere in the text
    for m in _BARE_NAME_RE.finditer(text):
        word = m.group(1)
        if word in _SKIP_PROPER:
            continue
        if word.lower() in _SKIP_WORDS:
            continue
        return word

    return None
