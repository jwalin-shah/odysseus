import os
import tempfile
from services.stt.stt_service import STTService


def _settings(provider, model="tiny", enabled=True):
    return {
        "stt_enabled": enabled,
        "stt_provider": provider,
        "stt_model": model,
        "stt_language": "",
    }


# ── local-moonshine (ONNX CPU) ──

def test_moonshine_transcribe_no_leak_on_error():
    """A failing Moonshine transcription must not leak temp .webm files."""
    service = STTService()

    class MockModel:
        def generate(self, *args, **kwargs):
            raise ValueError("Simulated moonshine error")

    service._get_moonshine = lambda: MockModel()
    service._moonshine_tokenizer = object()  # never reached

    temp_dir = tempfile.gettempdir()
    before = {f for f in os.listdir(temp_dir) if f.endswith(".webm")}

    result = service._transcribe_moonshine(b"dummy_audio_data")

    after = {f for f in os.listdir(temp_dir) if f.endswith(".webm")}

    assert result is None
    assert not (after - before), f"Leaked files: {after - before}"


def test_moonshine_unavailable_returns_none():
    """When the model can't load, transcription returns None (no crash)."""
    service = STTService()
    service._get_moonshine = lambda: None
    assert service._transcribe_moonshine(b"dummy") is None


def test_moonshine_dispatch_routes_to_moonshine(monkeypatch):
    """transcribe() must route the local-moonshine provider to the right backend."""
    service = STTService()
    monkeypatch.setattr(service, "_load_settings", lambda: _settings("local-moonshine"))

    called = {}

    def fake(audio, lang=""):
        called["hit"] = (audio, lang)
        return "ok"

    service._transcribe_moonshine = fake

    out = service.transcribe(b"abc")
    assert out == "ok"
    assert called["hit"][0] == b"abc"


def test_moonshine_disabled_returns_none(monkeypatch):
    service = STTService()
    monkeypatch.setattr(
        service, "_load_settings", lambda: _settings("local-moonshine", enabled=False)
    )
    assert service.transcribe(b"abc") is None


# ── local-moonshine-coreml (CoreML ANE) ──

def test_moonshine_coreml_unavailable_returns_none():
    """Missing .mlpackage / coremltools degrades gracefully to None."""
    service = STTService()
    service._get_moonshine_coreml = lambda: None
    assert service._transcribe_moonshine_coreml(b"dummy") is None


def test_moonshine_coreml_dispatch(monkeypatch):
    service = STTService()
    monkeypatch.setattr(
        service, "_load_settings", lambda: _settings("local-moonshine-coreml")
    )
    called = {}

    def fake(audio, lang=""):
        called["hit"] = True
        return "coreml-ok"

    service._transcribe_moonshine_coreml = fake
    assert service.transcribe(b"xyz") == "coreml-ok"
    assert called["hit"]


def test_stats_report_moonshine_backend(monkeypatch):
    """get_stats reflects the active provider without requiring a loaded model."""
    service = STTService()
    monkeypatch.setattr(service, "_load_settings", lambda: _settings("local-moonshine"))
    service._get_moonshine = lambda: None  # not loaded yet
    stats = service.get_stats()
    assert stats["provider"] == "local-moonshine"
