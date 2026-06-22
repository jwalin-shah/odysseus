// Package aiinteraction is the Go port of src/ai_interaction.py. The Python
// module wires four agent-facing tools (pipeline, manage_memory, ui_control,
// generate_image) plus a shared model resolver, a session-manager singleton,
// and a dispatcher. The Go port preserves the public behaviour in a
// portable form: HTTP/HTTPS-free parsers and pure dispatch helpers. The
// heavy lifting that depends on a live database, an HTTP client, the
// Chroma vector store, the memory/RAG managers, the session manager, and
// the Flask app is intentionally delegated to injected interfaces so the
// package compiles, tests, and runs without a live backend.
//
// # Scope
//
// This package captures the pure-data behaviour of src/ai_interaction.py:
//
//   - The pipeline parser (JSON or line-format) and the step-validation
//     logic — see ParsePipelineSteps and ValidatePipelineSteps.
//   - The memory manager protocol — list/add/edit/delete/search
//     arguments and the output formatting — see ParseMemoryAction.
//   - The RAG manager protocol — list/add_directory/remove_directory
//     — see ParseRAGAction.
//   - The UI control event generator — toggle, set_mode, switch_model,
//     set_theme, create_theme, highlight, clear_highlight, open_panel,
//     open_email_reply, get_toggles — see ParseUIControlAction.
//   - The image generation request parser (prompt/model/size/quality)
//     and the response-routing rules — see ParseImageRequest.
//   - The model specifier parser ("model" and "model@endpoint") and
//     the dispatch table — see ParseModelSpec and DispatchTool.
//
// # What is delegated to injected interfaces
//
// The Python module talks to a SQL database (ModelEndpoint), an httpx
// client, ChromaDB, an in-process memory manager, a session manager, and
// a gallery row writer. The Go port models those surfaces as small
// interfaces (MemoryStore, MemoryVector, RAGManager, PersonalDocsManager,
// GalleryWriter, SessionManager, ModelEndpointStore, HTTPDoer, LLMRuntime)
// so a caller wires them up once and the package can be driven from
// tests without a live database or HTTP transport.
//
// # Gaps vs. the Python source (called out in README.md)
//
//   - _resolve_model is delegated to EndpointResolver. The Go port
//     provides a default resolver that uses an in-memory endpoint
//     table for tests, but production callers wire this up against
//     the real SQL store.
//   - The LLM HTTP transport is delegated to LLMRuntime. The default
//     returns a placeholder so callers can wire the real client.
//   - The image-generation HTTP transport is delegated to HTTPDoer.
//   - The Chroma vector store is delegated to MemoryVector.
//
// # Constants
//
// AIChatTimeout, MaxDebateRounds, MaxPipelineSteps mirror the module-level
// constants in src/ai_interaction.py.
package aiinteraction
