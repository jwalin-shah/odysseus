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


def _m3_complete(prompt, system=None, model=_M3_DEFAULT_MODEL, max_tokens=None,
                 timeout=600, json_mode=True):
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    # TODO: revisit if we ever move off free tier — for now let M3 burn
    body = {"model": model, "messages": messages}
    # Greedy decoding: for structured-extraction roles we want the most-likely
    # output, not creative sampling. Same input → same output, so failures are
    # reproducible and the stochastic core behaves deterministically per call.
    body["temperature"] = 0
    # Soft constrained decoding — TokenRouter honors json_object (think block still
    # leaks, which _json_answer strips). Cuts the prose-instead-of-JSON failure mode.
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    req = urllib.request.Request(
        f"{_M3_BASE_URL}/chat/completions",
        data=json.dumps(body).encode(),
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
    # Strip markdown fences
    if answer.startswith("```"):
        parts = answer.split("```", 2)
        if len(parts) >= 2:
            answer = parts[1]
            if answer.startswith("json"):
                answer = answer[4:].lstrip()
    answer = answer.strip()
    if not answer:
        raise ValueError("empty JSON payload")
    # If M3 wrapped the JSON in prose, scan for the first object/array and
    # raw_decode from there (raw_decode only works from the exact start).
    try:
        return json.loads(answer)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for i, ch in enumerate(answer):
            if ch in "{[":
                try:
                    obj, _ = decoder.raw_decode(answer[i:])
                    return obj
                except json.JSONDecodeError:
                    continue
        sample = answer[:300].replace("\n", " ")
        raise ValueError(f"no valid JSON in response (len={len(answer)}) sample={sample!r}")

def _failure_summary(output, max_lines=8):
    """Pull the salient pytest/python failure lines out of noisy output.

    Warnings (DeprecationWarning, etc.) are skipped so they don't mask the real
    cause; we keep assertion/error/traceback lines and the pytest short summary.
    """
    salient = []
    for line in output.splitlines():
        s = line.strip()
        if not s or "Warning" in s or s.startswith("--"):
            continue
        if any(tok in s for tok in ("FAILED", "ERROR", "Error:", "assert", "Exception",
                                    "Traceback", "!=", "E   ", "short test summary")):
            salient.append(s[:200])
    return "\n".join(salient[-max_lines:])


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

_ODY_HOME = Path(__file__).resolve().parent.parent

def _repo_filelist(repo=None):
    """Return newline-separated list of real src/v2 Python files for M3 context."""
    root = Path(repo) if repo else _ODY_HOME
    files = []
    for pattern in ("src/*.py", "v2/src/*.py"):
        files.extend(sorted(p.relative_to(root) for p in root.glob(pattern)
                            if not p.name.startswith("__")))
    return "\n".join(str(f) for f in files)


def _extract_import_target(test_content):
    """Return the first repo-relative .py path that test_content imports from.

    Parses 'from src.foo.bar import baz' → 'src/foo/bar.py'.
    Returns None if no parseable import is found.
    """
    import re
    for line in (test_content or "").splitlines():
        m = re.match(r"^\s*from\s+([\w.]+)\s+import\s+", line)
        if m:
            module = m.group(1)
            # Only handle src.* or v2.src.* imports that map to real files
            if module.startswith("src.") or module.startswith("v2.src."):
                return module.replace(".", "/") + ".py"
        m2 = re.match(r"^\s*import\s+(src[\w.]*|v2\.src[\w.]*)", line)
        if m2:
            module = m2.group(1)
            return module.replace(".", "/") + ".py"
    return None


def default_runner(role, payload):
    if role == "implementer":
        mission = payload["mission"]
        requirements = payload["requirements"]
        test_plan = payload["test_author"]
        feedback = payload.get("feedback", [])
        # Inject the exact target path so the coder writes to the right file.
        # _target_rel is the repo-relative path (e.g. src/constants.py).
        # The coder runs with cwd=worktree, so relative path is correct;
        # do NOT use _target_abs here — that points to the main repo, not the worktree.
        target_rel = test_plan.get("_target_rel") or ""
        target_abs = test_plan.get("_target_abs") or ""
        # Inject the CURRENT file contents so the coder doesn't hallucinate
        # that the function already exists.  Claude in print mode reads files
        # lazily and sometimes invents content based on training data; showing
        # the real text forces it to reconcile with what's actually on disk.
        current_file_snippet = ""
        if target_abs and os.path.exists(target_abs):
            try:
                with open(target_abs, encoding="utf-8", errors="replace") as _f:
                    _contents = _f.read()
                current_file_snippet = (
                    f"\n\nCURRENT CONTENT OF {target_rel} (this is the REAL file "
                    f"content — the function you must add is NOT present yet):\n"
                    f"```python\n{_contents[:3000]}\n```"
                )
            except OSError:
                pass
        target_directive = (
            f"\n\nTARGET FILE (you are in a git worktree; write ONLY to this path relative to cwd): {target_rel}"
            if target_rel else ""
        )
        prompt = (
            f"{mission['mission']}\n\nREQUIREMENTS:\n{json.dumps(requirements)}\n"
            f"TEST AUTHOR CONTRACT:\n{json.dumps(test_plan)}\n"
            f"REVIEW FEEDBACK:\n{json.dumps(feedback)}\n"
            "The red test already exists in the worktree at the path shown in TEST AUTHOR CONTRACT. "
            "Implement the function and make the test pass (green). "
            "IMPORTANT: do NOT create git worktrees or new git branches — you are already "
            "in an isolated worktree. Just edit the target file directly."
            f"{target_directive}"
            f"{current_file_snippet}"
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
            "--no-docs",  # avoid unrelated project docs confusing the coder
        ]
        # Deterministically seed the red test into the worktree so the gate exists
        # regardless of whether the agent recreates it (the file-not-found blocker).
        seed_tmp = None
        test_file = (test_plan.get("test_file") or "").strip()
        test_content = test_plan.get("test_content")
        if test_file and test_content:
            import tempfile
            fd, seed_tmp = tempfile.mkstemp(suffix=".py", prefix="ody-seedtest-")
            with os.fdopen(fd, "w") as fh:
                fh.write(test_content)
            cmd += ["--seed-test-path", test_file, "--seed-test-src", seed_tmp]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, env=_RUNNER_ENV)
        finally:
            if seed_tmp and os.path.exists(seed_tmp):
                os.unlink(seed_tmp)
        output = proc.stdout + proc.stderr
        green = proc.returncode == 0 and "PASS" in output
        # Surface the real failure, not the output tail — deprecation warnings on the
        # last line were masking actual causes in the captured reason.
        feedback = output[-2000:] if green else (_failure_summary(output) or output[-2000:])
        return {"green": green, "feedback": feedback}

    repo = (payload.get("mission") or {}).get("repo") if isinstance(payload.get("mission"), dict) else None
    filelist = _repo_filelist(repo)

    prompts = {
        "proposer": (
            "Act as the mission proposer. Return JSON with a missions array. "
            "Each mission must contain mission, test, priority, evidence, and "
            "allowed_files. Rank only novel, testable improvements."
        ),
        "requirements": (
            "You are the REQUIREMENTS role in a bounded pipeline. You never write code and never produce prose paragraphs. "
            "Your sole output is one JSON object that EXACTLY matches this schema — no trailing keys, no markdown fences, no commentary before or after:\n\n"
            "{\n"
            "  \"role\": \"requirements\",\n"
            "  \"mission_id\": \"<uuid>\",\n"
            "  \"user_intent\": \"<one sentence, verbatim from caller>\",\n"
            "  \"scope\": {\"in\": [\"<concrete deliverable>\"], \"out\": [\"<explicit non-goal>\"]},\n"
            "  \"acceptance_criteria\": [{\"id\": \"AC<n>\", \"given\": \"<state>\", \"when\": \"<action>\", \"then\": \"<observable result>\"}],\n"
            "  \"edge_cases\": [{\"id\": \"EC<n>\", \"input\": \"<shape>\", \"expected\": \"<behavior>\"}],\n"
            "  \"allowed_files\": [\"<repo-relative path>\"],\n"
            "  \"test_command\": \"<shell command that must exit 0 to pass the gate>\",\n"
            "  \"unknowns\": [\"<assumption you made because the caller did not specify>\"]\n"
            "}\n\n"
            "Hard rules:\n"
            "1. Every acceptance_criterion must be machine-checkable by test_command. If you cannot express it as a command, rewrite it.\n"
            "2. unknowns is mandatory and non-empty if any ambiguity exists.\n"
            "3. Output is JSON-schema-validated. A parse error triggers corrective_feedback naming the offending path; regenerate the full object.\n"
            "4. You may ONLY reference files from this list in allowed_files:\n"
            f"{filelist}\n\n"
            "EXAMPLE INPUT → OUTPUT:\n"
            "Mission: 'Add parse_duration(s: str) -> int | None to utils/timefmt.py'\n"
            "Correct output: {\"role\":\"requirements\",\"mission_id\":\"m-7f3a\",\"user_intent\":\"Add parse_duration to timefmt.py\","
            "\"scope\":{\"in\":[\"new function in utils/timefmt.py\"],\"out\":[\"other modules\"]},\"acceptance_criteria\":"
            "[{\"id\":\"AC1\",\"given\":\"input '1h30m'\",\"when\":\"called\",\"then\":\"returns 5400\"}],"
            "\"edge_cases\":[{\"id\":\"EC1\",\"input\":\"''\",\"expected\":\"returns None\"}],"
            "\"allowed_files\":[\"utils/timefmt.py\"],\"test_command\":\"pytest tests/test_timefmt.py -v\","
            "\"unknowns\":[\"Whether uppercase '1H' is accepted\"]}"
        ),
        "test_author": (
            "You are the TEST_AUTHOR role. You never modify production code. "
            "Consume the requirements JSON and emit exactly one JSON object — strict, no fences, no prose:\n\n"
            "{\n"
            "  \"role\": \"test_author\",\n"
            "  \"mission_id\": \"<uuid matching requirements.mission_id>\",\n"
            "  \"red\": true,\n"
            "  \"test_file\": \"<repo-relative path to test file>\",\n"
            "  \"test_command\": \"<exact shell command from repo root>\",\n"
            "  \"test_content\": \"<full test file content as string>\",\n"
            "  \"coverage_map\": [{\"ac_id\": \"AC<n>\", \"covered_by\": \"<test function name>\"}],\n"
            "  \"unknowns\": [\"<gap between requirement and testable behavior>\"]\n"
            "}\n\n"
            "Hard rules:\n"
            "1. Every AC in requirements.acceptance_criteria MUST appear in coverage_map. Missing = schema violation.\n"
            "2. The test MUST FAIL when run against the CURRENT code, before any implementation. It must\n"
            "   call/import the not-yet-existing behavior so it errors (ImportError/AttributeError) or asserts\n"
            "   on a result the current code does not produce (AssertionError). A test that passes immediately\n"
            "   (e.g. `assert True`, asserting on behavior that already exists, or testing nothing) is INVALID\n"
            "   and will be rejected by the red gate. Set red=true ONLY when the test genuinely fails first.\n"
            "3. test_command must use only: pytest, -v, -q, -x, --tb=short, and .py file paths.\n"
            "4. Only reference files from this list:\n"
            f"{filelist}\n\n"
            "EXAMPLE — requirement 'add parse_duration to utils/timefmt.py' →\n"
            "VALID RED test_content: \"from utils.timefmt import parse_duration\\n\\n"
            "def test_parse_duration_hm():\\n    assert parse_duration('1h30m') == 5400\\n\"\n"
            "  (fails now with ImportError because parse_duration does not exist yet — this is correct.)\n"
            "INVALID test_content: \"def test_placeholder():\\n    assert True\\n\" (passes immediately — rejected.)"
        ),
        "red_team": (
            "You are the RED_TEAM role — an adversarial reliability reviewer. The test gate "
            "already passed; your job is to catch what passing tests miss. Emit exactly one "
            "JSON object — strict, no fences, no prose:\n\n"
            "{\n"
            "  \"role\": \"red_team\",\n"
            "  \"mission_id\": \"<uuid matching requirements.mission_id>\",\n"
            "  \"confidence\": <float 0.0-1.0 — your certainty the implementation is correct>,\n"
            "  \"verdict\": \"pass\" | \"revise\",\n"
            "  \"findings\": [{\"severity\": \"high|med|low\", \"category\": \"<class below>\", \"detail\": \"<what and where>\"}]\n"
            "}\n\n"
            "Check every implementation against these failure classes (ToolScan-derived):\n"
            "  - missing_ac: an acceptance_criterion in requirements is not actually satisfied\n"
            "  - edge_case_gap: a requirements.edge_case is unhandled (test passed but case untested)\n"
            "  - over_reach: code touches files outside requirements.allowed_files\n"
            "  - hallucinated_symbol: imports/calls a symbol that does not exist\n"
            "  - test_theater: the test passes without exercising the real behavior (tautological assert)\n"
            "  - silent_failure: errors swallowed, wrong return on the unhappy path\n\n"
            "Hard rules:\n"
            "1. verdict=pass ONLY if findings has no high-severity entry AND every AC is satisfied.\n"
            "2. confidence is a self-score: if < 0.7, you MUST return verdict=revise with concrete findings.\n"
            "3. Never certify in place of the test gate — a green test is necessary, not sufficient.\n"
            "4. Each finding.detail must name the specific file/line/AC, not a generic concern."
        ),
    }
    # System prompt carries the schema/rules (static, cacheable).
    # User turn carries only the mission payload (what M3 reasons about).
    # This keeps M3's thinking budget for the actual task, not re-reading the schema.
    system = prompts[role] + "\n\nRespond with valid JSON only. No prose, no fences."
    context = json.dumps(payload, sort_keys=True)
    raw = _m3_complete(context, system=system)  # no cap — free tier, let it burn
    answer = _json_answer(raw)
    # Roles must return an object; M3 sometimes emits a bare list/scalar. Treat that
    # as malformed so call_role retries with the JSON-only hint instead of crashing
    # downstream on `.get()` (surfaced as AttributeError: 'list' has no attribute 'get').
    if not isinstance(answer, dict):
        raise ValueError(f"role {role} returned non-object JSON ({type(answer).__name__})")
    return answer


class Supervisor:
    def __init__(self, state_dir, runner=None, max_attempts=3):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.queue_path = self.state_dir / "mission-queue.jsonl"
        self.ledger_path = self.state_dir / "supervisor-ledger.jsonl"
        self.receipts_path = self.state_dir / "role-receipts.jsonl"
        self.notes_dir = self.state_dir / "notes"
        self.notes_dir.mkdir(exist_ok=True)
        self.runner = runner or default_runner
        self.max_attempts = max_attempts

    # gnhf-style durable memory: failed-attempt lessons survive across daemon
    # cycles so a retried mission doesn't repeat the same mistakes (notes.md pattern).
    def _notes_path(self, key):
        return self.notes_dir / f"{key}.md"

    def _append_note(self, key, reason):
        if not reason:
            return
        reason_str = reason if isinstance(reason, str) else json.dumps(reason, ensure_ascii=False)
        line = reason_str.strip().splitlines()[0][:300]
        with self._notes_path(key).open("a") as handle:
            handle.write(f"- {line}\n")

    def _load_notes(self, key, limit=10):
        path = self._notes_path(key)
        if not path.exists():
            return []
        seen, notes = set(), []
        for line in path.read_text(errors="replace").splitlines():
            note = line.lstrip("- ").strip()
            if note and note not in seen:
                seen.add(note)
                notes.append(note)
        return notes[-limit:]

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
                # On JSON/empty retries, inject a "JSON only" nudge into payload
                current_payload = payload if attempt == 0 else {
                    **payload, "_retry_hint": "Respond with valid JSON only. No prose, no markdown, no explanation."
                }
                try:
                    output = self.runner(role, current_payload)
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

    _SAFE_TEST_DEFAULT = "pytest v2/tests/ -q"

    def _sanitize_test_command(self, cmd):
        """Strip flags M3 invents that pytest doesn't accept.

        Compound commands (&&, ;), python -c/-m, and __main__ invocations
        are replaced wholesale — they bypass token-level filtering.
        """
        if not cmd:
            return self._SAFE_TEST_DEFAULT
        # Reject compound or non-pytest invocations entirely
        if any(x in cmd for x in ("&&", ";", "python ", "__main__")):
            return self._SAFE_TEST_DEFAULT
        # Only allow known-safe flags; drop anything that looks invented
        safe_tokens = []
        for tok in cmd.split():
            if tok in ("-v", "-q", "-x", "-s", "--tb=short", "--tb=long",
                       "--tb=no", "--no-header", "-rN"):
                safe_tokens.append(tok)
            elif tok.startswith("tests/") or tok.startswith("v2/tests/") or tok.endswith(".py"):
                safe_tokens.append(tok)
            elif tok == "pytest":
                safe_tokens.append(tok)
            # drop unrecognised flags silently
        return " ".join(safe_tokens) if safe_tokens else self._SAFE_TEST_DEFAULT

    def _derive_test_command(self, test_plan):
        """Build the gate command from test_file (deterministic) rather than trusting
        M3's free-form test_command, which can name a path that doesn't exist."""
        tf = (test_plan.get("test_file") or "").strip()
        if tf.endswith(".py") and (tf.startswith("tests/") or tf.startswith("v2/tests/")):
            return f"pytest {tf} -q"
        return self._sanitize_test_command(test_plan.get("test_command"))

    def _enforce_path_coherence(self, requirements, test_plan, mission):
        """Pre-flight invariant: test-import-path == requirements-target == coder-write-path.

        Normalises all three to requirements.allowed_files[0].  If the test
        imports from a different module, the test_content is rewritten to
        import from the canonical target.  The resolved absolute path is
        stored in test_plan['_target_abs'] for the implementer prompt.
        """
        repo = Path(mission.get("repo") or os.getcwd()).resolve()
        allowed = requirements.get("allowed_files") or []
        target_rel = allowed[0] if allowed else None
        if not target_rel:
            return  # no target to enforce against

        target_abs = (repo / target_rel).resolve()

        # Record on test_plan so the implementer always has the absolute path
        test_plan["_target_abs"] = str(target_abs)
        test_plan["_target_rel"] = target_rel

        # Check what the test imports
        test_content = test_plan.get("test_content") or ""
        import_rel = _extract_import_target(test_content)
        if not import_rel or import_rel == target_rel:
            return  # already coherent

        # Paths disagree — rewrite test_content to import from target_rel
        import re
        target_module = target_rel.replace("/", ".").removesuffix(".py")
        new_content = re.sub(
            r"(^\s*from\s+)([\w.]+)(\s+import\s+)",
            lambda m: m.group(1) + target_module + m.group(3),
            test_content,
            count=1,
            flags=re.MULTILINE,
        )
        self.record({
            "event": "path_coherence_fix",
            "from": import_rel,
            "to": target_rel,
        })
        test_plan["test_content"] = new_content

    def _validate_and_fix_requirements(self, requirements, mission, feedback, max_fix=3):
        """Re-ask M3 for requirements until all allowed_files are real paths."""
        repo = Path(mission.get("repo") or os.getcwd())
        filelist = _repo_filelist(str(repo))
        real_files = set(filelist.splitlines())

        for fix_attempt in range(max_fix):
            claimed = requirements.get("allowed_files") or []
            bad = [f for f in claimed if f not in real_files]
            if not bad:
                # Sanitize test_command before returning
                if "test_command" in requirements:
                    requirements["test_command"] = self._sanitize_test_command(
                        requirements["test_command"]
                    )
                return requirements
            correction = (
                f"These files do not exist: {bad}. "
                f"You MUST pick only from this list:\n{filelist}\n"
                "Return corrected JSON with valid allowed_files."
            )
            self.record({"event": "requirements_correction", "bad_files": bad,
                         "fix_attempt": fix_attempt + 1})
            requirements = self.call_role("requirements", {
                "mission": mission,
                "feedback": feedback + [correction],
                "_correction": correction,
            })
        # After max_fix, sanitize whatever we have anyway
        if "test_command" in requirements:
            requirements["test_command"] = self._sanitize_test_command(
                requirements["test_command"]
            )
        return requirements

    def _run_mission(self, mission):
        key = mission["mission_key"]
        # Seed from durable notes so a retried mission learns from prior cycles
        feedback = self._load_notes(key)

        # Get requirements, then validate file paths — re-ask M3 if it hallucinated
        requirements = self.call_role("requirements", {"mission": mission, "feedback": feedback})
        requirements = self._validate_and_fix_requirements(requirements, mission, feedback)

        for attempt in range(1, self.max_attempts + 1):
            test_plan = self.call_role("test_author", {
                "mission": mission,
                "requirements": requirements,
                "feedback": feedback,
                "attempt": attempt,
            })
            # Deterministic test_command: derive it from test_file so M3 cannot
            # point pytest at a path that doesn't exist (the "file or directory not
            # found" class). Fall back to sanitizing its free-form command only if
            # no usable test_file was given.
            test_plan["test_command"] = self._derive_test_command(test_plan)
            # PRE-FLIGHT: enforce that test-import-path == requirements-target ==
            # coder-write-path before the implementer runs.
            self._enforce_path_coherence(requirements, test_plan, mission)
            if not test_plan.get("red"):
                reason = "test author did not establish a red gate"
                feedback.append(reason)
                self.record({"event": "attempt_failed", "mission_key": key,
                             "attempt": attempt, "reason": reason})
                self._append_note(key, reason)
                # Re-derive requirements with this feedback so next attempt improves
                requirements = self._validate_and_fix_requirements(
                    self.call_role("requirements", {"mission": mission, "feedback": feedback}),
                    mission, feedback,
                )
                continue

            implementation = self.call_role("implementer", {
                "mission": mission,
                "requirements": requirements,
                "test_author": test_plan,
                "feedback": feedback,
                "attempt": attempt,
            })
            impl_feedback = implementation.get("feedback") or ""
            if not implementation.get("green"):
                reason = impl_feedback[-500:] if impl_feedback else "green gate failed"
                feedback.append(reason)
                self.record({"event": "attempt_failed", "mission_key": key,
                             "attempt": attempt, "reason": reason})
                self._append_note(key, reason)
                # If implementer failed due to bad file, correct requirements
                if "missing file" in impl_feedback or "bad --hybrid" in impl_feedback:
                    requirements = self._validate_and_fix_requirements(
                        self.call_role("requirements", {"mission": mission, "feedback": feedback}),
                        mission, feedback,
                    )
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
            self._append_note(key, feedback[-1])

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

if __name__ == '__main__':
    import sys
    sys.exit(supervise_main())
