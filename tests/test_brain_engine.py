"""Tests for src.brain_engine — slugging, frontmatter, storage, cache, ingestion.

Filesystem tests run against a tmp_path-backed knowledge base; the LLM call
in ingest_brain_dump is mocked.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

import src.brain_engine as brain
from src.brain_engine import (
    _parse_frontmatter,
    _slugify,
    build_context_prefix,
    delete_entry,
    get_cached_context_prefix,
    get_recent_entries,
    ingest_brain_dump,
    regenerate_cache,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kb(tmp_path, monkeypatch):
    """Point the brain engine at a temporary knowledge base."""
    kb_dir = str(tmp_path / "knowledge-base")
    cache_dir = os.path.join(kb_dir, "_cache")
    monkeypatch.setattr(brain, "KB_DIR", kb_dir)
    monkeypatch.setattr(brain, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(brain, "CACHE_FILE", os.path.join(cache_dir, "context_prefix.md"))
    monkeypatch.setattr(brain, "LOCK_FILE", os.path.join(cache_dir, ".lock"))
    return kb_dir


def _write_entry(kb_dir: str, date: str, slug: str, title: str = "", body: str = "Body text."):
    date_dir = os.path.join(kb_dir, date)
    os.makedirs(date_dir, exist_ok=True)
    title = title or slug
    doc = (
        f"---\n"
        f"title: {title}\n"
        f"categories:\n  - decision\n"
        f"tags:\n  - test\n"
        f"date: {date}\n"
        f"source: brain-dump\n"
        f"---\n\n{body}\n"
    )
    with open(os.path.join(date_dir, f"{slug}.md"), "w", encoding="utf-8") as f:
        f.write(doc)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic(self):
        assert _slugify("Switch to FastAPI") == "switch-to-fastapi"

    def test_strips_special_chars(self):
        assert _slugify("Hello, World! (v2)") == "hello-world-v2"

    def test_collapses_hyphens(self):
        assert _slugify("a -- b") == "a-b"

    def test_truncates(self):
        assert len(_slugify("x" * 200)) == 60

    def test_empty_falls_back(self):
        assert _slugify("!!!") == "untitled"


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid(self):
        fm, body = _parse_frontmatter("---\ntitle: T\ntags:\n  - a\n---\nbody here")
        assert fm == {"title": "T", "tags": ["a"]}
        assert body == "body here"

    def test_no_frontmatter(self):
        fm, body = _parse_frontmatter("just text")
        assert fm == {}
        assert body == "just text"

    def test_invalid_yaml(self):
        text = "---\n: [unbalanced\n---\nbody"
        fm, body = _parse_frontmatter(text)
        assert fm == {}
        assert body == text


# ---------------------------------------------------------------------------
# get_recent_entries
# ---------------------------------------------------------------------------


class TestGetRecentEntries:
    def test_empty_kb(self, kb):
        assert get_recent_entries() == []

    def test_returns_recent_skips_old(self, kb):
        _write_entry(kb, _today(), "fresh")
        _write_entry(kb, _days_ago(30), "stale")
        entries = get_recent_entries(days=7)
        assert [e["slug"] for e in entries] == ["fresh"]

    def test_newest_first(self, kb):
        _write_entry(kb, _days_ago(2), "older")
        _write_entry(kb, _today(), "newer")
        entries = get_recent_entries(days=7)
        assert [e["slug"] for e in entries] == ["newer", "older"]

    def test_skips_cache_and_non_date_dirs(self, kb):
        _write_entry(kb, _today(), "real")
        os.makedirs(os.path.join(kb, "_cache"), exist_ok=True)
        os.makedirs(os.path.join(kb, "not-a-date"), exist_ok=True)
        entries = get_recent_entries(days=7)
        assert [e["slug"] for e in entries] == ["real"]

    def test_parses_frontmatter(self, kb):
        _write_entry(kb, _today(), "entry", title="My Title")
        e = get_recent_entries(days=7)[0]
        assert e["frontmatter"]["title"] == "My Title"
        assert e["content"] == "Body text."


# ---------------------------------------------------------------------------
# build_context_prefix
# ---------------------------------------------------------------------------


class TestBuildContextPrefix:
    def test_empty(self, kb):
        assert build_context_prefix(days=7) == ""

    def test_includes_entries(self, kb):
        _write_entry(kb, _today(), "alpha", body="Alpha decision.")
        ctx = build_context_prefix(days=7)
        assert ctx.startswith("## Brain Context")
        assert "alpha" in ctx
        assert "Alpha decision." in ctx

    def test_max_chars_drops_oldest(self, kb):
        _write_entry(kb, _today(), "keep", body="K" * 100)
        _write_entry(kb, _days_ago(1), "drop", body="D" * 100)
        ctx = build_context_prefix(days=7, max_chars=200)
        assert "keep" in ctx
        assert "drop" not in ctx


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class TestCache:
    def test_missing_cache_returns_empty(self, kb):
        assert get_cached_context_prefix() == ""

    def test_regenerate_then_read(self, kb):
        _write_entry(kb, _today(), "cached-entry", body="Cached content.")
        regenerate_cache()
        ctx = get_cached_context_prefix()
        assert "cached-entry" in ctx
        assert "Cached content." in ctx

    def test_regenerate_empty_kb_writes_empty(self, kb):
        regenerate_cache()
        assert get_cached_context_prefix() == ""


# ---------------------------------------------------------------------------
# delete_entry
# ---------------------------------------------------------------------------


class TestDeleteEntry:
    def test_delete_existing(self, kb):
        _write_entry(kb, _today(), "doomed")
        assert delete_entry("doomed") is True
        assert get_recent_entries(days=7) == []
        # Empty date dir was removed
        assert not os.path.isdir(os.path.join(kb, _today()))

    def test_delete_missing(self, kb):
        assert delete_entry("ghost") is False

    def test_delete_updates_cache(self, kb):
        _write_entry(kb, _today(), "transient")
        regenerate_cache()
        assert "transient" in get_cached_context_prefix()
        delete_entry("transient")
        assert "transient" not in get_cached_context_prefix()


# ---------------------------------------------------------------------------
# ingest_brain_dump (mocked LLM)
# ---------------------------------------------------------------------------


STRUCTURED_RESPONSE = """\
---
title: Test Decision About Routing
categories:
  - decision
tags:
  - routing
date: 2026-06-10
source: brain-dump
---

## Decision

We route code tasks to the Claude CLI.
"""


class TestIngestBrainDump:
    def _run(self, kb, response=STRUCTURED_RESPONSE):
        with patch("src.endpoint_resolver.resolve_endpoint",
                   return_value=("http://x/v1/chat/completions", "test-model", {})), \
             patch("src.llm_core.llm_call_async", new=AsyncMock(return_value=response)):
            return asyncio.run(ingest_brain_dump(text="raw dump"))

    def test_stores_structured_file(self, kb):
        result = self._run(kb)
        assert result["slug"] == "test-decision-about-routing"
        assert result["categories"] == ["decision"]
        entries = get_recent_entries(days=7)
        assert len(entries) == 1
        assert "route code tasks" in entries[0]["content"].lower()

    def test_regenerates_cache(self, kb):
        self._run(kb)
        assert "test-decision-about-routing" in get_cached_context_prefix()

    def test_slug_collision_appends_suffix(self, kb):
        first = self._run(kb)
        second = self._run(kb)
        assert first["slug"] == second["slug"]  # slug name reported the same
        # but two distinct files exist
        assert len(get_recent_entries(days=7)) == 2

    def test_no_frontmatter_falls_back_to_first_line(self, kb):
        result = self._run(kb, response="Plain response with no frontmatter.\nMore text.")
        assert result["slug"] == "plain-response-with-no-frontmatter"

    def test_no_endpoint_raises(self, kb):
        with patch("src.endpoint_resolver.resolve_endpoint",
                   return_value=(None, None, {})):
            with pytest.raises(RuntimeError, match="endpoint"):
                asyncio.run(ingest_brain_dump(text="raw dump"))
