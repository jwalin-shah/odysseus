# tests/test_orchestration_trace.py
"""Orchestration observability layer tests.

Covers the failure modes called out in platform/ORCHESTRATION.md:
* trace appends are intact under concurrent writers (no interleaved lines)
* stats cardinality is bounded by (classification, model) — never task_hash
* health probes detect a stale quota file (mtime/inner timestamp, not existence)
* failure streak counts consecutive failures, not last-N totals
* /api/route returns errors in-band (never a 500) and always records a trace
"""

import json
import os
import threading
import time

import pytest

from core import orchestration_trace as otrace


@pytest.fixture
def trace_file(tmp_path, monkeypatch):
    path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(otrace, "TRACE_DIR", str(tmp_path))
    monkeypatch.setattr(otrace, "TRACE_FILE", str(path))
    return path


class TestRecordTrace:
    def test_writes_one_valid_json_line(self, trace_file):
        receipt = otrace.record_trace(
            task="fix the bug in foo.py",
            classification="code",
            model_used="ca",
            tokens=120,
            latency_ms=1234.5,
            success=True,
        )
        lines = trace_file.read_text().splitlines()
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["classification"] == "code"
        assert row["task_hash"] == receipt["task_hash"]
        assert len(row["task_hash"]) == 16
        assert "fix the bug" not in lines[0]  # raw task text never persisted

    def test_concurrent_writers_produce_intact_lines(self, trace_file):
        n_threads, per_thread = 8, 50

        def writer(i):
            for j in range(per_thread):
                otrace.record_trace(
                    task=f"t{i}-{j}", classification="chat",
                    model_used="minimax-m3", latency_ms=1,
                )

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        lines = trace_file.read_text().splitlines()
        assert len(lines) == n_threads * per_thread
        for line in lines:
            json.loads(line)  # every line parses — no torn writes

    def test_never_raises_on_unwritable_dir(self, monkeypatch):
        monkeypatch.setattr(otrace, "TRACE_DIR", "/dev/null/nope")
        monkeypatch.setattr(otrace, "TRACE_FILE", "/dev/null/nope/t.jsonl")
        receipt = otrace.record_trace(task="x", classification="chat")
        assert "_write_error" in receipt


class TestStats:
    def test_cardinality_bounded_by_classification_model(self, trace_file):
        # 200 distinct tasks but only 2 (classification, model) pairs
        for i in range(200):
            otrace.record_trace(
                task=f"unique task {i}",
                classification="code" if i % 2 else "chat",
                model_used="ca" if i % 2 else "minimax-m3",
                latency_ms=10 * i,
                success=True,
            )
        stats = otrace.compute_stats()
        buckets = stats["last_24h"]["by_classification_model"]
        assert len(buckets) == 2  # not 200
        assert stats["last_24h"]["count"] == 200

    def test_percentiles_include_failures_and_success_rate_separate(self, trace_file):
        for _ in range(98):
            otrace.record_trace(task="ok", classification="chat",
                                model_used="m", latency_ms=100, success=True)
        for _ in range(2):
            otrace.record_trace(task="timeout", classification="code",
                                model_used="ca", latency_ms=300_000, success=False,
                                error="timeout")
        day = otrace.compute_stats()["last_24h"]
        assert day["success_rate"] == 0.98
        assert day["latency_ms_p95"] == 100  # p95 of 100 calls is still 100ms
        # but the failures ARE in the distribution: max bucket exists
        assert day["count"] == 100

    def test_old_rows_fall_out_of_windows(self, trace_file):
        old = {"ts": "x", "unix": time.time() - 8 * 86400, "classification": "chat",
               "model_used": "m", "tokens": 1, "latency_ms": 5, "success": True,
               "error": None, "task_hash": None, "source": "router"}
        trace_file.write_text(json.dumps(old) + "\n")
        otrace.record_trace(task="now", classification="chat", model_used="m")
        stats = otrace.compute_stats()
        assert stats["last_7d"]["count"] == 1
        assert stats["last_24h"]["count"] == 1


class TestHealth:
    def test_stale_quota_file_detected_by_age_not_existence(self, tmp_path, monkeypatch):
        quota = tmp_path / "quota-live.json"
        quota.write_text(json.dumps({"unix": time.time() - 7200, "providers": {}}))
        old = time.time() - 7200
        os.utime(quota, (old, old))
        monkeypatch.setattr(otrace, "QUOTA_LIVE_PATH", str(quota))
        probe = otrace._probe_quota_freshness()
        assert probe["ok"] is False  # file exists but is stale
        assert probe["file_age_s"] > otrace.QUOTA_STALE_SECONDS

    def test_fresh_quota_file_passes(self, tmp_path, monkeypatch):
        quota = tmp_path / "quota-live.json"
        quota.write_text(json.dumps({"unix": time.time(), "providers": {}}))
        monkeypatch.setattr(otrace, "QUOTA_LIVE_PATH", str(quota))
        assert otrace._probe_quota_freshness()["ok"] is True

    def test_missing_quota_file_fails(self, monkeypatch):
        monkeypatch.setattr(otrace, "QUOTA_LIVE_PATH", "/nonexistent/q.json")
        assert otrace._probe_quota_freshness()["ok"] is False

    def test_failure_streak_is_consecutive_not_total(self, trace_file):
        otrace.record_trace(task="a", success=False, error="x")
        otrace.record_trace(task="b", success=True)
        otrace.record_trace(task="c", success=False, error="x")
        otrace.record_trace(task="d", success=False, error="x")
        # newest-first: fail, fail, ok, fail → streak 2 (not 3 failures total)
        assert otrace._failure_streak(otrace.read_traces(limit=50)) == 2

    def test_cli_probe_fails_without_claude_binary(self, monkeypatch):
        monkeypatch.setattr(otrace, "_cli_probe_cache", {"ts": 0.0, "result": None})
        monkeypatch.setattr(otrace.shutil, "which", lambda _: None)
        probe = otrace._probe_cli_liveness()
        assert probe["ok"] is False
        assert "not on PATH" in probe["claude_binary"]["detail"]

    def test_cli_probe_fails_on_missing_config_dir(self, monkeypatch, tmp_path):
        monkeypatch.setattr(otrace, "_cli_probe_cache", {"ts": 0.0, "result": None})
        monkeypatch.setattr(
            otrace, "CLI_PROBE_ACCOUNTS", (("ca", str(tmp_path / "nope")),)
        )
        probe = otrace._probe_cli_liveness()
        assert probe["accounts"]["ca"]["ok"] is False
        assert "config dir missing" in probe["accounts"]["ca"]["detail"]

    def test_process_pressure_probe(self, monkeypatch):
        probe = otrace._probe_process_pressure()
        assert "ratio" in probe  # runs for real on this machine
        assert probe["ok"] is (probe["ratio"] < otrace.PROC_PRESSURE_THRESHOLD)
        monkeypatch.setattr(otrace, "PROC_PRESSURE_THRESHOLD", 0.0)
        hot = otrace._probe_process_pressure()
        assert hot["ok"] is False
        assert hot["top_commands"]  # culprits named when unhealthy


class TestRouteEndpoint:
    @pytest.fixture
    def client(self, trace_file):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routes.orchestration_routes import setup_orchestration_routes

        class FakeRouter:
            async def route(self, task, task_type="auto"):
                if task == "boom":
                    raise RuntimeError("dispatch exploded")
                if task == "fail":
                    return {"response": "Error (1): quota exhausted",
                            "model_used": "ca", "tokens": 0,
                            "classification": "code", "error": True}
                return {"response": "ok", "model_used": "minimax-m3",
                        "tokens": 5, "classification": "chat"}

        app = FastAPI()
        app.include_router(setup_orchestration_routes(task_router=FakeRouter()))
        return TestClient(app)

    def test_success_traced(self, client, trace_file):
        r = client.post("/api/route", json={"task": "hello", "type": "auto"})
        assert r.status_code == 200
        assert r.json()["model_used"] == "minimax-m3"
        row = json.loads(trace_file.read_text().splitlines()[-1])
        assert row["success"] is True and row["classification"] == "chat"

    def test_exception_returns_in_band_error_not_500(self, client, trace_file):
        r = client.post("/api/route", json={"task": "boom"})
        assert r.status_code == 200
        body = r.json()
        assert body["error"] is True
        assert "dispatch exploded" in body["error_detail"]
        row = json.loads(trace_file.read_text().splitlines()[-1])
        assert row["success"] is False

    def test_router_error_result_traced_as_failure(self, client, trace_file):
        r = client.post("/api/route", json={"task": "fail"})
        assert r.status_code == 200
        row = json.loads(trace_file.read_text().splitlines()[-1])
        assert row["success"] is False
        assert "quota exhausted" in row["error"]

    def test_observability_endpoints(self, client):
        client.post("/api/route", json={"task": "hello"})
        traces = client.get("/api/orchestration/traces?limit=10").json()
        assert traces["count"] >= 1
        stats = client.get("/api/orchestration/stats").json()
        assert "last_24h" in stats and "latency_definition" in stats
        health = client.get("/api/orchestration/health").json()
        assert "quota_core" in health and "consecutive_failures" in health
