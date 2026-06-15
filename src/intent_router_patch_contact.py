# New module-level constants — add these next to the existing _CONTACT_RE.

# Fallback pattern: any single capitalized word (2–16 chars).
# Used when the text has no "to/from/with <Name>" prepositional match.
_BARE_NAME_RE = re.compile(r"\b([A-Z][a-z]{1,15})\b")

# Platform / service / product names that must never be matched as a
# contact.  Compared case-insensitively against w.lower().
_SKIP_WORDS = {
    # Messaging / chat
    "imessage", "message", "messenger", "whatsapp", "signal", "telegram",
    "slack", "teams", "discord", "skype", "zoom", "wechat", "line",
    "snapchat", "twitter", "facebook", "instagram", "tiktok", "reddit",
    "linkedin", "youtube", "pinterest", "hangouts",
    # Email / calendar
    "gmail", "email", "mail", "outlook", "yahoo", "inbox", "calendar",
    # OS / vendor
    "google", "apple", "microsoft", "samsung", "android", "iphone",
    # Generic "send a ..." words
    "sms", "text", "phone", "call", "voicemail", "note", "reminder",
    # Defensive fragments of CamelCase product names
    "app", "web", "chat", "book", "docs", "drive",
}


# Updated function — replace the existing _extract_contact with this.

def _extract_contact(text: str) -> Optional[str]:
    """Return the most likely contact name in *text*, or None.

    Strategy
    --------
    1. Try a prepositional match first:  ``to Sarah``, ``from John``,
       ``with Alex``, ``at Megan`` — handled by the existing
       ``_CONTACT_RE`` regex.
    2. If that fails, scan for any capitalized token that is neither a
       known platform / service name nor a common English word.  This
       catches queries like ``"what did Sarah say"`` where the name
       appears without an introducing preposition.
    """
    # 1. Prepositional match: "to Sarah", "from John", "with Alex" ...
    m = _CONTACT_RE.search(text)
    if m:
        return m.group(1)

    # 2. Fallback: bare capitalized name anywhere in the text.
    for match in _BARE_NAME_RE.finditer(text):
        w = match.group(1)

        # Platform / service names — never a contact.
        if w.lower() in _SKIP_WORDS:
            continue

        # Sentence-initial, question, pronoun, and function words.
        if w in (
            # Articles / determiners
            "The", "A", "An", "My", "This", "That", "These", "Those",
            "Some", "Any", "No", "All", "Each", "Every", "Both",
            # Pronouns
            "I", "You", "He", "She", "It", "We", "They",
            "Me", "Him", "Her", "Us", "Them",
            "My", "Your", "His", "Her", "Its", "Our", "Their",
            "Mine", "Yours", "Hers", "Ours", "Theirs",
            # Question / wh-words
            "What", "Who", "Whom", "Whose", "Which",
            "When", "Where", "Why", "How",
            # Auxiliaries & modals
            "Do", "Does", "Did", "Done",
            "Have", "Has", "Had", "Having",
            "Be", "Am", "Is", "Are", "Was", "Were", "Been", "Being",
            "Will", "Would", "Shall", "Should",
            "Can", "Could", "May", "Might", "Must",
            # Common sentence-initial verbs
            "Say", "Said", "Tell", "Told", "Ask", "Asked",
            "Get", "Got", "Go", "Going", "Gone",
            "Want", "Wanted", "Need", "Needed", "Like", "Liked",
            "Make", "Made", "Take", "Took", "Give", "Gave",
            "See", "Saw", "Know", "Knew", "Think", "Thought",
            "Let", "Put", "Set", "Run", "Keep", "Find", "Found",
            # Prepositions / conjunctions
            "In", "On", "At", "To", "From", "With", "By", "For",
            "Of", "Off", "Out", "Over", "Under", "Into", "Onto",
            "About", "After", "Before", "Above", "Below", "Through",
            "During", "Since", "Until", "While", "Between", "Among",
            "And", "Or", "But", "Nor", "Yet", "So", "If", "As",
            "Because", "Although", "Though", "Unless", "Whether",
            # Adverbs / fillers
            "Just", "Also", "Then", "Now", "Still", "Already",
            "Yet", "Only", "Even", "Too", "Very", "Really", "Quite",
            "Here", "There", "Today", "Tomorrow", "Yesterday",
            "Please", "Thanks", "Sorry", "Hello", "Hi", "Hey",
            "Yes", "No", "Okay", "Ok",
        ):
            continue

        # CamelCase fragment guard: skip if the character right after
        # the match is uppercase or a digit — e.g. "App" inside
        # "WhatsApp", or "Web" inside "WebApp".
        end = match.end()
        if end < len(text) and (text[end].isupper() or text[end].isdigit()):
            continue

        return w

    return None
