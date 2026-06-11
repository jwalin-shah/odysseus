# src/brain_engine.py
"""Brain-dump ingestion, structuring, storage, and context retrieval.

Accepts raw brain-dump text, uses an LLM to structure it into categories
(decisions, projects, context, preferences), stores the result as a dated
markdown file with YAML frontmatter under ``knowledge-base/``, and maintains
a cached context-prefix string that other modules can inject into system
prompts for continuity across conversations.

Storage layout::

    knowledge-base/
        2026-06-10/
            project-architecture-decisions.md
            minimax-api-integration.md
        2026-06-11/
            ...
        _cache/
            context_prefix.md
"""

from __future__ import annotations

import fcntl
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from core.constants import BASE_DIR
from src.settings import get_setting

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────

KB_DIR = os.path.join(BASE_DIR, "knowledge-base")
CACHE_DIR = os.path.join(KB_DIR, "_cache")
CACHE_FILE = os.path.join(CACHE_DIR, "context_prefix.md")
LOCK_FILE = os.path.join(CACHE_DIR, ".lock")

# ── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_CONTEXT_DAYS = 7
MAX_CONTEXT_CHARS = 16_000  # ~4000 tokens

# ── Structuring prompt ───────────────────────────────────────────────────────

_STRUCTURING_PROMPT = """\
You are a structured-note assistant.  The user will give you a raw brain dump
— a stream-of-consciousness block of text about their work, decisions,
projects, or preferences.

Your job:
1. Read the dump carefully.
2. Output a **single** markdown document with YAML frontmatter.

The frontmatter MUST contain exactly these fields:
  - title: a concise (<60 chars) descriptive title
  - categories: a YAML list drawn from: decision, project, context, preference, idea, task
  - tags: a YAML list of 1-5 short lowercase tags
  - date: today's date in YYYY-MM-DD format
  - source: "brain-dump"

After the closing `---` write the body as clean, well-organized markdown.
Group related points under headings (##). Preserve all factual content — do
NOT invent information.

Example output:

---
title: Switch to FastAPI for the API layer
categories:
  - decision
  - project
tags:
  - fastapi
  - architecture
  - backend
date: {today}
source: brain-dump
---

## Decision

We are switching the API layer from Flask to FastAPI for async support …

## Rationale

…
"""


# ── Slug helpers ─────────────────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 60) -> str:
    """Generate a URL/filesystem-safe slug from *text*.

    Lowercase, spaces → hyphens, strip non-alphanumeric (except hyphens),
    collapse runs of hyphens, truncate to *max_len*.
    """
    slug = text.lower().strip()
    slug = slug.replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len] if slug else "untitled"


# ── File locking ─────────────────────────────────────────────────────────────

class _FileLock:
    """Simple advisory file lock using ``fcntl.flock``."""

    def __init__(self, path: str) -> None:
        self._path = path

    def __enter__(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._fd = open(self._path, "w")
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        self._fd.close()


# ── Frontmatter parsing ─────────────────────────────────────────────────────

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split *text* into (frontmatter_dict, markdown_body).

    Returns ``({}, text)`` if no valid frontmatter is found.
    """
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    body = text[m.end():]
    return fm, body


# ── Core public API ─────────────────────────────────────────────────────────

async def ingest_brain_dump(text: str, owner: str | None = None) -> dict:
    """Structure and store a brain dump.

    Calls the utility LLM endpoint to convert raw text into a structured
    markdown document, writes it to ``knowledge-base/{date}/{slug}.md``,
    and regenerates the context-prefix cache.

    Returns:
        ``{"slug": str, "path": str, "categories": list[str]}``
    """
    from src.llm_core import llm_call_async
    from src.endpoint_resolver import resolve_endpoint

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Resolve the utility endpoint for structuring
    url, model, headers = resolve_endpoint("utility", owner=owner)
    if not url or not model:
        raise RuntimeError(
            "No utility (or default) LLM endpoint configured. "
            "Please configure one in Settings → Models."
        )

    prompt = _STRUCTURING_PROMPT.format(today=today)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]

    raw_response = await llm_call_async(
        url=url,
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=4096,
        headers=headers,
        prompt_type="brain-structure",
    )

    # Parse the structured output
    frontmatter, body = _parse_frontmatter(raw_response.strip())

    # Derive slug from title or first line
    title = frontmatter.get("title", "")
    if not title:
        # Fall back to first non-empty line of body
        for line in body.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped:
                title = stripped
                break
        title = title or "brain-dump"

    slug = _slugify(title)
    categories = frontmatter.get("categories", [])

    # Ensure date in frontmatter
    if "date" not in frontmatter:
        frontmatter["date"] = today

    # Rebuild the full document
    fm_block = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip()
    full_doc = f"---\n{fm_block}\n---\n\n{body.strip()}\n"

    # Write to disk
    date_dir = os.path.join(KB_DIR, today)
    os.makedirs(date_dir, exist_ok=True)

    # Avoid collisions — append a numeric suffix if slug already exists
    filepath = os.path.join(date_dir, f"{slug}.md")
    counter = 1
    while os.path.exists(filepath):
        filepath = os.path.join(date_dir, f"{slug}-{counter}.md")
        counter += 1

    with _FileLock(LOCK_FILE):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_doc)

    rel_path = os.path.relpath(filepath, BASE_DIR)
    logger.info("Brain dump stored: %s (%s)", rel_path, categories)

    # Regenerate cache in the background (fast enough to do inline)
    try:
        regenerate_cache()
    except Exception:
        logger.warning("Failed to regenerate brain cache", exc_info=True)

    return {
        "slug": slug,
        "path": rel_path,
        "categories": categories,
    }


def get_recent_entries(days: int = 7) -> list[dict]:
    """Return recent brain entries sorted newest-first.

    Each entry is a dict with keys:
    ``date, slug, path, frontmatter, content``.
    """
    if days <= 0:
        days = DEFAULT_CONTEXT_DAYS

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    entries: list[dict] = []

    if not os.path.isdir(KB_DIR):
        return entries

    for dirname in sorted(os.listdir(KB_DIR), reverse=True):
        if dirname.startswith("_") or dirname.startswith("."):
            continue
        try:
            dir_date = datetime.strptime(dirname, "%Y-%m-%d").date()
        except ValueError:
            continue
        if dir_date < cutoff:
            break  # sorted descending — everything after is older

        date_dir = os.path.join(KB_DIR, dirname)
        if not os.path.isdir(date_dir):
            continue

        for fname in sorted(os.listdir(date_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(date_dir, fname)
            try:
                raw = Path(fpath).read_text(encoding="utf-8")
            except OSError:
                continue

            frontmatter, body = _parse_frontmatter(raw)
            slug = fname[:-3]  # strip .md
            entries.append({
                "date": dirname,
                "slug": slug,
                "path": os.path.relpath(fpath, BASE_DIR),
                "frontmatter": frontmatter,
                "content": body.strip(),
            })

    return entries


def build_context_prefix(days: int = 7, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """Build the system-prompt prefix from recent brain entries.

    Entries are added newest-first; if the accumulated text exceeds
    *max_chars* the oldest entries are dropped.
    """
    if days <= 0:
        days = int(get_setting("brain_context_days", DEFAULT_CONTEXT_DAYS))

    entries = get_recent_entries(days=days)
    if not entries:
        return ""

    sections: list[str] = []
    total_len = 0

    for entry in entries:
        slug = entry["slug"]
        date = entry["date"]
        content = entry["content"]

        section = f"### {date}: {slug}\n\n{content}\n"
        if total_len + len(section) > max_chars:
            break  # stop adding — oldest entries are dropped first
        sections.append(section)
        total_len += len(section)

    if not sections:
        return ""

    header = "## Brain Context (Recent Decisions & Notes)\n\n"
    return header + "\n".join(sections)


def get_cached_context_prefix() -> str:
    """Read the cached context prefix from disk.

    Fast path — a single file read, no directory traversal.
    Returns an empty string if the cache file does not exist.
    """
    try:
        return Path(CACHE_FILE).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError:
        logger.warning("Failed to read brain cache", exc_info=True)
        return ""


def regenerate_cache() -> None:
    """Rebuild the cached context-prefix file.

    Called after every new brain dump so subsequent reads are instant.
    Uses file locking to avoid partial writes under concurrency.
    """
    days = int(get_setting("brain_context_days", DEFAULT_CONTEXT_DAYS))
    prefix = build_context_prefix(days=days)

    os.makedirs(CACHE_DIR, exist_ok=True)

    with _FileLock(LOCK_FILE):
        tmp_path = CACHE_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(prefix)
        os.replace(tmp_path, CACHE_FILE)

    logger.debug("Brain cache regenerated (%d chars)", len(prefix))


def delete_entry(slug: str) -> bool:
    """Delete a brain entry by slug across all date directories.

    Returns True if a file was deleted, False if not found.
    Regenerates the cache after deletion.
    """
    if not os.path.isdir(KB_DIR):
        return False

    for dirname in os.listdir(KB_DIR):
        if dirname.startswith("_") or dirname.startswith("."):
            continue
        fpath = os.path.join(KB_DIR, dirname, f"{slug}.md")
        if os.path.isfile(fpath):
            with _FileLock(LOCK_FILE):
                os.remove(fpath)
            # Clean up empty date dirs
            date_dir = os.path.join(KB_DIR, dirname)
            remaining = [f for f in os.listdir(date_dir) if f.endswith(".md")]
            if not remaining:
                try:
                    os.rmdir(date_dir)
                except OSError:
                    pass
            try:
                regenerate_cache()
            except Exception:
                logger.warning("Failed to regenerate brain cache after delete", exc_info=True)
            return True

    return False
