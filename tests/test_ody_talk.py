import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "ody_talk.py"
SPEC = importlib.util.spec_from_file_location("ody_talk", MODULE_PATH)
ody_talk = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ody_talk)


def test_help_does_not_open_session(monkeypatch, capsys):
    monkeypatch.setattr(
        ody_talk,
        "get_session",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("network called")),
    )

    assert ody_talk.main(["--help"]) == 0
    assert "Usage:" in capsys.readouterr().out


def test_connection_error_is_actionable(monkeypatch, capsys):
    def fail_session(**kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(ody_talk, "get_session", fail_session)

    assert ody_talk.main(["hello"]) == 1
    error = capsys.readouterr().err
    assert "cannot reach Odysseus" in error
    assert "ody status" in error
