# --- Add these module-level definitions near the existing _CONTACT_RE ---

_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')

# Merge with your existing platform words; this is a reasonable default set.
_SKIP_WORDS = {
    'imessage', 'whatsapp', 'gmail', 'slack', 'teams', 'discord',
    'telegram', 'signal', 'sms', 'facebook', 'instagram', 'twitter',
    'linkedin', 'email', 'text', 'message', 'dm', 'chat', 'phone',
    'call', 'video', 'snapchat', 'messenger', 'wechat', 'line',
    'viber', 'skype', 'zoom', 'google', 'apple', 'microsoft',
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
    'saturday', 'sunday', 'january', 'february', 'march', 'april',
    'may', 'june', 'july', 'august', 'september', 'october',
    'november', 'december',
}

_STOP_WORDS = frozenset({
    'The', 'A', 'An', 'I', 'My', 'What', 'Who', 'When', 'Where',
    'How', 'Did', 'Does', 'Didn', 'Isn', 'Was', 'Were', 'Is', 'Are',
    'Am', 'Have', 'Has', 'Had', 'Do', 'Don', 'Can', 'Could', 'Would',
    'Should', 'Will', 'Won', 'Tell', 'Show', 'Send', 'Give', 'Get',
    'Make', 'Let', 'Put', 'Say', 'Said', 'Told', 'Ask',
    'Want', 'Need', 'Like', 'Love', 'Know', 'Think', 'See', 'Look',
    'Find', 'Use', 'Go', 'Come', 'Take', 'Bring', 'Keep', 'Leave',
    'Yesterday', 'Today', 'Tomorrow', 'Now', 'Then', 'Here', 'There',
})


# --- Updated function (replaces the existing _extract_contact) ---

def _extract_contact(text):
    """Extract a contact name from free-form text.

    First tries a prepositional match (e.g. "to Sarah", "from John").
    Falls back to any capitalized token that isn't a platform name
    or a common English stop word.
    """
    # 1. Prepositional match: "to/from/with <Name>"
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2. Fallback: bare capitalized name anywhere in the text
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() in _SKIP_WORDS:
            continue
        if w in _STOP_WORDS:
            continue
        return w

    return None
