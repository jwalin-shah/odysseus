# routes/orchestration_routes.py
"""Orchestration observability endpoints + the traced /api/route dispatcher.

/api/route            POST — classify + dispatch via core.router.TaskRouter,
                              with a trace receipt recorded on every call
                              (success, failure, or exception — never a 500;
                              errors are returned in-band per the contract).
/api/orchestration/traces  GET — raw receipts, newest first, paginated.
/api/orchestration/stats   GET — 24h/7d aggregates, fixed cardinality.
/api/orchestration/health  GET — probes: quota freshness, CLI liveness,
                                  consecutive-failure streak.
"""

import logging
import time
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from core import orchestration_trace as otrace

logger = logging.getLogger(__name__)


class RouteRequest(BaseModel):
    task: str
    type: Literal["code", "research", "chat", "auto"] = "auto"


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

    @router.post("/route")
    async def route(req: RouteRequest) -> Dict[str, Any]:
        started = time.time()
        try:
            result = await _get_task_router().route(req.task, req.type)
        except Exception as exc:  # contract: in-band errors, never a 500
            logger.exception("route dispatch raised")
            result = {
                "response": "",
                "model_used": "unknown",
                "tokens": 0,
                "classification": req.type,
                "error": True,
                "error_detail": str(exc),
            }
        latency_ms = (time.time() - started) * 1000
        otrace.record_trace(
            task=req.task,
            classification=str(result.get("classification", req.type)),
            model_used=str(result.get("model_used", "unknown")),
            tokens=int(result.get("tokens", 0) or 0),
            latency_ms=latency_ms,
            success=not result.get("error"),
            # router contract: error results set error=True and carry the
            # message in `response` (or error_detail when we caught a raise)
            error=result.get("error_detail")
            or (str(result.get("response", ""))[:500] if result.get("error") else None),
        )
        return result

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
