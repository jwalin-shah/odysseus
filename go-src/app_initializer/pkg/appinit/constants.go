// Package appinit provides the public surface of the Python module
// src/app_initializer.py. It is an orchestrator that wires a large graph of
// managers and handlers behind a Config + Registry pair so the wiring can be
// tested without dragging in FastAPI/Chroma/MCP backends.
//
// This file holds path-level constants. They mirror src/constants.py but are
// kept as plain defaults so callers (and tests) can override them via Config.
package appinit

// Default directory names under the application's data root. They map to the
// `.odysseus/...` style subdirectories used by the Python constants module.
// Callers that want a different layout should set the matching field on
// Config rather than depending on these strings.
const (
	// DefaultDataDir is the default base directory for all persisted state.
	DefaultDataDir = ".odysseus/data"

	// DefaultPersonalDir is where the user's personal documents live.
	DefaultPersonalDir = ".odysseus/data/personal_docs"

	// DefaultRunbookDir is where runbook documents live (a subdir of personal).
	DefaultRunbookDir = ".odysseus/data/personal_docs/runbook"

	// DefaultUploadDir is where uploads are staged before processing.
	DefaultUploadDir = ".odysseus/data/uploads"

	// DefaultSessionsFile is the default path of the session ledger.
	DefaultSessionsFile = ".odysseus/data/sessions.json"

	// DefaultAPIKeysFile is where the APIKeyManager backend reads/writes keys.
	DefaultAPIKeysFile = ".odysseus/data/api_keys.json"

	// BraveProvider is the well-known provider name whose key is forwarded to
	// the search-config helper at startup.
	BraveProvider = "brave"
)
