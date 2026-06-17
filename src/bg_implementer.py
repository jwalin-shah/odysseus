import asyncio
import logging
import httpx
import subprocess
import json
import sqlite3
import uuid
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# --- STATE MANAGEMENT ---

def load_implementer_state() -> Dict[str, Any]:
    """Load implementer state from data/implementer_state.json. Returns {processed: []} if missing."""
    state_path = Path("data/implementer_state.json")
    if not state_path.exists():
        return {"processed": []}
    try:
        with open(state_path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load implementer state: {e}")
        return {"processed": []}

def save_implementer_state(state: Dict[str, Any]):
    """Save implementer state to data/implementer_state.json."""
    state_path = Path("data/implementer_state.json")
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save implementer state: {e}")

def mark_finding_processed(msg_id: str):
    """Mark a finding as processed in the state file."""
    state = load_implementer_state()
    if msg_id not in state["processed"]:
        state["processed"].append(msg_id)
        save_implementer_state(state)

# --- FINDING DISCOVERY ---

def pick_finding() -> Optional[Tuple[str, str, str]]:
    """Query app.db for the newest assistant message in bg-* sessions (excluding bg-implementer).

    Returns (msg_id, session_name, content) or None if no unprocessed findings exist.
    """
    db_path = Path("data/app.db")
    if not db_path.exists():
        logger.warning("Database not found")
        return None

    state = load_implementer_state()
    processed_ids = set(state["processed"])

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Query for newest assistant message in bg-* sessions, excluding bg-implementer
        cur.execute("""
            SELECT m.id, s.name, m.content
            FROM chat_messages m
            JOIN sessions s ON m.session_id = s.id
            WHERE s.name LIKE 'bg-%'
              AND s.name NOT LIKE 'bg-implementer%'
              AND m.role = 'assistant'
            ORDER BY m.id DESC
            LIMIT 100
        """)

        rows = cur.fetchall()
        conn.close()

        # Return the first unprocessed finding
        for msg_id, session_name, content in rows:
            if msg_id not in processed_ids:
                logger.info(f"Found unprocessed finding: {msg_id} from {session_name}")
                return (msg_id, session_name, content)

        logger.debug("No unprocessed findings found")
        return None
    except Exception as e:
        logger.error(f"Failed to pick finding: {e}")
        return None

# --- WORKTREE ISOLATION ---

def create_worktree() -> Optional[str]:
    """Create a temporary git worktree. Returns path on success, None on failure."""
    try:
        # Create unique worktree path
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        wtpath = Path(f"/tmp/ody-impl-{ts}-{uuid.uuid4().hex[:8]}")

        # Add worktree pointing to current HEAD
        result = subprocess.run(
            ["git", "worktree", "add", str(wtpath), "HEAD"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"Failed to create worktree: {result.stderr}")
            return None

        logger.info(f"Created worktree: {wtpath}")
        return str(wtpath)
    except Exception as e:
        logger.error(f"Failed to create worktree: {e}")
        return None

def remove_worktree(wtpath: str):
    """Remove a git worktree. Always succeeds (logs errors but doesn't fail)."""
    try:
        result = subprocess.run(
            ["git", "worktree", "remove", "--force", wtpath],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            logger.warning(f"Failed to remove worktree {wtpath}: {result.stderr}")
        else:
            logger.info(f"Removed worktree: {wtpath}")
    except Exception as e:
        logger.warning(f"Exception removing worktree {wtpath}: {e}")

# --- M3 RESPONSE PARSING ---

def parse_m3_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse M3 response into a unified edit + test record.

    Two input formats are accepted (newer M3 outputs both):

    1. FILE / CONTENT style (newer, simpler):
         FILE: src/example.py
         CONTENT:
         def hello():
             return "world"

         TEST: tests/test_example.py
         TEST_CONTENT:
         def test_hello():
             assert True

    2. Aider SEARCH / REPLACE style (legacy, multi-file):
         src/example.py
         <<<< SEARCH
         ...
         ====
         ...
         >>>> REPLACE

         TEST_FILE: tests/test_example.py
         TEST_CONTENT:
         def test_hello():
             assert True

    Returns a dict with:
        - file_path   (str|None) — the single target file (from FILE: or the
                                   first Aider block)
        - diff_or_body(str|None) — the new file content (from CONTENT: or the
                                   REPLACE of the first Aider block)
        - edits       (list)     — non-empty for multi-file Aider responses
        - test_path   (str|None)
        - test_body   (str|None)

    Returns None if neither format is found.
    """
    if response_text.strip() == "CANNOT_PATCH":
        logger.warning("M3 response declined to patch: CANNOT_PATCH")
        return None

    import re
    try:
        result = {
            "file_path": None,
            "diff_or_body": None,
            "edits": [],
            "test_path": None,
            "test_body": None,
        }

        # ── Format 1: FILE / CONTENT ─────────────────────────────────
        # Match the FILE: line followed by a CONTENT: block (until blank
        # line or end of string).
        file_content_re = re.compile(
            r"^FILE:\s*(\S+)\s*\nCONTENT:\s*\n(.*?)(?=\n\s*\n|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        m = file_content_re.search(response_text)
        if m:
            result["file_path"] = m.group(1).strip()
            result["diff_or_body"] = m.group(2).rstrip()
            # Surface the single-file edit as a one-element edits list so
            # downstream code that already iterates ``edits`` keeps working.
            result["edits"].append({
                "file_path": result["file_path"],
                "search": "",
                "replace": result["diff_or_body"],
            })

        # ── Format 2: Aider SEARCH / REPLACE ─────────────────────────
        # Only used if Format 1 didn't match; if both match, Format 1 wins
        # for file_path / diff_or_body and the Aider blocks add to edits.
        if not result["file_path"]:
            block_pattern = re.compile(
                r"^([a-zA-Z0-9_./-]+)\s*\n<<<< SEARCH\n(.*?)\n====\n(.*?)\n>>>> REPLACE",
                re.MULTILINE | re.DOTALL,
            )
            for match in block_pattern.finditer(response_text):
                block = {
                    "file_path": match.group(1).strip(),
                    "search": match.group(2),
                    "replace": match.group(3),
                }
                result["edits"].append(block)
                # First block becomes the unified file_path / diff_or_body.
                if result["file_path"] is None:
                    result["file_path"] = block["file_path"]
                    result["diff_or_body"] = block["replace"]

        # ── Test section: TEST_FILE: or TEST: ────────────────────────
        test_re = re.compile(
            r"(?:^|\n)\s*(?:TEST_FILE|TEST):\s*([^\n]+)\n\s*TEST_CONTENT:\s*\n(.*)",
            re.DOTALL,
        )
        test_match = test_re.search(response_text)
        if test_match:
            result["test_path"] = test_match.group(1).strip()
            body = test_match.group(2).strip()
            if body.endswith("```"):
                body = body[:-3].strip()
            result["test_body"] = body

        # Strict mode: a usable response must have AT LEAST one edit AND
        # complete test material. Missing pieces return None so the worker
        # retries rather than acting on a partial parse.
        has_edit = bool(result["edits"])
        has_full_test = bool(result["test_path"]) and bool(result["test_body"])
        if not has_edit or not has_full_test:
            logger.warning(
                "M3 response incomplete: edits=%d test_path=%s test_body=%s",
                len(result["edits"]), result["test_path"],
                "present" if result["test_body"] else "missing",
            )
            return None

        logger.info(
            f"Parsed M3 response: {len(result['edits'])} edits, "
            f"file={result['file_path']}, test={result['test_path']}"
        )
        return result
    except Exception as e:
        logger.error(f"Failed to parse M3 response: {e}")
        return None

# --- IMPLEMENTATION PASS ---

async def run_implementation_pass(finding_id: str, session_name: str, report_content: str) -> Dict[str, Any]:
    """Execute a single implementation attempt.

    Returns dict with: {success, error, diff_stat, test_output, worktree}
    """
    wtpath = None
    try:
        # 1. Create worktree
        wtpath = create_worktree()
        if not wtpath:
            return {"success": False, "error": "Failed to create worktree"}

        # 2. Truncate report to 6000 chars
        truncated_report = report_content[:6000]

        # 3. Ask M3 for implementation
        prompt = (
            f"Given this research finding, implement ONE small concrete improvement to the codebase.\n\n"
            f"RESEARCH REPORT:\n{truncated_report}\n\n"
            f"TASK:\n"
            f"1. Choose ONE implementable improvement (feature, bugfix, refactor, or test).\n"
            f"2. Emit the fix using ONLY the strict Aider SEARCH/REPLACE format below.\n"
            f"3. Emit a pytest regression using the TEST_FILE format below.\n\n"
            f"OUTPUT CONTRACT:\n"
            f"- Output only edit blocks and the test file. No prose, markdown, or analysis.\n"
            f"- Do NOT emit unified diffs, diff fences, git patches, hunk headers, or +/- line prefixes.\n"
            f"- Do NOT use placeholder paths. Every path must be a real repository-relative path.\n"
            f"- The SEARCH section must be copied verbatim from the current file and must match exactly once.\n"
            f"- If you cannot produce an exact SEARCH block and a complete TEST_FILE, output exactly the word: CANNOT_PATCH\n\n"
            f"EDIT FORMAT:\n"
            f"path/to/existing_file.py\n"
            f"<<<< SEARCH\n"
            f"exact existing lines to find and replace\n"
            f"====\n"
            f"replacement lines\n"
            f">>>> REPLACE\n\n"
            f"TEST_FILE: path/to/test_file.py\n"
            f"TEST_CONTENT:\n"
            f"<complete pytest test file body>\n"
        )

        base_url = "http://127.0.0.1:7860"
        m3_response = None

        try:
            from src.defensive_architect import DefensiveArchitectAgent
            critic = DefensiveArchitectAgent(base_url)
            hostile_review = await critic.review_staged_skill(finding_id) # Using finding_id as mock path/identifier
            prompt = f"CRITICAL SECURITY REVIEW FROM HOSTILE ARCHITECT:\n{hostile_review}\n\n{prompt}"
        except Exception as e:
            logger.warning(f"Hostile Critic failed, proceeding without review: {e}")

        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                # Get or create session
                sessions_res = await client.get(f"{base_url}/api/sessions", headers={"X-Odysseus-Owner": "admin"})
                impl_session_id = next((s["id"] for s in sessions_res.json() if s["name"] == "bg-implementer"), None)
                if not impl_session_id:
                    create_res = await client.post(
                        f"{base_url}/api/session",
                        headers={"X-Odysseus-Owner": "admin"},
                        data={"name": "bg-implementer", "model": "MiniMax-M3", "endpoint_id": "dd45625c", "skip_validation": "true"}
                    )
                    impl_session_id = create_res.json().get("id")

                # Ask M3
                payload = {"message": prompt, "session": impl_session_id, "model": "MiniMax-M3"}
                res = await client.post(f"{base_url}/api/chat", json=payload, headers={"X-Odysseus-Owner": "admin"})

                if res.status_code == 200:
                    m3_response = res.json().get("text", "")
                else:
                    return {"success": False, "error": f"M3 request failed: {res.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"M3 request exception: {e}"}

        # 4. Parse M3 response
        parsed = parse_m3_response(m3_response)
        if not parsed:
            return {"success": False, "error": "M3 response unparseable"}

        # 5. Write the test file FIRST (Red-Green TDD Enforcement)
        try:
            if parsed.get("test_path") and parsed.get("test_body"):
                test_path = Path(wtpath) / parsed["test_path"]
                test_path.parent.mkdir(parents=True, exist_ok=True)
                test_path.write_text(parsed["test_body"])
                logger.info(f"Wrote test file {test_path}")
            else:
                return {"success": False, "error": "No test path/body provided by model"}
        except Exception as e:
            return {"success": False, "error": f"Failed to write test file: {e}"}

        # 6. Run pytest BEFORE edits (MUST FAIL)
        test_rel = parsed.get("test_path", "")
        try:
            result_before = subprocess.run(
                [".venv/bin/python", "-m", "pytest", test_rel, "-q"],
                cwd=wtpath, capture_output=True, text=True, timeout=120
            )
            if result_before.returncode == 0:
                logger.warning("Test passed BEFORE edits (invalid test).")
                return {"success": False, "error": "Test is not robust: it passed before the code was patched."}
        except Exception as e:
            return {"success": False, "error": f"Exception during pre-test: {e}"}

        # 7. Apply Aider edits to worktree
        try:
            for edit in parsed.get("edits", []):
                file_path = Path(wtpath) / edit["file_path"]
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                if file_path.exists():
                    content = file_path.read_text()
                    if edit["search"] in content:
                        content = content.replace(edit["search"], edit["replace"], 1)
                        file_path.write_text(content)
                        logger.info(f"Applied Aider block to {file_path}")
                    else:
                        logger.warning(f"SEARCH block not found in {file_path}")
                        return {"success": False, "error": f"SEARCH block exact match failed in {file_path}"}
                else:
                    file_path.write_text(edit["replace"])
                    logger.info(f"Created new file via Aider block {file_path}")
        except Exception as e:
            return {"success": False, "error": f"Failed to apply edits: {e}"}

        # 8. Run pytest AFTER edits (MUST PASS)
        try:
            result = subprocess.run(
                [".venv/bin/python", "-m", "pytest", test_rel, "-q"],
                cwd=wtpath,
                capture_output=True,
                text=True,
                timeout=120
            )
            test_output = result.stdout + result.stderr
            test_passed = result.returncode == 0
        except subprocess.TimeoutExpired:
            test_output = "TIMEOUT (120s)"
            test_passed = False
        except Exception as e:
            test_output = f"Exception: {e}"
            test_passed = False

        # 7. Compute diff stat
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=wtpath,
                capture_output=True,
                text=True,
                timeout=10
            )
            diff_stat = diff_result.stdout
        except:
            diff_stat = "(could not compute)"

        return {
            "success": True,
            "error": None,
            "diff_stat": diff_stat,
            "test_output": test_output[-500:] if test_output else "",  # Last 500 chars
            "test_passed": test_passed,
            "file_path": parsed["file_path"],
            "test_path": parsed["test_path"],
        }
    except Exception as e:
        logger.error(f"Implementation pass exception: {e}")
        return {"success": False, "error": f"Exception: {e}"}
    finally:
        if wtpath:
            remove_worktree(wtpath)

# --- RECORD OUTCOME ---

async def record_outcome(base_url: str, finding_id: str, session_name: str, outcome: Dict[str, Any]):
    """Record the implementation outcome to the bg-implementer session."""
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            # Get or create bg-implementer session
            sessions_res = await client.get(f"{base_url}/api/sessions", headers={"X-Odysseus-Owner": "admin"})
            impl_session_id = next((s["id"] for s in sessions_res.json() if s["name"] == "bg-implementer"), None)
            if not impl_session_id:
                create_res = await client.post(
                    f"{base_url}/api/session",
                    headers={"X-Odysseus-Owner": "admin"},
                    data={"name": "bg-implementer", "model": "MiniMax-M3", "endpoint_id": "dd45625c", "skip_validation": "true"}
                )
                impl_session_id = create_res.json().get("id")

            # Build report
            if outcome["success"]:
                report = (
                    f"SUCCESS: Implemented finding {finding_id} from {session_name}\n"
                    f"Test: {outcome.get('test_path', 'unknown')}\n"
                    f"Diff stat:\n{outcome.get('diff_stat', '')}\n"
                    f"Test passed: {outcome.get('test_passed', False)}\n"
                    f"Test output:\n{outcome.get('test_output', '(no output)')}"
                )
            else:
                report = (
                    f"FAILED: Implementation attempt for {finding_id} from {session_name}\n"
                    f"Error: {outcome.get('error', 'unknown')}"
                )

            # Post to session
            payload = {"message": report, "session": impl_session_id, "model": "MiniMax-M3"}
            await client.post(f"{base_url}/api/chat", json=payload, headers={"X-Odysseus-Owner": "admin"})
            logger.info(f"Recorded outcome for {finding_id}")
    except Exception as e:
        logger.error(f"Failed to record outcome: {e}")

# --- MAIN LOOP ---

async def run_implementer_loop(interval: int = 1200):
    """Run the bg-implementer loop. Attempts one finding every interval_seconds."""
    base_url = "http://127.0.0.1:7860"

    while True:
        try:
            # Pick a finding
            finding = pick_finding()
            if not finding:
                logger.debug("No unprocessed findings; sleeping...")
                await asyncio.sleep(interval)
                continue

            msg_id, session_name, content = finding
            logger.info(f"Processing finding {msg_id} from {session_name}")

            # Run implementation pass
            outcome = await run_implementation_pass(msg_id, session_name, content)

            # Record outcome
            await record_outcome(base_url, msg_id, session_name, outcome)

            # Mark as processed (regardless of outcome)
            mark_finding_processed(msg_id)
            logger.info(f"Marked {msg_id} as processed")

        except Exception as e:
            logger.error(f"Implementer loop error: {e}")
            await asyncio.sleep(300)

        await asyncio.sleep(interval)
