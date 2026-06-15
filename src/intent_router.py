from dataclasses import dataclass, field
from typing import Optional
import re


@dataclass
class IntentResult:
    platform: str       # "imessage"|"gmail"|"whatsapp"|"calendar"|"linkedin"|"code"|"general"
    action: str         # "read"|"reply"|"send"|"search"|"create"|"delete"|"analyze"
    contact: Optional[str]
    needs_approval: bool
    confidence: float
    inbox_route: str    # REST path e.g. "/imessage/contacts"
    time_info: Optional[dict] = field(default=None)


_PLATFORM_PATTERNS = [
    ("imessage",  r"\b(iMessage|text(ed)?|sms|message[sd]?|chat)\b"),
    ("whatsapp",  r"\b(whatsapp|wa|wapp)\b"),
    ("gmail",     r"\b(email|gmail|mail(box)?|inbox)\b"),
    ("calendar",  r"\b(calendar|meeting|event|schedule|appointment|remind(er)?)\b"),
    ("linkedin",  r"\b(linkedin|li\b|connection[s]?|dm[s]?|network(ing)?)\b"),
    ("code",      r"\b(bug|fix|refactor|code|file|function|test|error|stack trace|pr|commit)\b"),
]

_ACTION_PATTERNS = [
    ("reply",   r"\b(reply|respond|answer|write back|send back)\b"),
    ("send",    r"\b(send|forward|share|dm|text)\b"),
    ("create",  r"\b(add|create|schedule|set up|book|make)\b"),
    ("delete",  r"\b(delete|remove|cancel|decline)\b"),
    ("search",  r"\b(search|find|look for|who|where)\b"),
    ("read",    r"\b(read|show|get|what|check|list|summary|summarize|unread|latest|recent)\b"),
    ("analyze", r"\b(analyze|analyse|explain|why|how|understand)\b"),
]

_WRITE_ACTIONS = {"reply", "send", "create", "delete"}

_PLATFORM_ROUTES = {
    "imessage": "/imessage/contacts",
    "gmail":    "/messages/gmail/",
    "whatsapp": "/whatsapp/contacts",
    "calendar": "/calendar/upcoming",
    "linkedin": "/linkedin/dms",
    "code":     "",
    "general":  "",
}

_ACTION_ROUTES = {
    ("imessage", "read"):   "/imessage/messages/{contact}",
    ("imessage", "reply"):  "/messages/send",
    ("imessage", "send"):   "/messages/send",
    ("gmail",    "read"):   "/messages/gmail/",
    ("gmail",    "send"):   "/gmail/send",
    ("gmail",    "reply"):  "/gmail/reply",
    ("whatsapp", "read"):   "/whatsapp/messages/{contact}",
    ("whatsapp", "send"):   "/whatsapp/send",
    ("whatsapp", "reply"):  "/whatsapp/send",
    ("calendar", "read"):   "/calendar/upcoming",
    ("calendar", "create"): "/calendar/events",
    ("linkedin", "read"):   "/linkedin/dms",
    ("linkedin", "send"):   "/linkedin/send",
}

_PLATFORM_WORDS = {"imessage", "whatsapp", "gmail", "email", "calendar", "linkedin", "text", "sms"}
_STOP_WORDS = {"about", "for", "re", "regarding", "on", "and", "but", "with", "to", "in"}

# Stop contact capture at prepositions/conjunctions that start a new clause
_CONTACT_RE = re.compile(
    r"(?:to|from|with|for|reply to|send to|forward to|ask)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    re.IGNORECASE,
)

_TIME_DAYS = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|yesterday)"
_TIME_HMS = r"(?:(\d{1,2})(?::(\d{2}))?\s*([ap]m)?)"
_TIME_ISO = r"(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?)"
_TIME_RELATIVE = r"(next\s+week|this\s+week|this\s+morning|this\s+afternoon|this\s+evening|tonight)"

_DAY_RE = re.compile(_TIME_DAYS, re.IGNORECASE)
_HMS_RE = re.compile(_TIME_HMS, re.IGNORECASE)
_ISO_RE = re.compile(_TIME_ISO)
_REL_RE = re.compile(_TIME_RELATIVE, re.IGNORECASE)


def _match_platform(text: str) -> tuple[str, float]:
    lower = text.lower()
    for platform, pattern in _PLATFORM_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return platform, 0.9
    return "general", 0.3


def _match_action(text: str) -> tuple[str, float]:
    lower = text.lower()
    for action, pattern in _ACTION_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            return action, 0.85
    return "read", 0.4


def _extract_contact(text: str) -> Optional[str]:
    m = _CONTACT_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Drop trailing words that are prepositions or platform names
    words = raw.split()
    clean = []
    for w in words:
        if w.lower() in _STOP_WORDS or w.lower() in _PLATFORM_WORDS:
            break
        # Drop possessives at word boundary ("mom's" → "mom")
        clean.append(w.rstrip("'s"))
    return " ".join(clean) if clean else None


def _extract_time(text: str) -> Optional[dict]:
    iso = _ISO_RE.search(text)
    if iso:
        raw = iso.group(1).replace(" ", "T")
        if "T" not in raw:
            raw += "T00:00:00"
        return {"datetime_iso": raw}

    rel = _REL_RE.search(text)
    day = _DAY_RE.search(text)
    hms = _HMS_RE.search(text)

    if rel and not day:
        return {"relative": rel.group(0).lower()}

    if not day and not hms:
        return None

    result: dict = {"relative": True}
    if day:
        result["day"] = day.group(0).capitalize()
    if hms:
        h = int(hms.group(1))
        mn = int(hms.group(2) or 0)
        ampm = (hms.group(3) or "").lower()
        if ampm == "pm" and h < 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        result["time"] = f"{h:02d}:{mn:02d}"
    elif day:
        word = day.group(0).lower()
        if "morning" in text.lower():
            result["time"] = "09:00"
        elif "afternoon" in text.lower() or "evening" in text.lower():
            result["time"] = "15:00"
    return result


def _route(platform: str, action: str, contact: Optional[str]) -> str:
    route = _ACTION_ROUTES.get((platform, action), _PLATFORM_ROUTES.get(platform, ""))
    if contact and "{contact}" in route:
        route = route.replace("{contact}", contact)
    return route


def classify(text: str) -> IntentResult:
    platform, p_conf = _match_platform(text)
    action, a_conf = _match_action(text)
    contact = _extract_contact(text)
    time_info = _extract_time(text)
    # Both platform and action strong → high confidence
    confidence = 0.95 if (p_conf >= 0.85 and a_conf >= 0.85) else (p_conf + a_conf) / 2
    needs_approval = action in _WRITE_ACTIONS
    route = _route(platform, action, contact)
    return IntentResult(
        platform=platform,
        action=action,
        contact=contact,
        needs_approval=needs_approval,
        confidence=confidence,
        inbox_route=route,
        time_info=time_info,
    )
