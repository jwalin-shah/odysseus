import re

# Existing prepositional contact pattern (kept as-is).
_CONTACT_RE = re.compile(
    r'\b(?:to|from|with|about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b'
)

# Fallback: bare capitalized name not after a preposition.
_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')

# Tokens that look like proper nouns but are not contacts.
_SKIP_WORDS = {
    # platforms / services
    'imessage', 'whatsapp', 'gmail', 'email', 'slack', 'discord',
    'telegram', 'signal', 'messenger', 'facebook', 'twitter',
    'instagram', 'snapchat', 'teams', 'skype', 'zoom', 'sms',
    'text', 'message', 'mail', 'inbox', 'draft', 'thread',
    # generic verbs / nouns that can appear capitalized
    'send', 'reply', 'forward', 'show', 'find', 'get', 'give',
    'call', 'ask', 'tell', 'say', 'said', 'tell',
    # common stop words (defensive — most are filtered by the
    # explicit tuple below, but this catches the lowercase forms)
    'the', 'a', 'an', 'i', 'my', 'me', 'we', 'us', 'our', 'you', 'your',
    'what', 'who', 'when', 'where', 'how', 'why', 'which',
    'did', 'does', 'do', 'is', 'was', 'were', 'are', 'am',
    'be', 'been', 'being',
    'can', 'could', 'would', 'should', 'will', 'shall', 'may', 'might',
    'to', 'from', 'with', 'for', 'in', 'on', 'at', 'by', 'about', 'of',
    'please', 'thanks', 'thank', 'hi', 'hello', 'hey',
}

# Words that may be capitalized in input but are never contact names.
_EXPLICIT_TITLE_SKIP = {
    'The', 'A', 'An', 'I', 'My', 'Me', 'What', 'Who', 'When', 'Where',
    'How', 'Why', 'Which', 'Did', 'Does', 'Do', 'Is', 'Was', 'Were',
    'Are', 'Am', 'Can', 'Could', 'Would', 'Should', 'Will', 'To',
    'From', 'With', 'For', 'In', 'On', 'At', 'By', 'About',
    'Send', 'Reply', 'Forward', 'Show', 'Find', 'Get', 'Give', 'Call',
    'Ask', 'Tell', 'Say', 'Said',
}


def _extract_contact(text: str) -> str | None:
    """Return a contact name from ``text``, or ``None`` if none is found.

    Strategy
    --------
    1. Prefer a name introduced by a preposition (``to Sarah``,
       ``from John Smith``, ``with Alex``).
    2. Otherwise fall back to scanning for any bare capitalized token
       that is not a platform name, service word, or common English
       stop word.  This handles queries like
       ``"what did Sarah say"`` where no preposition precedes the name.
    """
    # 1) Prepositional match wins.
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2) Bare-capitalized-name fallback.
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w in _EXPLICIT_TITLE_SKIP:
            continue
        if w.lower() in _SKIP_WORDS:
            continue
        return w

    return None
