"""Unit tests for src/odysseus.py: router classification, tool picking, feedback."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import odysseus


def test_classify_code_missions():
    for m in ["fix the bug in sys_quota.py", "implement the waterfall",
              "rewrite sys_map cleanly", "make the test pass", "broken import"]:
        assert odysseus.classify(m) == "code", m


def test_classify_analyze_missions():
    for m in ["review the v2 router for security", "summarize tonight's reports",
              "diagnose the flaky quota test", "why does WAL deadlock here"]:
        assert odysseus.classify(m) == "analyze", m


def test_classify_research_missions():
    assert odysseus.classify("find arxiv papers on agent routing") == "research"


def test_code_beats_analyze_on_overlap():
    # "review ... and fix" implies a write -> code lane
    assert odysseus.classify("review and fix the failing test") == "code"


def test_m3_is_never_in_the_code_waterfall():
    assert "opencode-m3" not in odysseus.CODE_WATERFALL
    for tool in odysseus.CODE_WATERFALL:
        assert odysseus.REGISTRY[tool]["kind"] == "coder"


def test_pick_skips_missing_clis(monkeypatch):
    monkeypatch.setattr(odysseus, "cli_exists", lambda t: t == "codex")
    monkeypatch.setattr(odysseus, "quota_ok", lambda t: True)
    assert odysseus.pick(odysseus.CODE_WATERFALL) == "codex"


def test_pick_skips_exhausted_quota(monkeypatch):
    monkeypatch.setattr(odysseus, "cli_exists", lambda t: True)
    monkeypatch.setattr(odysseus, "quota_ok", lambda t: t != "claude")
    assert odysseus.pick(odysseus.CODE_WATERFALL) == "opencode-opus"


def test_pick_returns_none_when_nothing_viable(monkeypatch):
    monkeypatch.setattr(odysseus, "cli_exists", lambda t: False)
    assert odysseus.pick(odysseus.CODE_WATERFALL) is None


def test_feedback_record_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(odysseus, "FEEDBACK_DIR", str(tmp_path))
    path = odysseus.write_feedback({"prompt": "x", "agent_used": "claude",
                                    "test_passed": True})
    rec = json.loads(open(path).read())
    assert rec["agent_used"] == "claude" and rec["test_passed"] is True


def test_docs_preamble_respects_total_cap():
    docs = odysseus.load_docs()
    assert len(docs) <= odysseus.DOCS_TOTAL_CAP + len(odysseus.DOCS) * 50


def test_route_keyword_fallback_env(monkeypatch):
    monkeypatch.setenv("ODY_ROUTER", "keyword")
    assert odysseus.route("fix the bug") == ("code", "keyword")


def test_hybrid_patch_splices_function(tmp_path, monkeypatch):
    import m3
    f = tmp_path / "calc.py"
    f.write_text("def add(a, b):\n    return a - b\n\nX = 1\n")
    monkeypatch.setattr(m3, "complete",
                        lambda *a, **k: "def add(a, b):\n    return a + b\n")
    rc, out, err = odysseus.hybrid_patch(str(tmp_path), "calc.py:add", "fix add")
    assert rc == 0, err
    assert "return a + b" in f.read_text() and "X = 1" in f.read_text()


def test_hybrid_patch_rejects_wrong_function(tmp_path, monkeypatch):
    import m3
    f = tmp_path / "calc.py"
    f.write_text("def add(a, b):\n    return a - b\n")
    monkeypatch.setattr(m3, "complete",
                        lambda *a, **k: "def sub(a, b):\n    return a - b\n")
    rc, _, err = odysseus.hybrid_patch(str(tmp_path), "calc.py:add", "fix")
    assert rc == 1 and "did not return" in err
    assert "a - b" in f.read_text()
