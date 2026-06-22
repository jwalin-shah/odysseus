# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.

## Moonshine STT tests

`tests/test_stt_moonshine.py` has 7 unit tests for Moonshine transcription paths
(moonshine ONNX, moonshine CoreML, moonshine CoreML streaming). Run with:
`python3 -m pytest tests/test_stt_moonshine.py -q`
