import re

_CONTACT_RE = re.compile(
    r'\b(?:to|from|with|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
    re.IGNORECASE,
)
_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
_SKIP_WORDS = {
    'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'slack', 'signal',
    'telegram', 'messenger', 'facebook', 'twitter', 'instagram', 'discord',
    'teams', 'outlook', 'yahoo', 'snapchat', 'linkedin', 'youtube',
    'phone', 'message', 'text', 'call', 'send', 'reply', 'forward',
    'hi', 'hello', 'hey', 'ok', 'okay', 'yes', 'no', 'thanks', 'thank',
}
_QUESTION_WORDS = {'The', 'A', 'An', 'I', 'My', 'What', 'Who', 'When',
                   'Where', 'How', 'Did', 'Does', 'Is', 'Are', 'Was',
                   'Were', 'Will', 'Would', 'Can', 'Could', 'Should'}


def _extract_contact(text: str) -> str | None:
    """Return the most likely contact name from the user text, or None."""
    # Primary: name directly following a preposition (e.g. "to Sarah")
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # Fallback: any capitalized token that isn't a platform or
    # question/sentence-starter word (e.g. "what did Sarah say" -> "Sarah")
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() in _SKIP_WORDS:
            continue
        if w in _QUESTION_WORDS:
            continue
        return w

    return None
