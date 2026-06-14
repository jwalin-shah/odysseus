"""Estimate mission complexity to route to the right agent config.

The estimator inspects a mission string for three families of signals:

* keyword density of complex vs. simplifying terms
* count of distinct file / path mentions
* presence of multi-step / sequenced language

The result (``"simple"``, ``"medium"``, or ``"complex"``) keys into
:data:`AGENT_CONFIGS` so the supervisor can pick a fast, default, or
careful execution policy.
"""

import re
from typing import Dict, List, Tuple

__all__ = ["estimate_complexity", "config_for", "score_breakdown", "AGENT_CONFIGS"]

# --- Signal tables --------------------------------------------------------

# Terms that usually indicate involved, architectural work.
_COMPLEX_KEYWORDS = {
    "refactor", "redesign", "rewrite", "rearchitect", "migrate", "migration",
    "restructure", "overhaul", "integrate", "integration", "architect",
    "architecture", "distributed", "concurrent", "asynchronous", "async",
    "optimize", "optimization", "scale", "scaling", "security",
    "authenticate", "authentication", "authorization", "deploy", "deployment",
    "pipeline", "database", "schema", "transaction", "endpoint", "rest",
    "graphql", "grpc", "orchestrat", "coordinat", "synchroniz",
    "algorithm", "data-structure", "datastructure", "framework",
    "test-suite", "testsuite", "coverage", "benchmark", "concurrency",
    "threading", "multiprocess", "kubernetes", "docker", "terraform",
    "queue", "worker", "scheduler", "backoff", "retry",
}

# Terms that usually indicate trivial cleanup work.
_SIMPLE_KEYWORDS = {
    "fix", "typo", "rename", "comment", "docstring", "documentation",
    "format", "style", "lint", "whitespace", "spelling", "grammar",
    "readme", "log", "print", "string", "message", "delete", "remove",
    "strip", "trim",
}

# Phrases that imply sequenced / multi-step work.
_MULTI_STEP_PATTERNS: List[str] = [
    r"\bthen\b",
    r"\bafterwards?\b",
    r"\bbefore\b",
    r"\bfirst(?:ly)?\b",
    r"\bsecond(?:ly)?\b",
    r"\bthird(?:ly)?\b",
    r"\bnext\b",
    r"\bfinally\b",
    r"\blastly\b",
    r"\bstep\s*\d+\b",
    r"\bphase\s*\d+\b",
    r"\bonce\b",
    r"\bwhile\b",
    r"\bsubsequently\b",
    r"\bfollowed by\b",
    r"\bin order to\b",
    r"\bprior to\b",
]

# Common code/config file extensions used to detect file mentions.
_FILE_EXTENSIONS = (
    r"py|js|jsx|ts|tsx|mjs|cjs|java|kt|go|rs|swift|c|cpp|cc|cxx|h|hpp|hh|"
    r"cs|fs|rb|php|phtml|pl|sh|bash|zsh|ps1|sql|md|markdown|rst|"
    r"yaml|yml|toml|json|xml|html|htm|xhtml|css|scss|sass|less|"
    r"vue|svelte|astro|lua|r|dart|ex|exs|clj|cljs|edn|elm|hs|ml|mli|"
    r"scala|sc|groovy|gradle|properties|ini|cfg|conf|env|proto|txt"
)
_FILE_PATTERN = re.compile(r"\." + _FILE_EXTENSIONS + r"\b", re.IGNORECASE)
_PATH_PATTERN = re.compile(
    r"(?:^|[\s\"'(\[])([^\s\"'<>|\]\\]+\.[A-Za-z0-9]{1,5})\b"
)

# Conjunction-heavy words that hint at composite work.
_CONJUNCTIONS = {"and", "plus", "also", "additionally", "as", "but"}


# --- Helpers --------------------------------------------------------------

def _word_set(text: str) -> List[str]:
    """Return lowercase word tokens from ``text``."""
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)


# --- Public API -----------------------------------------------------------

def estimate_complexity(mission_text: str) -> str:
    """Classify ``mission_text`` as ``"simple"``, ``"medium"``, or ``"complex"``.

    The classification is a small additive score over four heuristics:

    1. complex keyword hits minus simple keyword hits
    2. file / path mentions in the mission body
    3. multi-step / sequencing language matches
    4. conjunction density and overall word count (soft signals)

    Thresholds are deliberately conservative: a single straightforward
    change stays "simple", a small focused task lands on "medium", and
    anything that drags in several files, complex terminology, or
    sequenced steps escalates to "complex".
    """
    if not mission_text or not mission_text.strip():
        return "simple"

    text = mission_text.lower()
    words = _word_set(text)
    word_count = max(len(words), 1)

    score = 0

    # 1) Keyword density.
    complex_hits = sum(1 for w in words if w in _COMPLEX_KEYWORDS)
    simple_hits = sum(1 for w in words if w in _SIMPLE_KEYWORDS)
    score += complex_hits
    score -= simple_hits

    # 2) File / path mentions.
    explicit_paths = set(_PATH_PATTERN.findall(mission_text))
    ext_hits = len(set(_FILE_PATTERN.findall(text)))
    # Use the larger of the two signals so a clearly written mission is
    # not penalised for spelling extensions slightly differently.
    file_signal = max(len(explicit_paths), ext_hits)
    if file_signal >= 5:
        score += 3
    elif file_signal >= 2:
        score += 2
    elif file_signal >= 1:
        score += 1

    # 3) Multi-step indicators.
    multi_step_hits = sum(
        1 for p in _MULTI_STEP_PATTERNS if re.search(p, text)
    )
    score += multi_step_hits

    # 3b) Conjunction density (a milder multi-step signal).
    conjunction_hits = sum(1 for w in words if w in _CONJUNCTIONS)
    if conjunction_hits >= 5:
        score += 2
    elif conjunction_hits >= 2:
        score += 1

    # 4) Mission length as a soft signal.
    if word_count >= 200:
        score += 2
    elif word_count >= 80:
        score += 1

    # Final thresholds.
    if score <= 1:
        return "simple"
    if score <= 4:
        return "medium"
    return "complex"


# Recommended agent configs for each complexity level. The supervisor can
# read these to decide retry budget, timeouts, and model parameters.
AGENT_CONFIGS: Dict[str, Dict] = {
    "simple": {
        "max_attempts": 1,
        "timeout_s": 300,
        "max_tokens": 4096,
        "model": "MiniMax-M3",
        "description": "Fast config for trivial missions",
    },
    "medium": {
        "max_attempts": 3,
        "timeout_s": 900,
        "max_tokens": 8192,
        "model": "MiniMax-M3",
        "description": "Default config for typical missions",
    },
    "complex": {
        "max_attempts": 5,
        "timeout_s": 1800,
        "max_tokens": 16384,
        "model": "MiniMax-M3",
        "description": "Careful config with extra retries and larger context",
    },
}


def config_for(mission_text: str) -> Dict:
    """Return the recommended agent config for a given mission text."""
    return AGENT_CONFIGS[estimate_complexity(mission_text)]


def score_breakdown(mission_text: str) -> Tuple[str, Dict[str, int]]:
    """Return ``(complexity, detail)`` - useful for debugging / telemetry."""
    if not mission_text or not mission_text.strip():
        return "simple", {"reason": "empty"}
    text = mission_text.lower()
    words = _word_set(text)
    detail = {
        "word_count": len(words),
        "complex_keyword_hits": sum(
            1 for w in words if w in _COMPLEX_KEYWORDS
        ),
        "simple_keyword_hits": sum(
            1 for w in words if w in _SIMPLE_KEYWORDS
        ),
        "explicit_file_mentions": len(set(_PATH_PATTERN.findall(mission_text))),
        "extension_hits": len(set(_FILE_PATTERN.findall(text))),
        "multi_step_hits": sum(
            1 for p in _MULTI_STEP_PATTERNS if re.search(p, text)
        ),
        "conjunction_hits": sum(1 for w in words if w in _CONJUNCTIONS),
    }
    return estimate_complexity(mission_text), detail


# --- CLI / smoke test -----------------------------------------------------

if __name__ == "__main__":
    samples = [
        ("", "simple"),
        ("Fix typo in README", "simple"),
        ("Rename variable foo to bar in src/utils.py", "simple"),
        ("Add a new helper to utils.py", "simple"),
        (
            "Refactor the auth module, then migrate to async, and add "
            "integration tests for src/auth.py and src/api.py",
            "complex",
        ),
        (
            "Implement a distributed task queue with retry, then add "
            "monitoring, then write tests for src/queue/manager.py and "
            "src/queue/worker.py",
            "complex",
        ),
        (
            "Update the changelog and bump the version number, then "
            "tag the release in CI",
            "medium",
        ),
    ]
    failures = 0
    for text, expected in samples:
        label, detail = score_breakdown(text)
        ok = label == expected
        if not ok:
            failures += 1
        flag = "ok  " if ok else "FAIL"
        snippet = (text[:55] + "...") if len(text) > 58 else text
        print(f"[{flag}] {label:6s} (want {expected:6s}) :: {snippet}")
        if not ok:
            print(f"        detail={detail}")
    if failures:
        raise SystemExit(1)