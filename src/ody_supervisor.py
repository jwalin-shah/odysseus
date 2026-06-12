"""Bounded, evidence-driven self-improvement supervisor for Odysseus."""

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

# --- Inline M3 client (avoids subprocess sandbox issues) ---
import ssl
import urllib.request

try:
    import certifi as _certifi
    _SSL_CTX = ssl.create_default_context(cafile=_certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()

_OPENCODE_JSON = os.path.expanduser("~/.config/opencode/opencode.json")
_M3_BASE_URL = "https://api.tokenrouter.com/v1"
_M3_DEFAULT_MODEL = "MiniMax-M3"


def _m3_api_key():
    key = os.environ.get("TOKENROUTER_API_KEY")
    if key:
        return key
    cfg = json.load(open(_OPENCODE_JSON))
    return cfg["provider"]["tokenrouter"]["options"]["apiKey"]


def _m3_complete(prompt, system=None, model=_M3_DEFAULT_MODEL, max_tokens=16384, timeout=600):
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    req = urllib.request.Request(
        f"{_M3_BASE_URL}/chat/completions",
        data=json.dumps({"model": model, "messages": messages,
                         "max_tokens": max_tokens}).encode(),
        headers={"Authorization": f"Bearer {_m3_api_key()}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as r:
        body = json.load(r)
    return body["choices"][0]["message"]["content"]


ROLE_ORDER = ("requirements", "test_author", "implementer", "red_team")
SECRET_KEYS = {
    "api_key", "apikey", "access_token", "refresh_token", "auth_token",
    "secret", "password", "authorization", "pioneer_api_key",
}


def mission_key(mission):
    scoped = {
        "mission": mission.get("mission", "").strip(),
        "repo": os.path.abspath(mission.get("repo") or os.getcwd()),
        "test": mission.get("test") or "pytest -q",
    }
    raw = json.dumps(scoped, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _json_answer(text):
    if not text or not text.strip():
        raise ValueError("empty M3 response")
    answer = text.split("</think>")[-1].strip()
    if not answer:
        raise ValueError("no content after think block")
    if answer.startswith("```"):
        parts = answer.split("```", 2)
        if len(parts) >= 2:
            answer = parts[1]
            if answer.startswith("json"):
                answer = answer[4:].lstrip()
    answer = answer.strip()
    if not answer:
        raise ValueError("empty JSON payload")
    return json.loads(answer)

def _safe(value):
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if key.lower() in SECRET_KEYS
                  else _safe(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


_VENV_BIN = Path(__file__).resolve().parent.parent / ".venv" / "bin"
_RUNNER_ENV = {**os.environ, "PATH": f"{_VENV_BIN}:{os.environ.get('PATH', '')}"}


def default_runner(role, payload):
    if role == "implementer":
        mission = payload["mission"]
        requirements = payload["requirements"]
        test_plan = payload["test_author"]
        feedback = payload.get("feedback", [])
        prompt = (
            f"{mission['mission']}\n\nREQUIREMENTS:\n{json.dumps(requirements)}\n"
            f"TEST AUTHOR CONTRACT:\n{json.dumps(test_plan)}\n"
            f"REVIEW FEEDBACK:\n{json.dumps(feedback)}\n"
            "Work test-first in the isolated worktree. Run the stated red test "
            "before implementation, then make it green."
        )
        test_cmd = test_plan.get("test_command") or mission.get("test") or "pytest -q"
        # Ensure pytest/python resolve from the project venv
        if test_cmd.startswith("pytest"):
            test_cmd = str(_VENV_BIN / "pytest") + test_cmd[6:]
        cmd = [
            str(_VENV_BIN / "python3"), str(Path(__file__).with_name("odysseus.py")), prompt,
            "--repo", mission.get("repo") or os.getcwd(),
            "--test", test_cmd,
            "--lane", "code", "--timeout", str(mission.get("timeout") or 900),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=_RUNNER_ENV)
        output = proc.stdout + proc.stderr
        return {
            "green": proc.returncode == 0 and "PASS" in output,
            "feedback": output[-2000:],
        }

    prompts = {
        "proposer": (
            "Act as the mission proposer. Return JSON with a missions array. "
            "Each mission must contain mission, test, priority, evidence, and "
            "allowed_files. Rank only novel, testable improvements."
        ),
        "requirements": (
            "Convert this candidate mission into one narrow, testable workpack. "
            "Return JSON with target FILE:FUNC, acceptance, allowed_files, "
            "test_command, and stop_condition."
        ),
        "test_author": (
            "Act as an independent test author. Return JSON with red=true, "
            "test_file, test_command, and test_content. The test must fail on "
            "the current behavior and prove the acceptance criteria."
        ),
        "red_team": (
            "Act as an adversarial reliability reviewer. Return JSON with "
            "verdict pass or revise and a findings array. Never certify in "
            "place of the test gate."
        ),
    }
    context = json.dumps(payload, sort_keys=True)
    prompt = f"{prompts[role]}\n\nINPUT:\n{context}"
    raw = _m3_complete(prompt)
    return _json_answer(raw)


class Supervisor:
    def __init__(self, state_dir, runner=None, max_attempts=3):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.queue_path = self.state_dir / "mission-queue.jsonl"
        self.ledger_path = self.state_dir / "supervisor-ledger.jsonl"
        self.receipts_path = self.state_dir / "role-receipts.jsonl"
        self.runner = runner or default_runner
        self.max_attempts = max_attempts

    def record(self, event):
        row = {"ts": time.time(), **event}
        with self.ledger_path.open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        return row

    def _rows(self, path):
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(errors="replace").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def _known_keys(self):
        keys = {row.get("mission_key") for row in self._rows(self.queue_path)}
        keys.update(
            row.get("mission_key") for row in self._rows(self.ledger_path)
            if row.get("event") in {"mission_completed", "mission_failed"}
        )
        return keys

    def call_role(self, role, payload, retries=2):
        safe_input = _safe(payload)
        started = time.time()
        output = None
        status = "unknown"
        try:
            last_exc = None
            for attempt in range(retries + 1):
                try:
                    output = self.runner(role, payload)
                    status = "ok"
                    return output
                except (TimeoutError, subprocess.TimeoutExpired) as exc:
                    last_exc = exc
                    if attempt >= retries:
                        raise
                    time.sleep(30)
                except (json.JSONDecodeError, ValueError) as exc:
                    last_exc = exc
                    if attempt >= retries:
                        raise
                    time.sleep(5)
                except Exception as exc:
                    last_exc = exc
                    if attempt >= retries:
                        raise
                    time.sleep(10)
            if last_exc:
                raise last_exc
        except Exception as exc:
            output = {"error": str(exc)}
            status = "error"
            raise
        finally:
            raw = json.dumps(safe_input, sort_keys=True, separators=(",", ":"))
            receipt = {
                "ts": started,
                "role": role,
                "status": status,
                "duration_s": round(time.time() - started, 3),
                "input_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                "input": safe_input,
                "output": _safe(output),
            }
            with self.receipts_path.open("a") as handle:
                handle.write(json.dumps(receipt, sort_keys=True) + "\n")

    def enqueue(self, mission):
        key = mission_key(mission)
        if key in self._known_keys():
            self.record({"event": "mission_duplicate", "mission_key": key})
            return False
        row = {"mission_key": key, **mission}
        with self.queue_path.open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
        self.record({"event": "mission_queued", "mission_key": key})
        return True

    def _pending(self):
        terminal = {
            row.get("mission_key") for row in self._rows(self.ledger_path)
            if row.get("event") in {"mission_completed", "mission_failed"}
        }
        return [row for row in self._rows(self.queue_path)
                if row.get("mission_key") not in terminal]

    def _run_mission(self, mission):
        key = mission["mission_key"]
        requirements = self.call_role("requirements", {"mission": mission})
        feedback = []
        for attempt in range(1, self.max_attempts + 1):
            test_plan = self.call_role("test_author", {
                "mission": mission,
                "requirements": requirements,
                "feedback": feedback,
                "attempt": attempt,
            })
            if not test_plan.get("red"):
                feedback.append("test author did not establish a red gate")
                self.record({"event": "attempt_failed", "mission_key": key,
                             "attempt": attempt, "reason": feedback[-1]})
                continue
            implementation = self.call_role("implementer", {
                "mission": mission,
                "requirements": requirements,
                "test_author": test_plan,
                "feedback": feedback,
                "attempt": attempt,
            })
            if not implementation.get("green"):
                feedback.append(implementation.get("feedback") or "green gate failed")
                self.record({"event": "attempt_failed", "mission_key": key,
                             "attempt": attempt, "reason": feedback[-1]})
                continue
            review = self.call_role("red_team", {
                "mission": mission,
                "requirements": requirements,
                "test_author": test_plan,
                "implementation": implementation,
                "feedback": feedback,
                "attempt": attempt,
            })
            if review.get("verdict") == "pass":
                self.record({"event": "mission_completed", "mission_key": key,
                             "attempt": attempt, "result": implementation})
                return True
            feedback.extend(review.get("findings") or ["review requested revision"])
            self.record({"event": "attempt_failed", "mission_key": key,
                         "attempt": attempt, "reason": feedback[-1]})
        self.record({"event": "mission_failed", "mission_key": key,
                     "reason": feedback[-1] if feedback else "retry limit"})
        return False

    def run(self, max_missions=5):
        completed = failed = 0
        for mission in self._pending()[:max_missions]:
            try:
                ok = self._run_mission(mission)
            except Exception as exc:
                self.record({"event": "mission_failed",
                             "mission_key": mission.get("mission_key"),
                             "reason": f"{type(exc).__name__}: {exc}"})
                ok = False
            if ok:
                completed += 1
            else:
                failed += 1
        return {"completed": completed, "failed": failed,
                "remaining": len(self._pending())}


def propose_from_evidence(state_dir, repo, evidence_paths, limit=5, runner=None):
    runner = runner or default_runner
    evidence = []
    for path in evidence_paths:
        candidate = Path(path)
        if candidate.exists():
            evidence.append(f"--- {candidate.name} ---\n"
                            f"{candidate.read_text(errors='replace')[-12000:]}")
    supervisor = Supervisor(state_dir, runner=runner)
    result = supervisor.call_role("proposer", {
        "mode": "propose",
        "repo": str(repo),
        "limit": limit,
        "evidence": "\n\n".join(evidence),
        "instruction": (
            "Return a JSON object with a missions array. Rank novel, testable "
            "improvements by impact, evidence strength, and implementation cost."
        ),
    })
    missions = result.get("missions", []) if isinstance(result, dict) else []
    return sum(supervisor.enqueue({**mission, "repo": str(repo)})
               for mission in missions[:limit])


def supervise_main(argv=None, supervisor_cls=Supervisor):
    parser = argparse.ArgumentParser(prog="ody supervise")
    parser.add_argument("action", choices=["enqueue", "propose", "run", "status"])
    parser.add_argument("--state-dir", default=".credit-lab/supervisor")
    parser.add_argument("--repo", default=os.getcwd())
    parser.add_argument("--mission")
    parser.add_argument("--test", default="pytest -q")
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--max-missions", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval", type=int, default=300)
    args = parser.parse_args(argv)
    supervisor = supervisor_cls(args.state_dir, max_attempts=args.max_attempts)

    if args.action == "enqueue":
        if not args.mission:
            parser.error("--mission is required for enqueue")
        added = supervisor.enqueue({
            "mission": args.mission,
            "repo": args.repo,
            "test": args.test,
        })
        print(json.dumps({"queued": added}))
        return 0
    if args.action == "propose":
        evidence = args.evidence or [
            Path(args.repo) / ".credit-lab" / "mining" / "GRADES.md",
            Path(args.repo) / ".credit-lab" / "mining" / "FINDINGS.md",
            Path(args.repo) / "FABLE_BLUEPRINT.md",
            Path(args.repo) / "V2_MASTERPLAN.md",
        ]
        added = propose_from_evidence(
            args.state_dir, args.repo, evidence, args.max_missions,
        )
        print(json.dumps({"queued": added}))
        return 0
    if args.action == "status":
        result = {
            "pending": len(supervisor._pending()),
            "ledger": str(supervisor.ledger_path),
            "queue": str(supervisor.queue_path),
        }
        print(json.dumps(result, sort_keys=True))
        return 0

    totals = {"completed": 0, "failed": 0, "remaining": 0}
    for cycle in range(max(1, args.cycles)):
        result = supervisor.run(max_missions=max(1, args.max_missions))
        totals["completed"] += result["completed"]
        totals["failed"] += result["failed"]
        totals["remaining"] = result["remaining"]
        if not result["remaining"] or cycle + 1 >= args.cycles:
            break
        time.sleep(max(1, args.interval))
    print(json.dumps(totals, sort_keys=True))
    return 1 if totals["failed"] else 0
