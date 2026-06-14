import asyncio
import json

from scripts import m3_run_mission_queue as runner


def _brief(**overrides):
    brief = {
        "affected_files": ["src/example.py"],
        "proposed_fix": "Fix the example implementation.",
        "proposed_test": "pytest -q tests/test_example.py",
        "mission_prompt": "Fix the example implementation.",
        "confidence": 0.8,
    }
    brief.update(overrides)
    return brief


def test_dry_run_validates_without_dispatching(tmp_path):
    queue = tmp_path / "queue.jsonl"
    results = tmp_path / "results.jsonl"
    queue.write_text(json.dumps(_brief()) + "\n")
    calls = []

    summary = asyncio.run(runner.run_queue(
        queue, results, execute=False,
        dispatcher=lambda payload: calls.append(payload),
    ))

    assert summary == {"ready": 1, "invalid": 0, "dispatched": 0, "failed": 0}
    assert calls == []
    assert json.loads(results.read_text())["status"] == "ready"


def test_invalid_brief_is_recorded_and_not_dispatched(tmp_path):
    queue = tmp_path / "queue.jsonl"
    results = tmp_path / "results.jsonl"
    queue.write_text(json.dumps(_brief(affected_files=["<placeholder>"])) + "\n")
    calls = []

    summary = asyncio.run(runner.run_queue(
        queue, results, execute=True,
        dispatcher=lambda payload: calls.append(payload),
    ))

    assert summary["invalid"] == 1
    assert calls == []
    record = json.loads(results.read_text())
    assert record["status"] == "invalid"
    assert record["field"] == "affected_files"


def test_execute_preserves_full_brief_for_dispatch(tmp_path):
    queue = tmp_path / "queue.jsonl"
    results = tmp_path / "results.jsonl"
    brief = _brief()
    queue.write_text(json.dumps(brief) + "\n")
    calls = []

    async def dispatch(payload):
        calls.append(json.loads(payload))
        return {"exit_code": 0, "dispatch_id": "d_test"}

    summary = asyncio.run(runner.run_queue(
        queue, results, execute=True, dispatcher=dispatch,
    ))

    assert summary["dispatched"] == 1
    assert calls[0]["brief"] == brief
    assert calls[0]["mission"] == brief["mission_prompt"]
    assert calls[0]["test"] == brief["proposed_test"]
    record = json.loads(results.read_text())
    assert record["dispatch_id"] == "d_test"


def test_missing_affected_file_is_invalid(tmp_path):
    queue = tmp_path / "queue.jsonl"
    results = tmp_path / "results.jsonl"
    queue.write_text(json.dumps(_brief()) + "\n")

    summary = asyncio.run(runner.run_queue(
        queue, results, execute=False, repo=tmp_path,
    ))

    assert summary["invalid"] == 1
    assert "does not exist" in json.loads(results.read_text())["error"]


def test_nested_missing_test_target_is_invalid(tmp_path):
    queue = tmp_path / "queue.jsonl"
    results = tmp_path / "results.jsonl"
    source = tmp_path / "src"
    source.mkdir()
    (source / "example.py").write_text("")
    queue.write_text(json.dumps(_brief(
        proposed_test="pytest -q v2/tests/agents/test_missing.py",
    )) + "\n")

    summary = asyncio.run(runner.run_queue(
        queue, results, execute=False, repo=tmp_path,
    ))

    assert summary["invalid"] == 1
    assert "v2/tests/agents/test_missing.py" in results.read_text()


def test_limit_summary_counts_only_selected_records(tmp_path):
    queue = tmp_path / "queue.jsonl"
    results = tmp_path / "results.jsonl"
    queue.write_text(
        json.dumps(_brief(affected_files=["<bad-one>"])) + "\n"
        + json.dumps(_brief(affected_files=["<bad-two>"])) + "\n"
    )

    summary = asyncio.run(runner.run_queue(
        queue, results, execute=False, limit=1,
    ))

    assert summary == {"ready": 0, "invalid": 1, "dispatched": 0, "failed": 0}
    assert len(results.read_text().splitlines()) == 1


def test_ready_briefs_are_ranked_by_confidence_and_cluster_size(tmp_path):
    queue = tmp_path / "queue.jsonl"
    results = tmp_path / "results.jsonl"
    source = tmp_path / "src"
    tests = tmp_path / "tests"
    source.mkdir()
    tests.mkdir()
    (source / "example.py").write_text("")
    (tests / "test_example.py").write_text("")
    low = _brief(confidence=0.5, cluster_size=100, failure_mode="low")
    high = _brief(confidence=0.9, cluster_size=20, failure_mode="high")
    queue.write_text(json.dumps(low) + "\n" + json.dumps(high) + "\n")

    summary = asyncio.run(runner.run_queue(
        queue, results, execute=False, repo=tmp_path,
    ))

    records = [json.loads(line) for line in results.read_text().splitlines()]
    assert summary["ready"] == 2
    assert records[0]["failure_mode"] == "high"
    assert records[0]["priority"] > records[1]["priority"]
