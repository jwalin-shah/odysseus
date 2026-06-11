# tests/test_route_api.py
"""Integration tests for POST /api/route and GET /api/route/status.

Uses FastAPI TestClient with stubbed auth (mimicking the pattern used in
other odysseus tests: patch src.auth_helpers.get_current_user to return a
fixed user string) and a patched subprocess.run to avoid real CLI calls.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.route_dispatch import setup_route_dispatch
import src.auth_helpers as auth_helpers


# ---------------------------------------------------------------------------
# App factory — minimal FastAPI app with the route_dispatch router
# ---------------------------------------------------------------------------


def _build_app(auth_user: str = "test-user"):
    """Build a minimal FastAPI app with route_dispatch and stubbed auth."""
    app = FastAPI()
    router = setup_route_dispatch()
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    """TestClient with auth stubbed to always return 'test-user'."""
    monkeypatch.setattr(auth_helpers, "get_current_user", lambda req: "test-user")
    app = _build_app()
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRouteEndpoint:
    """Integration tests for POST /api/route."""

    def test_code_task_returns_correct_fields(self, client, monkeypatch):
        """POST /api/route with type=code and a stubbed subprocess returns
        the expected JSON shape with response/model_used/tokens/classification."""
        canned_stdout = "def hello():\n    print('hello world')"
        mock_result = subprocess.CompletedProcess(
            args=["ca", "--print", "-p", "write hello world"],
            returncode=0,
            stdout=canned_stdout,
            stderr="",
        )
        # Patch at the module level used by route_code
        with patch("subprocess.run", return_value=mock_result):
            # Also patch quota + shutil.which so CLI selection is deterministic
            with patch("shutil.which", return_value="/usr/bin/ca"):
                from pathlib import Path
                import json, time
                quota = {
                    "timestamp": "2026-06-10",
                    "unix": time.time(),
                    "providers": {
                        "ca": {"status": "success"},
                    },
                }
                with patch.object(Path, "read_text", return_value=json.dumps(quota)):
                    resp = client.post(
                        "/api/route",
                        json={"task": "write a hello world function", "type": "code"},
                    )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "response" in data
        assert "model_used" in data
        assert "tokens" in data
        assert "classification" in data
        assert data["classification"] == "code"
        assert canned_stdout in data["response"]

    def test_invalid_type_returns_422(self, client):
        """POST /api/route with an unrecognized type should return 422."""
        resp = client.post(
            "/api/route",
            json={"task": "do something", "type": "invalid_type"},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    def test_subprocess_file_not_found_returns_200_with_error(self, client, monkeypatch):
        """FileNotFoundError from subprocess should yield 200 with error:True, not a 500."""
        with patch("subprocess.run", side_effect=FileNotFoundError("ca not found")):
            with patch("shutil.which", return_value="/usr/bin/ca"):
                from pathlib import Path
                import json, time
                quota = {
                    "timestamp": "2026-06-10",
                    "unix": time.time(),
                    "providers": {
                        "ca": {"status": "success"},
                    },
                }
                with patch.object(Path, "read_text", return_value=json.dumps(quota)):
                    resp = client.post(
                        "/api/route",
                        json={"task": "write some code", "type": "code"},
                    )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("error") is True
        assert "not found" in data["response"].lower()
