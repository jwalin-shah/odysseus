# routes/route_dispatch.py
"""Routing status endpoint — quota summary + available CLI backends.

GET /api/route/status — quota summary + available CLI backends

NOTE: POST /api/route used to live here but is now owned by
routes/orchestration_routes.py (traced dispatcher, in-band error contract,
never a 500). Do not re-add a POST handler here — Starlette matches routes
in registration order and a duplicate would silently shadow or be shadowed.
"""

import logging

from fastapi import APIRouter, Request, HTTPException

from src.auth_helpers import get_current_user

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def setup_route_dispatch() -> APIRouter:
    """Create and return the routing APIRouter."""
    router = APIRouter(prefix="/api/route", tags=["routing"])

    # Lazy-init a single TaskRouter instance on first request so we don't
    # import heavy modules at import-time (keeps test isolation easy).
    _router_instance = {}

    def _get_router():
        if "r" not in _router_instance:
            from core.router import TaskRouter
            _router_instance["r"] = TaskRouter()
        return _router_instance["r"]

    # -----------------------------------------------------------------
    # GET /api/route/status — quota + backend summary
    # -----------------------------------------------------------------

    @router.get("/status")
    async def route_status(request: Request):
        """Show current routing status: quota levels and available backends."""
        user = get_current_user(request)
        if not user:
            raise HTTPException(401, "Authentication required")

        task_router = _get_router()
        quota = task_router.get_quota_status()
        best_cli, best_provider = task_router.get_best_code_cli()

        # Build a clean provider summary
        providers_summary = {}
        for name, pdata in quota.get("providers", {}).items():
            providers_summary[name] = {
                "status": pdata.get("status", "unknown"),
            }
            if "weekly_pct_remaining" in pdata:
                providers_summary[name]["weekly_pct_remaining"] = pdata["weekly_pct_remaining"]
            if "quotas" in pdata and isinstance(pdata["quotas"], dict):
                providers_summary[name]["has_quota_data"] = True

        # List available CLI binaries
        import shutil
        cli_binaries = {}
        for binary_name in ("ca", "cb", "cp", "claude", "codex"):
            path = shutil.which(binary_name)
            cli_binaries[binary_name] = {
                "available": path is not None,
                "path": path,
            }

        return {
            "quota_timestamp": quota.get("timestamp", "unknown"),
            "providers": providers_summary,
            "best_code_cli": {
                "binary": best_cli,
                "provider": best_provider,
            },
            "cli_binaries": cli_binaries,
        }

    return router
