import re

def _extract_contact(text: str) -> str | None:
    """Extract a contact name from user text.

    Order of attempts:
      1. Name following a preposition (to/from/with/by/for ...).
      2. Fallback: any capitalized token that is not a platform word
         or a common English word (handles "what did Sarah say").
    """
    # 1) Prepositional match (existing behavior)
    prep_match = _CONTACT_RE.search(text)
    if prep_match:
        return prep_match.group(1)

    # 2) Fallback: bare capitalized name anywhere in the text
    _BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')
    _SKIP_WORDS = {
        # platforms / channels
        'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'message', 'messages',
        'text', 'texts', 'mail', 'slack', 'discord', 'telegram', 'signal',
        # common verbs
        'send', 'sent', 'reply', 'replied', 'tell', 'told', 'say', 'said',
        'ask', 'asked', 'show', 'showed', 'read', 'wrote', 'write',
        # time / determiners
        'last', 'latest', 'recent', 'new', 'old', 'first', 'second', 'next',
        'this', 'that', 'these', 'those',
        # days / months
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
        'saturday', 'sunday',
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december',
    }
    _SKIP_PROPER = {
        'The', 'A', 'An', 'I', 'My', 'What', 'Who', 'When', 'Where',
        'How', 'Did', 'Does', 'Is', 'Was', 'Are', 'Were', 'In', 'On',
        'At', 'To', 'From', 'With', 'By', 'For', 'Of', 'And', 'Or',
        'It', 'Its', 'They', 'Them', 'Their', 'He', 'She', 'His', 'Her',
    }

    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() in _SKIP_WORDS:
            continue
        if w in _SKIP_PROPER:
            continue
        return w

    return None
