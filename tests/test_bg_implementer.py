"""Tests for background implementer loop: state dedup, M3 parsing, worktree isolation."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock, mock_open
import pytest

from src.bg_implementer import (
    load_implementer_state,
    save_implementer_state,
    mark_finding_processed,
    pick_finding,
    parse_m3_response,
    create_worktree,
    remove_worktree,
)


class TestStateManagement:
    """Test state file loading and saving."""

    def test_load_implementer_state_missing_file(self):
        """Return default state if file missing."""
        with patch("src.bg_implementer.Path") as mock_path:
            mock_config = MagicMock()
            mock_config.exists.return_value = False
            mock_path.return_value = mock_config
            result = load_implementer_state()
            assert result == {"processed": []}

    def test_load_implementer_state_success(self, tmp_path):
        """Load valid implementer state."""
        state_file = tmp_path / "implementer_state.json"
        state = {"processed": ["msg1", "msg2"]}
        state_file.write_text(json.dumps(state))

        with patch("src.bg_implementer.Path") as mock_path:
            mock_path.return_value = state_file
            result = load_implementer_state()
            assert result == state

    def test_load_implementer_state_invalid_json(self, tmp_path):
        """Return default on invalid JSON."""
        state_file = tmp_path / "implementer_state.json"
        state_file.write_text("{ invalid json }")

        with patch("src.bg_implementer.Path") as mock_path:
            mock_path.return_value = state_file
            result = load_implementer_state()
            assert result == {"processed": []}

    def test_save_implementer_state(self, tmp_path):
        """Save state to file."""
        state_file = tmp_path / "implementer_state.json"

        with patch("src.bg_implementer.Path") as mock_path:
            mock_cfg = MagicMock()
            mock_cfg.parent.mkdir = MagicMock()
            mock_path.return_value = mock_cfg
            # Need to configure the mock to allow open()
            mock_cfg.__truediv__ = lambda self, x: state_file
            mock_path.return_value = mock_cfg

            state = {"processed": ["msg1"]}
            save_implementer_state(state)
            # Just verify it doesn't crash; actual file write is tested via integration

    def test_mark_finding_processed(self, tmp_path):
        """Mark a finding as processed."""
        state_file = tmp_path / "implementer_state.json"
        state_file.write_text(json.dumps({"processed": []}))

        with patch("src.bg_implementer.Path") as mock_path:
            mock_path.return_value = state_file
            mark_finding_processed("msg1")
            # Verify file was updated
            state = json.loads(state_file.read_text())
            assert "msg1" in state["processed"]

    def test_mark_finding_processed_dedup(self, tmp_path):
        """Don't add duplicate msg_ids."""
        state_file = tmp_path / "implementer_state.json"
        state_file.write_text(json.dumps({"processed": ["msg1"]}))

        with patch("src.bg_implementer.Path") as mock_path:
            mock_path.return_value = state_file
            mark_finding_processed("msg1")
            state = json.loads(state_file.read_text())
            assert state["processed"].count("msg1") == 1


class TestPickFinding:
    """Test finding discovery from database."""

    def test_pick_finding_no_database(self):
        """Return None if database not found."""
        with patch("src.bg_implementer.Path") as mock_path:
            mock_db = MagicMock()
            mock_db.exists.return_value = False
            mock_path.return_value = mock_db
            result = pick_finding()
            assert result is None

    def test_pick_finding_no_unprocessed(self, tmp_path):
        """Return None if all findings processed."""
        # Create temp DB with one processed message
        db_file = tmp_path / "app.db"
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("CREATE TABLE sessions (id VARCHAR PRIMARY KEY, name VARCHAR)")
        cur.execute("CREATE TABLE chat_messages (id VARCHAR PRIMARY KEY, session_id VARCHAR, role VARCHAR, content TEXT)")
        cur.execute("INSERT INTO sessions VALUES ('s1', 'bg-test')")
        cur.execute("INSERT INTO chat_messages VALUES ('m1', 's1', 'assistant', 'finding')")
        conn.commit()
        conn.close()

        # Mock state to mark m1 as processed
        state = {"processed": ["m1"]}
        state_file = tmp_path / "implementer_state.json"
        state_file.write_text(json.dumps(state))

        with patch("src.bg_implementer.Path") as mock_path_cls:
            mock_path_cls.side_effect = lambda p="": (
                db_file if str(p) == "data/app.db"
                else state_file if str(p) == "data/implementer_state.json"
                else Path(str(p))
            )
            with patch("src.bg_implementer.load_implementer_state", return_value=state):
                result = pick_finding()
                assert result is None

    def test_pick_finding_excludes_bg_implementer(self, tmp_path):
        """Exclude messages from bg-implementer sessions."""
        db_file = tmp_path / "app.db"
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("CREATE TABLE sessions (id VARCHAR PRIMARY KEY, name VARCHAR)")
        cur.execute("CREATE TABLE chat_messages (id VARCHAR PRIMARY KEY, session_id VARCHAR, role VARCHAR, content TEXT)")
        cur.execute("INSERT INTO sessions VALUES ('s1', 'bg-implementer')")
        cur.execute("INSERT INTO sessions VALUES ('s2', 'bg-test')")
        cur.execute("INSERT INTO chat_messages VALUES ('m1', 's1', 'assistant', 'impl-msg')")
        cur.execute("INSERT INTO chat_messages VALUES ('m2', 's2', 'assistant', 'test-finding')")
        conn.commit()
        conn.close()

        with patch("src.bg_implementer.Path") as mock_path_cls:
            mock_path_cls.return_value = db_file
            with patch("src.bg_implementer.load_implementer_state", return_value={"processed": []}):
                result = pick_finding()
                assert result is not None
                assert result[0] == "m2"  # Should pick from bg-test, not bg-implementer
                assert result[1] == "bg-test"

    def test_pick_finding_success(self, tmp_path):
        """Return newest unprocessed assistant message from bg-* session."""
        db_file = tmp_path / "app.db"
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("CREATE TABLE sessions (id VARCHAR PRIMARY KEY, name VARCHAR)")
        cur.execute("CREATE TABLE chat_messages (id VARCHAR PRIMARY KEY, session_id VARCHAR, role VARCHAR, content TEXT)")
        cur.execute("INSERT INTO sessions VALUES ('s1', 'bg-code-architect')")
        cur.execute("INSERT INTO chat_messages VALUES ('m1', 's1', 'assistant', 'finding1')")
        cur.execute("INSERT INTO chat_messages VALUES ('m2', 's1', 'user', 'question')")
        cur.execute("INSERT INTO chat_messages VALUES ('m3', 's1', 'assistant', 'finding2')")
        conn.commit()
        conn.close()

        with patch("src.bg_implementer.Path") as mock_path_cls:
            mock_path_cls.return_value = db_file
            with patch("src.bg_implementer.load_implementer_state", return_value={"processed": []}):
                result = pick_finding()
                assert result is not None
                msg_id, session_name, content = result
                assert msg_id == "m3"  # Newest
                assert session_name == "bg-code-architect"
                assert content == "finding2"


class TestM3ResponseParsing:
    """Test M3 response parsing."""

    def test_parse_m3_response_valid(self):
        """Parse valid M3 response."""
        response = """FILE: src/example.py
CONTENT:
def hello():
    return "world"

TEST: tests/test_example.py
TEST_CONTENT:
def test_hello():
    assert True
"""
        result = parse_m3_response(response)
        assert result is not None
        assert result["file_path"] == "src/example.py"
        assert "def hello()" in result["diff_or_body"]
        assert result["test_path"] == "tests/test_example.py"
        assert "def test_hello()" in result["test_body"]

    def test_parse_m3_response_unified_diff(self):
        """Parse M3 response with unified diff."""
        response = """FILE: src/example.py
CONTENT:
--- a/src/example.py
+++ b/src/example.py
@@ -1,3 +1,4 @@
 def hello():
+    print("start")
     return "world"

TEST: tests/test_example.py
TEST_CONTENT:
def test_hello():
    assert True
"""
        result = parse_m3_response(response)
        assert result is not None
        assert result["file_path"] == "src/example.py"
        assert "---" in result["diff_or_body"]
        assert "+++" in result["diff_or_body"]

    def test_parse_m3_response_missing_file(self):
        """Return None if FILE section missing."""
        response = """CONTENT:
some content

TEST: test.py
TEST_CONTENT:
test body
"""
        result = parse_m3_response(response)
        assert result is None

    def test_parse_m3_response_missing_content(self):
        """Return None if CONTENT section missing."""
        response = """FILE: src/example.py
TEST: test.py
TEST_CONTENT:
test body
"""
        result = parse_m3_response(response)
        assert result is None

    def test_parse_m3_response_missing_test(self):
        """Return None if TEST section missing."""
        response = """FILE: src/example.py
CONTENT:
content

TEST_CONTENT:
test body
"""
        result = parse_m3_response(response)
        assert result is None

    def test_parse_m3_response_missing_test_content(self):
        """Return None if TEST_CONTENT section missing."""
        response = """FILE: src/example.py
CONTENT:
content

TEST: test.py
"""
        result = parse_m3_response(response)
        assert result is None

    def test_parse_m3_response_malformed(self):
        """Return None on malformed response."""
        response = "garbage data"
        result = parse_m3_response(response)
        assert result is None


class TestWorktreeIsolation:
    """Test worktree creation and removal."""

    def test_create_worktree_success(self):
        """Create worktree returns path."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = create_worktree()
            assert result is not None
            assert "/tmp/ody-impl-" in result

    def test_create_worktree_failure(self):
        """Return None on git worktree add failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "git error"
            result = create_worktree()
            assert result is None

    def test_create_worktree_timeout(self):
        """Return None on timeout."""
        with patch("subprocess.run", side_effect=Exception("timeout")):
            result = create_worktree()
            assert result is None

    def test_remove_worktree_success(self):
        """Remove worktree succeeds."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            remove_worktree("/tmp/test-wt")
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "worktree" in args
            assert "remove" in args

    def test_remove_worktree_failure_logged(self):
        """Log warning on removal failure but don't crash."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "error"
            with patch("src.bg_implementer.logger") as mock_logger:
                remove_worktree("/tmp/test-wt")
                mock_logger.warning.assert_called()

    def test_remove_worktree_exception_handled(self):
        """Handle exception on removal."""
        with patch("subprocess.run", side_effect=Exception("test error")):
            with patch("src.bg_implementer.logger") as mock_logger:
                remove_worktree("/tmp/test-wt")
                mock_logger.warning.assert_called()


class TestIntegration:
    """Integration tests with minimal mocking."""

    def test_state_roundtrip(self, tmp_path):
        """Load, modify, and save state."""
        state_file = tmp_path / "implementer_state.json"
        state_file.write_text(json.dumps({"processed": []}))

        with patch("src.bg_implementer.Path") as mock_path:
            mock_path.return_value = state_file
            state = load_implementer_state()
            assert state == {"processed": []}

            state["processed"].append("test_id")
            save_implementer_state(state)

            reloaded = load_implementer_state()
            assert "test_id" in reloaded["processed"]

    def test_pick_finding_with_real_db(self, tmp_path):
        """Test pick_finding against a real SQLite database."""
        db_file = tmp_path / "app.db"
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("CREATE TABLE sessions (id VARCHAR PRIMARY KEY, name VARCHAR)")
        cur.execute("CREATE TABLE chat_messages (id VARCHAR PRIMARY KEY, session_id VARCHAR, role VARCHAR, content TEXT)")
        cur.execute("INSERT INTO sessions VALUES ('s1', 'bg-test-miner')")
        cur.execute("INSERT INTO sessions VALUES ('s2', 'bg-implementer')")
        cur.execute("INSERT INTO chat_messages VALUES ('msg1', 's1', 'user', 'q')")
        cur.execute("INSERT INTO chat_messages VALUES ('msg2', 's1', 'assistant', 'important finding')")
        cur.execute("INSERT INTO chat_messages VALUES ('msg3', 's2', 'assistant', 'ignored')")
        conn.commit()
        conn.close()

        with patch("src.bg_implementer.Path") as mock_path_cls:
            mock_path_cls.return_value = db_file
            with patch("src.bg_implementer.load_implementer_state", return_value={"processed": []}):
                result = pick_finding()
                assert result is not None
                assert result[0] == "msg2"
                assert result[1] == "bg-test-miner"
                assert result[2] == "important finding"
