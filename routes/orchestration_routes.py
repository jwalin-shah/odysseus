# routes/orchestration_routes.py
"""Orchestration observability endpoints + the traced /api/route dispatcher.

/api/route                        POST — classify + dispatch via core.router.TaskRouter,
                                          with a trace receipt recorded on every call
                                          (success, failure, or exception — never a 500;
                                          errors are returned in-band per the contract).
                                          When classification=="code" and sync==False
                                          (default), the CLI call is submitted as a
                                          background task and the run_id is returned
                                          immediately (no blocking).
                                          Pass sync=true in the request body to force the
                                          old blocking behaviour.
/api/route/{run_id}               GET  — poll the status of an async code run.
/api/route/{run_id}/followup      POST — resume a claude session: runs
                                          `claude --resume <session_id> -p <message>`
                                          in the background via the same adapter/account
                                          as the original run. Returns a new run_id
                                          linked to the parent via parent_run_id.
                                          Non-claude providers or runs without a
                                          session_id return an in-band error (never 500).
/api/orchestration/traces         GET  — raw receipts, newest first, paginated.
/api/orchestration/stats          GET  — 24h/7d aggregates, fixed cardinality.
/api/orchestration/health         GET  — probes: quota freshness, CLI liveness,
                                          consecutive-failure streak.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core import orchestration_trace as otrace
from core import code_run_store as run_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Unified ledger integration
# ---------------------------------------------------------------------------
# The otrace stream (orchestration_trace.record_trace) is the existing
# per-request SQLite trace. The unified ledger at
# ~/projects/odysseus/.ledger/ is the new append-only JSONL stream that
# consolidates otrace + m3lab + agent-rules. Every dispatch recorded to
# otrace is also written to the unified ledger via _record_dispatch.
#
# Both writes are best-effort: a failure in one must not break the other
# or the dispatch itself. The unified ledger import is wrapped in
# try/except so a missing ledger (e.g. in tests) does not break the route.

_LEDGER_DIR = os.path.expanduser("~/projects/odysseus/.ledger")
if _LEDGER_DIR not in sys.path and os.path.isdir(_LEDGER_DIR):
    sys.path.insert(0, _LEDGER_DIR)

_LEDGER_OK = False
_ledger_append = None  # type: ignore[assignment]
try:
    from odyssey_ledger import append_event as _ledger_append  # noqa: F401
    _LEDGER_OK = True
except Exception as _ledger_exc:
    logger.debug("unified ledger import failed (non-critical): %s", _ledger_exc)


def _record_dispatch(
    *,
    task: str,
    classification: str,
    model_used: str,
    tokens: int,
    latency_ms: float,
    success: bool,
    error: Optional[str],
    source: str,
    actor: str = "router",
) -> None:
    """Record a dispatch to both otrace and the unified ledger.

    Both writes are best-effort. otrace is the existing per-request
    SQLite trace; the unified ledger is the new append-only JSONL
    stream at ~/projects/odyssey/.ledger/ that consolidates otrace +
    m3lab + agent-rules. The two are kept in sync so the architecture
    doc's "one unified ledger" goal holds without dropping the
    existing otrace observability surface.
    """
    try:
        otrace.record_trace(
            task=task,
            classification=classification,
            model_used=model_used,
            tokens=tokens,
            latency_ms=latency_ms,
            success=success,
            error=error,
            source=source,
        )
    except Exception as exc:
        logger.debug("otrace.record_trace failed (non-critical): %s", exc)
    if _LEDGER_OK and _ledger_append is not None:
        try:
            _ledger_append(
                source_system="odysseus",
                subject=otrace.task_hash(task) if task else f"run-{source}",
                subject_kind="route",
                actor=actor,
                task_type=classification,
                outcome="success" if success else "failure",
                duration_s=latency_ms / 1000.0,
                tokens_in=int(tokens or 0),
                error=error,
                forensic={"model_used": model_used, "source": source},
                source_file="orchestration_routes.py",
            )
        except Exception as exc:
            logger.debug("unified ledger append failed (non-critical): %s", exc)


class RouteRequest(BaseModel):
    task: str
    type: Literal["code", "research", "chat", "auto"] = "auto"
    # sync=True forces the legacy blocking behaviour. Default is False so
    # code tasks return immediately with a run_id instead of blocking for
    # up to 300s while the CLI runs.
    sync: bool = False


class FollowupRequest(BaseModel):
    message: str


def setup_orchestration_routes(task_router: Optional[Any] = None) -> APIRouter:
    """Build the router. ``task_router`` is a core.router.TaskRouter; if None,
    one is constructed lazily so the observability endpoints work even when
    routing is unavailable."""
    router = APIRouter(prefix="/api", tags=["orchestration"])

    def _get_task_router():
        nonlocal task_router
        if task_router is None:
            from core.router import TaskRouter

            task_router = TaskRouter()
        return task_router

    # ------------------------------------------------------------------
    # POST /api/route — classify + dispatch (async for code, sync for rest)
    # ------------------------------------------------------------------

    @router.post("/route")
    async def route(req: RouteRequest) -> Dict[str, Any]:
        started = time.time()

        # Step 1: classify without dispatching (so we can branch on type).
        try:
            classified = await _get_task_router().classify_task_async(
                req.task, hint=req.type
            )
        except Exception as exc:
            logger.exception("classify_task_async raised")
            classified = req.type if req.type != "auto" else "chat"

        # Step 2a: async path — code task + no sync flag → submit background job.
        if classified == "code" and not req.sync:
            run_id = run_store.create_run(req.task)

            async def _run_code_background(run_id: str, task: str) -> None:
                """Background coroutine: run CLI, update store, finalize trace."""
                bg_start = time.time()
                run_store.mark_running(run_id)
                try:
                    result = await _get_task_router().route_code(task)
                except Exception as exc:
                    result = {
                        "response": f"Background dispatch error: {exc}",
                        "model_used": "unknown",
                        "tokens": 0,
                        "provider": "unknown",
                        "error": True,
                    }
                bg_latency_ms = (time.time() - bg_start) * 1000
                success = not result.get("error")
                run_store.finalize_run(
                    run_id,
                    success=success,
                    result=result.get("response", ""),
                    error=result.get("error_detail")
                    or (str(result.get("response", ""))[:500] if not success else None),
                    tokens=int(result.get("tokens", 0) or 0),
                    latency_ms=bg_latency_ms,
                    session_id=result.get("session_id"),
                    adapter_name=result.get("provider"),
                )
                # Completion trace — records final cost/latency for the stats layer.
                _record_dispatch(
                    task=task,
                    classification="code",
                    model_used=str(result.get("model_used", "unknown")),
                    tokens=int(result.get("tokens", 0) or 0),
                    latency_ms=bg_latency_ms,
                    success=success,
                    error=result.get("error_detail")
                    or (str(result.get("response", ""))[:500] if not success else None),
                    source="router_async_completion",
                )
                logger.info(
                    "Async code run %s completed: success=%s tokens=%d latency=%.0fms",
                    run_id, success, int(result.get("tokens", 0) or 0), bg_latency_ms,
                )

            asyncio.create_task(_run_code_background(run_id, req.task))

            # Submission trace — records that the task was accepted.
            submit_latency_ms = (time.time() - started) * 1000
            _record_dispatch(
                task=req.task,
                classification="code",
                model_used="pending",
                tokens=0,
                latency_ms=submit_latency_ms,
                success=True,
                error=None,
                source="router_async_submission",
            )

            return {
                "run_id": run_id,
                "status": "submitted",
                "classification": "code",
                "response": None,
                "model_used": "pending",
                "tokens": 0,
                "provider": "pending",
                "poll_url": f"/api/route/{run_id}",
            }

        # Step 2b: synchronous path — research, chat, or code with sync=True.
        try:
            if classified == "code":
                # sync=True explicitly requested — call route_code directly.
                result = await _get_task_router().route_code(req.task)
                result["classification"] = "code"
            else:
                # For non-code types, use the full route() which handles
                # research and chat dispatch.
                result = await _get_task_router().route(req.task, classified)
        except Exception as exc:  # contract: in-band errors, never a 500
            logger.exception("route dispatch raised")
            result = {
                "response": "",
                "model_used": "unknown",
                "tokens": 0,
                "classification": classified,
                "error": True,
                "error_detail": str(exc),
            }

        latency_ms = (time.time() - started) * 1000
        _record_dispatch(
            task=req.task,
            classification=str(result.get("classification", classified)),
            model_used=str(result.get("model_used", "unknown")),
            tokens=int(result.get("tokens", 0) or 0),
            latency_ms=latency_ms,
            success=not result.get("error"),
            error=result.get("error_detail")
            or (str(result.get("response", ""))[:500] if result.get("error") else None),
            source="router_sync",
        )
        return result

    # ------------------------------------------------------------------
    # GET /api/route/{run_id} — poll async code run status
    # ------------------------------------------------------------------

    @router.get("/route/{run_id}")
    async def run_status(run_id: str) -> Dict[str, Any]:
        """Poll the status of an async code run submitted via POST /api/route
        with sync=false (the default for code tasks).

        Returns:
          - status: "submitted" | "running" | "success" | "error"
          - result: the CLI output (once complete)
          - error: error message if status=="error"
          - tokens, latency_ms: filled on completion
          - session_id: claude session_id if available (claude provider only)
          - adapter_name: the CLI adapter used (e.g. "claude-ca", "codex")
        """
        rec = run_store.get_run(run_id)
        if rec is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
        return rec

    # ------------------------------------------------------------------
    # POST /api/route/{run_id}/followup — resume a claude session
    # ------------------------------------------------------------------

    @router.post("/route/{run_id}/followup")
    async def followup(run_id: str, req: FollowupRequest) -> Dict[str, Any]:
        """Continue a previous claude code run via session resume.

        Looks up the original run's session_id and adapter_name.  For
        claude runs, dispatches ``claude --resume <session_id> -p <message>``
        in the background using the same account (CLAUDE_CONFIG_DIR) as the
        original.  Returns a new run_id linked to the parent via
        parent_run_id.

        In-band errors (never 500):
          - 404-like in-band error if run_id not found
          - error:True if the original run has no session_id (non-claude or
            not yet completed)
          - error:True if the adapter does not support resume (codex, gemini)
        """
        started = time.time()

        parent_rec = run_store.get_run(run_id)
        if parent_rec is None:
            return {
                "run_id": None,
                "status": "error",
                "classification": "code",
                "response": f"Run '{run_id}' not found",
                "model_used": "unknown",
                "tokens": 0,
                "provider": "unknown",
                "error": True,
                "error_detail": f"parent run_id '{run_id}' not found",
                "parent_run_id": run_id,
            }

        session_id = parent_rec.get("session_id")
        adapter_name = parent_rec.get("adapter_name")

        if not session_id:
            return {
                "run_id": None,
                "status": "error",
                "classification": "code",
                "response": "Followup not supported: original run has no session_id (may not be a claude run, or run not yet complete)",
                "model_used": "unknown",
                "tokens": 0,
                "provider": adapter_name or "unknown",
                "error": True,
                "error_detail": "no session_id on parent run",
                "parent_run_id": run_id,
            }

        # Validate adapter supports resume before firing background task
        from core.router import _CLI_ADAPTERS
        adapter = next(
            (a for a in _CLI_ADAPTERS if a["name"] == adapter_name and a.get("supports_resume")),
            None,
        )
        if adapter is None:
            return {
                "run_id": None,
                "status": "error",
                "classification": "code",
                "response": f"Followup not supported for provider '{adapter_name}': only claude adapters support session resume",
                "model_used": "unknown",
                "tokens": 0,
                "provider": adapter_name or "unknown",
                "error": True,
                "error_detail": f"adapter '{adapter_name}' does not support resume",
                "parent_run_id": run_id,
            }

        followup_run_id = run_store.create_run(req.message, parent_run_id=run_id)

        async def _run_followup_background(
            frun_id: str, message: str, sess_id: str, adp_name: str
        ) -> None:
            bg_start = time.time()
            run_store.mark_running(frun_id)
            try:
                result = await _get_task_router().route_code_resume(
                    message, session_id=sess_id, adapter_name=adp_name
                )
            except Exception as exc:
                result = {
                    "response": f"Followup dispatch error: {exc}",
                    "model_used": "unknown",
                    "tokens": 0,
                    "provider": adp_name,
                    "error": True,
                }
            bg_latency_ms = (time.time() - bg_start) * 1000
            success = not result.get("error")
            run_store.finalize_run(
                frun_id,
                success=success,
                result=result.get("response", ""),
                error=result.get("error_detail")
                or (str(result.get("response", ""))[:500] if not success else None),
                tokens=int(result.get("tokens", 0) or 0),
                latency_ms=bg_latency_ms,
                session_id=result.get("session_id"),
                adapter_name=result.get("provider"),
            )
            _record_dispatch(
                task=message,
                classification="code",
                model_used=str(result.get("model_used", "unknown")),
                tokens=int(result.get("tokens", 0) or 0),
                latency_ms=bg_latency_ms,
                success=success,
                error=result.get("error_detail")
                or (str(result.get("response", ""))[:500] if not success else None),
                source="router_followup",
            )
            logger.info(
                "Followup run %s (parent=%s) completed: success=%s latency=%.0fms",
                frun_id, run_id, success, bg_latency_ms,
            )

        asyncio.create_task(
            _run_followup_background(followup_run_id, req.message, session_id, adapter_name)
        )

        submit_latency_ms = (time.time() - started) * 1000
        _record_dispatch(
            task=req.message,
            classification="code",
            model_used="pending",
            tokens=0,
            latency_ms=submit_latency_ms,
            success=True,
            error=None,
            source="router_followup_submission",
        )

        return {
            "run_id": followup_run_id,
            "status": "submitted",
            "classification": "code",
            "response": None,
            "model_used": "pending",
            "tokens": 0,
            "provider": adapter_name,
            "poll_url": f"/api/route/{followup_run_id}",
            "parent_run_id": run_id,
        }

    # ------------------------------------------------------------------
    # GET /api/orchestration/traces
    # ------------------------------------------------------------------

    @router.get("/orchestration/traces")
    async def traces(
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        since_hours: Optional[float] = Query(None, gt=0),
    ) -> Dict[str, Any]:
        since_unix = time.time() - since_hours * 3600 if since_hours else None
        rows = otrace.read_traces(limit=limit, offset=offset, since_unix=since_unix)
        return {"traces": rows, "count": len(rows), "offset": offset}

    @router.get("/orchestration/stats")
    async def stats() -> Dict[str, Any]:
        return otrace.compute_stats()

    @router.get("/orchestration/health")
    async def health() -> Dict[str, Any]:
        return otrace.compute_health()

    return router
