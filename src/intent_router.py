from dataclasses import dataclass
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

_CONTACT_RE = re.compile(
    r"(?:to|from|with|for|reply to|send to|ask)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    re.IGNORECASE,
)


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
    if m:
        return m.group(1).strip()
    return None


def _route(platform: str, action: str, contact: Optional[str]) -> str:
    route = _ACTION_ROUTES.get((platform, action), _PLATFORM_ROUTES.get(platform, ""))
    if contact and "{contact}" in route:
        route = route.replace("{contact}", contact)
    return route


def classify(text: str) -> IntentResult:
    platform, p_conf = _match_platform(text)
    action, a_conf = _match_action(text)
    contact = _extract_contact(text)
    confidence = (p_conf + a_conf) / 2
    needs_approval = action in _WRITE_ACTIONS
    route = _route(platform, action, contact)
    return IntentResult(
        platform=platform,
        action=action,
        contact=contact,
        needs_approval=needs_approval,
        confidence=confidence,
        inbox_route=route,
    )
