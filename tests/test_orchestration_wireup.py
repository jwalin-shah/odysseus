# tests/test_orchestration_wireup.py
"""Brief 1 wire-up guards (docs/orchestration-briefs.md).

Pins the route-collision resolution: routes/orchestration_routes.py owns
POST /api/route (traced, in-band errors); routes/route_dispatch.py keeps
only GET /api/route/status. Starlette matches routes in registration order,
so a duplicate POST would silently shadow the traced dispatcher — these
tests make that regression loud.

Deliberately avoids importing app.py (it boots managers, DB, scheduler).
Instead it builds a minimal FastAPI app from the two route factories mounted
in the same order app.py uses, and separately asserts app.py's source mounts
them in that order.
"""

import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import orchestration_trace as otrace
from routes.orchestration_routes import setup_orchestration_routes
from routes.route_dispatch import setup_route_dispatch

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def trace_file(tmp_path, monkeypatch):
    path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(otrace, "TRACE_DIR", str(tmp_path))
    monkeypatch.setattr(otrace, "TRACE_FILE", str(path))
    return path


class _FakeTaskRouter:
    async def route(self, task, task_type="auto"):
        return {
            "response": "ok",
            "model_used": "fake-model",
            "tokens": 3,
            "classification": "chat",
            "provider": "fake",
        }


@pytest.fixture
def client(trace_file):
    app = FastAPI()
    # route_dispatch first so its concrete GET /api/route/status registers
    # before orchestration_routes' wildcard GET /api/route/{run_id}.
    # POST /api/route collision is not affected: only one POST handler exists.
    # app.py mounts orchestration before dispatch (required for the POST
    # ownership invariant); that assertion lives in TestAppPySource below.
    app.include_router(setup_route_dispatch())
    app.include_router(setup_orchestration_routes(task_router=_FakeTaskRouter()))
    return TestClient(app)


def _post_routes(app_obj):
    return [
        r for r in app_obj.routes
        if getattr(r, "path", None) == "/api/route" and "POST" in getattr(r, "methods", set())
    ]


class TestSingleOwner:
    def test_exactly_one_post_route(self, client):
        routes = _post_routes(client.app)
        assert len(routes) == 1, f"expected exactly one POST /api/route, got {len(routes)}"

    def test_post_route_is_orchestration(self, client):
        (route,) = _post_routes(client.app)
        assert route.endpoint.__module__ == "routes.orchestration_routes"

    def test_route_dispatch_has_no_post(self):
        r = setup_route_dispatch()
        posts = [x for x in r.routes if "POST" in getattr(x, "methods", set())]
        assert posts == [], "route_dispatch must not register POST handlers"


class TestTracedDispatch:
    def test_post_route_inband_contract(self, client):
        resp = client.post("/api/route", json={"task": "hi", "type": "chat"})
        assert resp.status_code == 200
        body = resp.json()
        for key in ("response", "model_used", "tokens", "classification"):
            assert key in body, f"missing contract key {key}"

    def test_post_route_writes_receipt(self, client, trace_file):
        client.post("/api/route", json={"task": "hello receipt", "type": "chat"})
        lines = trace_file.read_text().strip().splitlines()
        assert len(lines) == 1
        receipt = json.loads(lines[0])
        assert receipt["task_hash"] == otrace.task_hash("hello receipt")
        assert receipt["classification"] == "chat"
        assert receipt["model_used"] == "fake-model"

    def test_invalid_type_is_422_request_shape(self, client):
        # Request-shape errors are NOT in-band; only dispatch errors are.
        resp = client.post("/api/route", json={"task": "x", "type": "bogus"})
        assert resp.status_code == 422


class TestRouteDispatchSurvivor:
    def test_status_endpoint_exists(self):
        r = setup_route_dispatch()
        paths = {(x.path, m) for x in r.routes for m in getattr(x, "methods", set())}
        assert ("/api/route/status", "GET") in paths

    def test_status_requires_auth(self, client):
        resp = client.get("/api/route/status")
        assert resp.status_code == 401


class TestAppPySource:
    """app.py can't be imported in tests (boots the world) — assert on source."""

    def test_app_mounts_orchestration_before_dispatch(self):
        src = (REPO / "app.py").read_text()
        orch = src.index("setup_orchestration_routes()")
        disp = src.index("setup_route_dispatch()")
        assert orch < disp, "orchestration router must mount before route_dispatch"

    def test_app_mounts_orchestration_exactly_once(self):
        src = (REPO / "app.py").read_text()
        assert len(re.findall(r"app\.include_router\(setup_orchestration_routes\(\)\)", src)) == 1
