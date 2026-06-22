# stt

A Go port of `services/stt/stt_service.py`: a multi-provider Speech-to-Text service.

## What it does

Transcribes audio bytes to text using one of three backends:

- **local** — runs [whisper.cpp](https://github.com/ggerganov/whisper.cpp) via its Go bindings (CPU/GPU, no Python dependency)
- **endpoint** — OpenAI-compatible `/audio/transcriptions` API (any provider serving the Whisper API shape)
- **browser** — client-side Web Speech API (no server transcription; the Go service returns a no-op)

The service reads provider configuration from `data/settings.json` on each call, so settings can be hot-reloaded without restarting the server.

## Layout

```
go-src/stt/
├── go.mod
├── README.md
├── cmd/stt/main.go              # demo CLI: transcribe a .webm file
└── pkg/stt/
    ├── service.go               # STTService — multi-provider dispatch
    └── service_test.go          # unit tests for each provider path
```

## Public surface

```go
type STTService struct { /* ... */ }
func New() *STTService

func (s *STTService) Available() bool
func (s *STTService) Transcribe(ctx context.Context, audio []byte) (string, error)
func (s *STTService) Stats() Stats

type Stats struct {
    Available    bool   `json:"available"`
    Provider     string `json:"provider"`
    Model        string `json:"model"`
    Language     string `json:"language"`
    ModelLoaded  bool   `json:"model_loaded,omitempty"`
    EndpointID   string `json:"endpoint_id,omitempty"`
}
```

## Port notes

- **Settings**: reads `data/settings.json` from the working directory on every call (same as Python). No caching — hot-reload friendly.
- **Local Whisper**: uses `whisper.cpp` Go bindings. The model file is downloaded on first use via the bindings' built-in downloader. Model sizes match the Python `faster-whisper` naming (`base`, `small`, `medium`, `large-v3`).
- **API endpoint**: plain HTTP POST with `multipart/form-data` — no SDK dependency. Reads endpoint config (base URL + API key) from the database via the same `ModelEndpoint` table.
- **Browser**: `Available()` returns `true` but `Transcribe()` returns `("", nil)` — transcription happens client-side.
- **Singleton**: `GetSTTService()` provides a module-level singleton matching the Python `get_stt_service()` pattern.

## Test approach

Tests use a mock settings file and a mock HTTP server to exercise each provider path without real audio or network dependencies. The local-whisper path is tested with a stub that simulates the whisper.cpp bindings interface.

Run:

```
go build ./...
go test -race ./...
```