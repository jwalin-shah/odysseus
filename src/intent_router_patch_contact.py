# --- New module-level helpers (add near _CONTACT_RE) ---
_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')

# Platforms, services, and weekday/month names that look like names
# but are not contacts.
_SKIP_WORDS = {
    # messaging platforms / services
    'imessage', 'whatsapp', 'gmail', 'slack', 'discord', 'telegram',
    'signal', 'sms', 'email', 'messenger', 'teams', 'outlook',
    'facebook', 'instagram', 'twitter', 'snapchat', 'linkedin',
    'message', 'messages', 'chat', 'chats', 'notification', 'notifications',
    # days
    'sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
    'saturday',
    # months
    'january', 'february', 'march', 'april', 'may', 'june', 'july',
    'august', 'september', 'october', 'november', 'december',
    # common app/feature words
    'Today', 'Tomorrow', 'Yesterday', 'Inbox', 'Drafts', 'Sent',
    'Trash', 'Spam',
}

# Sentence-initial / function words that are capitalized but not names.
_SKIP_INITIAL = {
    'The', 'A', 'An', 'I', 'My', 'Your', 'His', 'Her', 'Our', 'Their',
    'What', 'Who', 'When', 'Where', 'How', 'Why', 'Which',
    'Did', 'Does', 'Do', 'Is', 'Are', 'Was', 'Were', 'Has', 'Have', 'Had',
    'Can', 'Could', 'Would', 'Should', 'Will', 'Shall', 'May', 'Might',
    'Show', 'Get', 'Find', 'Send', 'Open', 'Read', 'Tell', 'Check',
    'Reply', 'Forward', 'Delete', 'Mark', 'Unread', 'Draft', 'Compose',
    'New', 'Old', 'Latest', 'Last', 'First', 'Next', 'Previous',
    'Hey', 'Hi', 'Hello', 'Please', 'Thanks', 'Thank',
}


def _extract_contact(text: str) -> Optional[str]:
    """Return the most likely contact name in *text*, or None.

    Order of attempts:
      1. A capitalized token immediately following a preposition
         (``to`` / ``from`` / ``with`` / ``about`` / ``on`` etc.),
         matched by ``_CONTACT_RE``.
      2. A bare capitalized word anywhere in the string, excluding
         platform names, services, and English function/initial words.
    """
    # 1. Prepositional match (highest confidence).
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2. Fallback: any capitalized word that looks like a proper noun.
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w in _SKIP_INITIAL:
            continue
        if w.lower() in _SKIP_WORDS:
            continue
        # Require at least one vowel to reduce false positives like
        # "Btw", "Ok", "Lol" sneaking through.
        if not any(ch in 'aeiou' for ch in w.lower()):
            continue
        return w

    return None
