def _extract_contact(text: str) -> str | None:
    """Extract a contact name from the user text.

    First tries a prepositional match (e.g. "to Sarah", "from John").
    Falls back to scanning for any bare capitalized name that isn't a
    platform/common word or a question-word.
    """
    # 1) Prepositional match: "to/from/with <Name>"
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2) Fallback: any bare capitalized name in the text
    _BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
    _SKIP_WORDS = {
        # platforms / channels
        'imessage', 'whatsapp', 'gmail', 'email', 'mail', 'sms',
        'slack', 'teams', 'discord', 'telegram', 'signal',
        'facebook', 'instagram', 'twitter', 'snapchat', 'messenger',
        # common UI / action words that get capitalized mid-sentence
        'message', 'messages', 'text', 'texts', 'chat', 'chats',
        'inbox', 'sent', 'draft', 'drafts', 'unread', 'spam',
        'send', 'show', 'find', 'search', 'get', 'open', 'read',
        'last', 'latest', 'recent', 'new', 'old', 'first', 'next',
        'today', 'yesterday', 'tomorrow', 'week', 'month', 'year',
        'morning', 'afternoon', 'evening', 'night',
        # addresses / fillers
        'Subject', 'From', 'To', 'Cc', 'Bcc', 'Re', 'Fwd',
    }
    _SKIP_PROPER = {
        'The', 'A', 'An', 'I', 'My', 'Your', 'Our', 'Their',
        'What', 'Who', 'Whom', 'Whose', 'When', 'Where', 'Why', 'How',
        'Did', 'Does', 'Do', 'Is', 'Are', 'Was', 'Were', 'Will', 'Would',
        'Can', 'Could', 'Should', 'May', 'Might', 'Have', 'Has', 'Had',
        'Please', 'Thanks', 'Thank', 'Hi', 'Hello', 'Hey', 'Yeah',
        'Yes', 'No', 'Not', 'Never', 'Always',
    }

    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w in _SKIP_PROPER:
            continue
        if w.lower() in _SKIP_WORDS:
            continue
        return w
    return None
