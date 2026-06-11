# routes/brain_routes.py
"""Brain-dump ingestion and context retrieval routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Query, Request

from src.auth_helpers import get_current_user, require_user
from src.brain_engine import (
    build_context_prefix,
    delete_entry,
    get_cached_context_prefix,
    get_recent_entries,
    ingest_brain_dump,
)

logger = logging.getLogger(__name__)


def setup_brain_routes():
    """Set up brain-dump ingestion and context retrieval routes."""
    router = APIRouter(prefix="/api/brain", tags=["brain"])

    def _owner(request: Request) -> Optional[str]:
        return get_current_user(request)

    # ── POST /api/brain/dump ─────────────────────────────────────────────

    @router.post("/dump")
    async def brain_dump(request: Request):
        """Accept a brain dump, structure it via LLM, and store.

        Accepts either JSON ``{"text": "..."}`` or a form field ``text``.
        """
        user = require_user(request)

        # Accept JSON or form data
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
            text = body.get("text", "").strip()
        else:
            form = await request.form()
            text = (form.get("text") or "").strip()

        if not text:
            raise HTTPException(400, "Missing or empty 'text' field.")

        if len(text) > 100_000:
            raise HTTPException(413, "Brain dump too large (max 100 KB).")

        try:
            result = await ingest_brain_dump(text=text, owner=user or None)
        except RuntimeError as e:
            raise HTTPException(503, str(e))
        except Exception:
            logger.exception("Brain dump ingestion failed")
            raise HTTPException(500, "Failed to process brain dump.")

        return result

    # ── GET /api/brain/context ───────────────────────────────────────────

    @router.get("/context")
    async def brain_context():
        """Return the cached brain-context prefix.

        Fast path — reads a single cache file, no LLM calls.
        """
        ctx = get_cached_context_prefix()
        # Count entries from the full list for the response metadata
        from src.settings import get_setting
        days = int(get_setting("brain_context_days", 7))
        entries = get_recent_entries(days=days)

        return {
            "context": ctx,
            "entry_count": len(entries),
            "days": days,
        }

    # ── GET /api/brain/list ──────────────────────────────────────────────

    @router.get("/list")
    async def brain_list(days: int = Query(default=7, ge=1, le=365)):
        """List recent brain entries."""
        entries = get_recent_entries(days=days)

        return {
            "entries": [
                {
                    "date": e["date"],
                    "slug": e["slug"],
                    "type": (e["frontmatter"].get("categories") or ["unknown"])[0],
                    "tags": e["frontmatter"].get("tags", []),
                    "title": e["frontmatter"].get("title", e["slug"]),
                }
                for e in entries
            ]
        }

    # ── DELETE /api/brain/{slug} ─────────────────────────────────────────

    @router.delete("/{slug}")
    async def brain_delete(slug: str, request: Request):
        """Delete a specific brain entry by slug."""
        require_user(request)

        if not slug or len(slug) > 100:
            raise HTTPException(400, "Invalid slug.")

        deleted = delete_entry(slug)
        if not deleted:
            raise HTTPException(404, f"Brain entry '{slug}' not found.")

        return {"ok": True, "deleted": slug}

    return router
