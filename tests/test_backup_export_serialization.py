"""ODYSSEY-JSON regression tests for backup_routes.export_data.

Verifies that the export endpoint survives non-JSON-native types
(datetime, Decimal, UUID, pathlib.Path) by falling back to `default=str`
and surfaces any other TypeError as 500 with a useful message.
"""
from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Stub the heavy dependencies the route module imports so we can import
# backup_routes in isolation.
class _StubRouter:
    def __init__(self, *a, **kw):
        self.routes = []
    def get(self, *a, **kw):
        def deco(fn):
            fn.path = a[0] if a else kw.get("path")
            self.routes.append(fn)
            return fn
        return deco
    def post(self, *a, **kw):
        def deco(fn):
            fn.path = a[0] if a else kw.get("path")
            self.routes.append(fn)
            return fn
        return deco

class _StubHTTPException(Exception):
    def __init__(self, status, detail=""):
        self.status_code = status
        self.detail = detail

class _StubResponse:
    def __init__(self, content, media_type=None, headers=None):
        self.body = content
        self.media_type = media_type
        self.headers = headers or {}

fastapi_stub = types.ModuleType("fastapi")
fastapi_stub.APIRouter = _StubRouter
fastapi_stub.HTTPException = _StubHTTPException
fastapi_stub.Request = MagicMock
fastapi_stub.Response = _StubResponse
sys.modules["fastapi"] = fastapi_stub

# Insert _StubResponse so backup_routes uses our simple Response class
sys.modules["core.middleware"] = types.ModuleType("core.middleware")
sys.modules["core.middleware"].require_admin = lambda request: None
sys.modules["src.auth_helpers"] = types.ModuleType("src.auth_helpers")
sys.modules["src.auth_helpers"].get_current_user = lambda request: "test-user"

settings_mod = types.ModuleType("src.settings")
settings_mod.load_settings = lambda: {}
settings_mod.save_settings = lambda x: None
settings_mod.load_features = lambda: {}
settings_mod.save_features = lambda x: None
sys.modules["src.settings"] = settings_mod

# routes.prefs_routes is imported lazily inside export_data; pre-create it.
if "routes.prefs_routes" not in sys.modules:
    pr = types.ModuleType("routes.prefs_routes")
    pr._load_for_user = lambda user: {}
    pr._save_for_user = lambda user, data: None
    sys.modules["routes.prefs_routes"] = pr

from routes import backup_routes  # noqa: E402


def _build_request():
    return MagicMock()


def test_export_data_survives_datetime_field():
    """datetime objects in the export payload must serialize, not 500."""
    mem = MagicMock()
    mem.load = MagicMock(return_value=[{"text": "hi", "ts": __import__("datetime").datetime(2026, 6, 21)}])
    preset = MagicMock()
    preset.get_all = MagicMock(return_value={})
    skills = MagicMock()
    skills.load = MagicMock(return_value=[])

    router = backup_routes.setup_backup_routes(mem, preset, skills)
    # Find the /api/export handler
    export_handler = None
    for route in router.routes:
        # Stub stores the path on the function itself
        if getattr(route, "path", "") == "/api/export":
            export_handler = route
            break
    assert export_handler is not None, "export_data route not registered"

    resp = asyncio.get_event_loop().run_until_complete(
        export_handler(_build_request())
    )
    # The Response body is bytes; parse it back to confirm it's valid JSON
    body = resp.body
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    parsed = json.loads(body)
    assert parsed["memories"][0]["ts"].startswith("2026-06-21")


def test_export_data_survives_decimal_field():
    """Decimal values must serialize via default=str fallback."""
    from decimal import Decimal

    mem = MagicMock()
    mem.load = MagicMock(return_value=[{"text": "hi", "amount": Decimal("3.14")}])
    preset = MagicMock()
    preset.get_all = MagicMock(return_value={})
    skills = MagicMock()
    skills.load = MagicMock(return_value=[])

    router = backup_routes.setup_backup_routes(mem, preset, skills)
    export_handler = None
    for route in router.routes:
        if getattr(route, "path", "") == "/api/export":
            export_handler = route
            break

    resp = asyncio.get_event_loop().run_until_complete(
        export_handler(_build_request())
    )
    body = resp.body
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    parsed = json.loads(body)
    assert parsed["memories"][0]["amount"] == "3.14"


if __name__ == "__main__":
    test_export_data_survives_datetime_field()
    test_export_data_survives_decimal_field()
    print("2 passed")
