# Module-level additions (place alongside _CONTACT_RE):

_BARE_NAME_RE = re.compile(r'\b([A-Z][a-z]{1,15})\b')

# Extends the existing platform-word set with common non-name capitalized tokens
# so the bare-name fallback doesn't pick up sentence starters, weekdays, etc.
_SKIP_WORDS = {
    # --- messaging/email platforms (existing) ---
    'imessage', 'whatsapp', 'gmail', 'email', 'sms', 'message', 'messages',
    'messenger', 'telegram', 'signal', 'slack', 'discord', 'teams',
    'google', 'apple', 'microsoft', 'facebook', 'twitter', 'instagram',
    'linkedin', 'outlook', 'yahoo', 'siri', 'alexa',
    # --- common sentence-starter / question words ---
    'the', 'this', 'that', 'these', 'those', 'there', 'here',
    'a', 'an', 'some', 'any', 'all', 'each', 'every',
    'i', 'my', 'your', 'his', 'her', 'its', 'our', 'their',
    'what', 'who', 'when', 'where', 'why', 'how', 'which',
    'did', 'does', 'do', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'will', 'would', 'could', 'should', 'can', 'may',
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'january', 'february', 'march', 'april', 'may', 'june', 'july',
    'august', 'september', 'october', 'november', 'december',
    'today', 'tomorrow', 'yesterday', 'now', 'then', 'later', 'soon',
    'send', 'show', 'find', 'get', 'open', 'read', 'write', 'reply', 'forward',
    'call', 'text', 'tell', 'ask', 'check', 'search', 'look',
    'please', 'thanks', 'thank', 'hello', 'hi', 'hey', 'yes', 'no', 'ok', 'okay',
    'first', 'last', 'next', 'previous', 'new', 'old', 'latest', 'recent',
    'us', 'uk', 'usa', 'eu',
}


def _extract_contact(text: str) -> str | None:
    """Extract a contact name from free-form text.

    Strategy:
      1. Try the prepositional match (e.g. "to Sarah", "from John",
         "with Mom"). This is the most precise path.
      2. If that fails, fall back to scanning for any bare capitalized
         word that isn't a known platform/function-word token. This
         catches questions like "what did Sarah say" or
         "did John call me" where the name stands alone.
    """
    # 1) Primary path: prepositional contact match
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2) Fallback: bare capitalized name not after a preposition
    for m in _BARE_NAME_RE.finditer(text):
        w = m.group(1)
        if w.lower() in _SKIP_WORDS:
            continue
        if w in ('The', 'A', 'An', 'I', 'My', 'What', 'Who',
                 'When', 'Where', 'How', 'Did', 'Does'):
            continue
        return w

    return None
