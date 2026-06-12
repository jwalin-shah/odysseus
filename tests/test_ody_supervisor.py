import json

from src.ody_supervisor import Supervisor, mission_key, supervise_main


def test_mission_key_is_stable_and_scope_sensitive():
    base = {"mission": "fix quota reset", "repo": "/repo", "test": "pytest -q"}
    assert mission_key(base) == mission_key(dict(base))
    assert mission_key(base) != mission_key({**base, "mission": "fix router"})


def test_supervisor_deduplicates_completed_and_queued_missions(tmp_path):
    supervisor = Supervisor(tmp_path)
    mission = {"mission": "fix quota reset", "repo": "/repo", "test": "pytest -q"}

    assert supervisor.enqueue(mission) is True
    assert supervisor.enqueue(mission) is False
    supervisor.record({"event": "mission_completed", "mission_key": mission_key(mission)})
    assert supervisor.enqueue(mission) is False


def test_supervisor_runs_separated_roles_and_retries_review_findings(tmp_path):
    calls = []

    def runner(role, payload):
        calls.append(role)
        if role == "requirements":
            return {"target": "src/example.py:solve", "acceptance": "returns 2"}
        if role == "test_author":
            return {"red": True, "test_command": "pytest -q tests/test_example.py"}
        if role == "implementer":
            return {"green": True, "branch": "ody-m3-1"}
        if role == "red_team" and calls.count("red_team") == 1:
            return {"verdict": "revise", "findings": ["test empty input"]}
        return {"verdict": "pass"}

    supervisor = Supervisor(tmp_path, runner=runner, max_attempts=3)
    supervisor.enqueue({"mission": "fix solver", "repo": "/repo", "test": "pytest -q"})

    result = supervisor.run(max_missions=1)

    assert result["completed"] == 1
    assert calls == [
        "requirements", "test_author", "implementer", "red_team",
        "test_author", "implementer", "red_team",
    ]


def test_supervisor_stops_after_retry_limit(tmp_path):
    def runner(role, payload):
        if role == "requirements":
            return {"target": "src/example.py:solve", "acceptance": "works"}
        if role == "test_author":
            return {"red": True, "test_command": "pytest -q"}
        if role == "implementer":
            return {"green": False, "feedback": "still red"}
        raise AssertionError(role)

    supervisor = Supervisor(tmp_path, runner=runner, max_attempts=2)
    supervisor.enqueue({"mission": "fix solver", "repo": "/repo", "test": "pytest -q"})

    result = supervisor.run(max_missions=1)

    assert result == {"completed": 0, "failed": 1, "remaining": 0}
    events = [json.loads(line)["event"] for line in supervisor.ledger_path.read_text().splitlines()]
    assert events.count("attempt_failed") == 2
    assert events[-1] == "mission_failed"


def test_supervise_cli_runs_bounded_queue(tmp_path):
    class FakeSupervisor:
        def __init__(self, state_dir, max_attempts=3):
            assert str(state_dir) == str(tmp_path)
            assert max_attempts == 2

        def run(self, max_missions):
            assert max_missions == 4
            return {"completed": 2, "failed": 1, "remaining": 3}

    rc = supervise_main([
        "run", "--state-dir", str(tmp_path), "--max-missions", "4",
        "--max-attempts", "2",
    ], supervisor_cls=FakeSupervisor)

    assert rc == 1


def test_supervisor_records_role_inputs_outputs_and_timing(tmp_path):
    def runner(role, payload):
        if role == "requirements":
            return {"target": "src/example.py:solve", "acceptance": "works"}
        if role == "test_author":
            return {"red": True, "test_command": "pytest -q"}
        if role == "implementer":
            return {"green": True, "branch": "ody-m3-1", "usage": {"total_tokens": 42}}
        return {"verdict": "pass"}

    supervisor = Supervisor(tmp_path, runner=runner)
    supervisor.enqueue({"mission": "fix solver", "repo": "/repo", "test": "pytest -q"})
    supervisor.run(max_missions=1)

    receipts = [
        json.loads(line) for line in supervisor.receipts_path.read_text().splitlines()
    ]
    assert [row["role"] for row in receipts] == [
        "requirements", "test_author", "implementer", "red_team",
    ]
    assert receipts[0]["input"]["mission"]["mission"] == "fix solver"
    assert receipts[2]["output"]["usage"]["total_tokens"] == 42
    assert all(row["duration_s"] >= 0 for row in receipts)
    assert all(len(row["input_sha256"]) == 64 for row in receipts)
