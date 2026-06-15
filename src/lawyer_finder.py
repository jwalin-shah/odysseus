"""Odysseus module — find a lawyer for a legal problem.

This module does NOT make web requests. It analyzes a free-text problem
description, detects the appropriate legal specialty, and returns a
``LawyerSearchResult`` containing:

  * a Google search query
  * an Avvo search URL
  * a ready-to-send intake email template
  * a checklist of next steps

The user copies the queries / email and does the outreach themselves.

Example
-------
>>> from src.lawyer_finder import find_lawyer
>>> result = find_lawyer(
...     "My landlord won't return my security deposit",
...     city="Portland, OR",
... )
>>> result.specialty
'tenant rights lawyer'
>>> result.google_search_query
'"tenant rights lawyer" "Portland, OR" free consultation reviews'
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Specialty detection
# ---------------------------------------------------------------------------

# Patterns are regex alternations. Order matters — first match wins.
# Patterns are matched case-insensitively.
SPECIALTY_MAP: dict[str, str] = {
    r"landlord|tenant|eviction|rent|lease|security deposit": "tenant rights lawyer",
    r"employment|fired|discrimination|workplace|wage|overtime|harassment": "employment lawyer",
    r"contract|agreement|breach|NDA|IP|patent|trademark|copyright": "business contract lawyer",
    r"divorce|custody|child support|alimony|family|adoption|prenup": "family law attorney",
    r"car accident|personal injury|slip|fall|wrongful death|malpractice": "personal injury lawyer",
    r"immigration|visa|green card|citizenship|deportation|asylum": "immigration lawyer",
    r"criminal|arrested|charges|DUI|drug|theft|assault": "criminal defense attorney",
}

DEFAULT_SPECIALTY = "general practice attorney"


def _detect_specialty(problem_description: str) -> str:
    """Return the best matching legal specialty for ``problem_description``."""
    if not problem_description or not problem_description.strip():
        return DEFAULT_SPECIALTY

    text = problem_description.lower()
    for pattern, specialty in SPECIALTY_MAP.items():
        if re.search(pattern, text, flags=re.IGNORECASE):
            return specialty
    return DEFAULT_SPECIALTY


# ---------------------------------------------------------------------------
# Search-query construction
# ---------------------------------------------------------------------------

def _normalize_city(city: str) -> str:
    return city.strip().strip('"').strip("'")


def _build_google_query(specialty: str, city: str) -> str:
    """Build a Google query the user can paste into the search bar."""
    specialty_q = f'"{specialty}"'
    if city:
        city_clean = _normalize_city(city)
        return f'{specialty_q} "{city_clean}" free consultation reviews'
    return f'{specialty_q} free consultation reviews'


def _build_avvo_url(specialty: str, city: str) -> str:
    """Build a deep link to Avvo's lawyer-finder results page."""
    parts = [specialty]
    if city:
        parts.append(_normalize_city(city))
    query = " ".join(parts).strip()
    encoded = urllib.parse.quote_plus(query)
    return f"https://www.avvo.com/find-a-lawyer?q={encoded}"


# ---------------------------------------------------------------------------
# Email template
# ---------------------------------------------------------------------------

def generate_intake_email(specialty: str, problem: str) -> str:
    """Return a ready-to-edit intake email for a prospective lawyer.

    The email contains bracketed placeholders (``[...]``) the user fills
    in before sending. Keep it short — lawyers read hundreds of these.
    """
    problem_clean = problem.strip() or "[Briefly describe your legal issue]"
    specialty_clean = specialty or DEFAULT_SPECIALTY

    return (
        f"Subject: Initial consultation inquiry — {specialty_clean} matter\n"
        f"\n"
        f"Dear [Attorney Name],\n"
        f"\n"
        f"I found your profile on [Avvo / Google] and I'm writing to ask whether "
        f"you handle {specialty_clean} matters and offer a free or low-cost "
        f"initial consultation.\n"
        f"\n"
        f"BRIEF SUMMARY\n"
        f"-------------\n"
        f"{problem_clean}\n"
        f"\n"
        f"WHAT I NEED HELP WITH\n"
        f"--------------------\n"
        f"  - Understanding my rights and options\n"
        f"  - An honest assessment of the strength of my case\n"
        f"  - Estimated cost and likely timeline\n"
        f"\n"
        f"KEY DATES & DOCUMENTS I CAN PROVIDE\n"
        f"-----------------------------------\n"
        f"  - [Date the problem started]\n"
        f"  - [Any contracts, leases, notices, photos, emails, or letters]\n"
        f"  - [Any court date or deadline, if applicable]\n"
        f"\n"
        f"Please let me know your availability for a 15–30 minute call. I'm "
        f"flexible on timing and can share additional details by phone or email.\n"
        f"\n"
        f"Thank you for your time,\n"
        f"[Your full name]\n"
        f"[Phone number]\n"
        f"[Email address]\n"
        f"[City, State]\n"
    )


# ---------------------------------------------------------------------------
# Next-steps checklist
# ---------------------------------------------------------------------------

def _build_next_steps(specialty: str, problem_description: str) -> list[str]:
    """Return a list of concrete actions the user should take."""
    text = (problem_description or "").lower()
    specialty_lc = (specialty or "").lower()

    steps: list[str] = [
        f"Run the Google search query below to surface local {specialty} options.",
        "Open the Avvo link below and shortlist 3–5 attorneys with strong reviews "
        "(4.5+ stars) and active bar membership in your state.",
        "Verify each candidate on your state bar website (license status, "
        "disciplinary history, years admitted).",
        "Prepare a one-page case timeline: key dates, people involved, and a "
        "short chronology of what happened.",
        "Gather supporting documents (contracts, photos, emails, receipts, "
        "notices) into a single folder you can share later.",
        "Email 2–3 lawyers using the intake template below. Ask explicitly about "
        "free consultations, fee structure, and estimated total cost.",
        "After responses come back, schedule consultations with your top 2 picks "
        "before signing anything.",
    ]

    # Specialty-specific urgent warnings
    if any(tok in specialty_lc for tok in ("criminal", "dui")) or "arrested" in text:
        steps.insert(
            0,
            "⚠️  URGENT: Do not speak with police, prosecutors, or anyone else "
            "about the case before a lawyer is present. Exercise your right to "
            "remain silent and ask for counsel.",
        )
    elif "immigration" in specialty_lc:
        steps.insert(
            0,
            "⚠️  Do not sign any document from USCIS, ICE, or CBP without an "
            "immigration attorney reviewing it first — some forms waive rights.",
        )
    elif "personal injury" in specialty_lc or "car accident" in text:
        steps.insert(
            0,
            "📸  Preserve evidence now: photos of the scene, vehicle damage, "
            "injuries, and any surveillance or dash-cam footage before it is "
            "overwritten.",
        )
    elif "tenant" in specialty_lc or "landlord" in text or "eviction" in text:
        steps.insert(
            0,
            "📨  Save every written communication with your landlord (texts, "
            "emails, notices). Photograph the unit's condition with timestamps.",
        )

    return steps


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class LawyerSearchResult:
    """Bundle of search and outreach material for finding a lawyer."""
    specialty: str
    google_search_query: str          # paste-able Google search
    avvo_search_url: str              # deep link to Avvo results
    email_template: str               # ready-to-edit intake email
    next_steps: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_lawyer(problem_description: str, city: str = "") -> LawyerSearchResult:
    """Analyze ``problem_description`` and return search + outreach material.

    Parameters
    ----------
    problem_description:
        Free-text description of the legal problem, e.g.
        ``"I have a landlord dispute about security deposit"``.
    city:
        Optional city for localized results, e.g. ``"Portland, OR"`` or
        ``"Brooklyn, NY"``. Empty string means no location filter.

    Returns
    -------
    LawyerSearchResult
        Contains the detected specialty, a Google query, an Avvo URL,
        a ready-to-edit intake email, and a checklist of next steps.

    Notes
    -----
    This function performs no network I/O. The user is responsible for
    actually running the searches and sending the email.
    """
    specialty = _detect_specialty(problem_description)
    google_query = _build_google_query(specialty, city)
    avvo_url = _build_avvo_url(specialty, city)
    email = generate_intake_email(specialty, problem_description)
    next_steps = _build_next_steps(specialty, problem_description)

    return LawyerSearchResult(
        specialty=specialty,
        google_search_query=google_query,
        avvo_search_url=avvo_url,
        email_template=email,
        next_steps=next_steps,
    )


__all__ = [
    "LawyerSearchResult",
    "SPECIALTY_MAP",
    "find_lawyer",
    "generate_intake_email",
]
