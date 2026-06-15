# --- module-level additions (place near _CONTACT_RE) --------------------
_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
_SKIP_WORDS = {
    # messaging / email platforms
    'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'slack',
    'teams', 'discord', 'telegram', 'signal', 'messenger',
    'facebook', 'instagram', 'twitter', 'linkedin', 'wechat',
    # common verb / object nouns that often appear capitalized
    'phone', 'call', 'text', 'message', 'send', 'reply',
    'forward', 'draft', 'inbox', 'mail',
}
# ------------------------------------------------------------------------


def _extract_contact(text):
    """Return the contact name appearing in `text`, or None.

    1) Try the prepositional pattern first (e.g. "to Sarah", "from John",
       "with Alex"). This is the most reliable signal.
    2) Fall back to scanning for any bare capitalized token that isn't
       a known platform / object word or a common sentence-initial word.
       This handles inputs like "what did Sarah say" where the name is
       the subject of the sentence rather than the object of a
       preposition.
    """
    # 1) Prepositional match: "to Sarah", "from John", "with Alex", ...
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2) Fallback: bare capitalized name not after a preposition.
    _SENTENCE_INITIAL = {
        'The', 'A', 'An', 'I', 'My', 'Your', 'Our', 'Their',
        'What', 'Who', 'When', 'Where', 'How', 'Why', 'Which',
        'Did', 'Does', 'Do', 'Is', 'Are', 'Was', 'Were',
        'Can', 'Could', 'Would', 'Should', 'Will', 'Shall',
        'May', 'Might', 'Have', 'Has', 'Had',
    }
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() in _SKIP_WORDS:
            continue
        if w in _SENTENCE_INITIAL:
            continue
        return w
    return None
