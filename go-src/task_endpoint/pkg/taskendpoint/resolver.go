// Package taskendpoint is the Go port of src/task_endpoint.py. It exposes a
// single Resolver that mirrors Python's resolve_task_endpoint(fallback_url,
// fallback_model, fallback_headers, owner) helper used by background-task
// callers (auto-naming, memory writes, scheduled jobs, etc.).
//
// The Go port keeps the resolution contract identical to the Python source:
//
//   - An explicit endpoint ID (or settings key) is read from a Settings
//     struct (the same role "admin settings" plays in Python).
//   - When that lookup yields a usable endpoint, its URL, model, and
//     headers are returned. Otherwise the supplied fallbacks are used.
//   - A non-nil owner narrows the admin-settings lookup to that owner's
//     rows; when owner is empty the resolver falls back to the global
//     default the same way Python does.
//
// The package deliberately has no external dependencies — it operates only
// on small, in-memory data. Persistence and HTTP transport are the caller's
// responsibility, identical to how src/task_endpoint.py defers to
// src/endpoint_resolver.py for the actual DB and network calls.
package taskendpoint

import "strings"

// Settings mirrors the slice of admin-settings the task resolver reads.
// The zero value behaves as "no admin setting configured" and the resolver
// will use the supplied fallbacks.
//
// EndpointID is the admin-settings key the resolver looks up (the Python
// source reads "task_endpoint_id" / "task_model" from the same row).
// EndpointURL and EndpointModel are pre-resolved values, supplied by the
// caller when the row already carries them. When both EndpointID and the
// pre-resolved fields are empty, the resolver returns the fallback.
type Settings struct {
	// EndpointID identifies the row the admin configured for the "task"
	// role. Empty means "no admin override".
	EndpointID string

	// EndpointURL is the URL associated with EndpointID, when known.
	// Empty when the caller has not pre-resolved the row.
	EndpointURL string

	// EndpointModel is the model id associated with EndpointID, when
	// known. Empty when the caller has not pre-resolved the row.
	EndpointModel string

	// EndpointHeaders are the per-endpoint headers configured for the
	// "task" role (e.g. auth headers). Nil/empty when none are set.
	EndpointHeaders map[string]string
}

// Resolution is the result of Resolve. It mirrors the (endpoint_url,
// model, headers) tuple returned by Python's resolve_task_endpoint.
type Resolution struct {
	URL     string
	Model   string
	Headers map[string]string

	// Source describes where the resolution came from. It is one of
	// "admin" (configured via Settings), "fallback" (caller-supplied),
	// or "empty" (no fallback and no admin setting — caller should
	// treat this as "no endpoint available").
	Source string
}

// Resolve is the Go equivalent of
// resolve_task_endpoint(fallback_url, fallback_model, fallback_headers,
// owner) in src/task_endpoint.py.
//
// When Settings carries a non-empty EndpointURL the resolver returns that
// URL, the configured model (when set) or fallback_model, and a merged
// header map. Otherwise the fallbacks are returned with Source="fallback".
// When neither is configured the result has Source="empty" and the URL /
// model fields are empty strings — callers should treat that as
// "unconfigured" the same way the Python version returns the fallbacks
// literally (which may be None / unset in admin settings).
//
// owner is accepted for parity with the Python signature but is not
// otherwise used by this in-memory port. Persistence-layer callers would
// thread it into the DB query the same way the Python version does.
func Resolve(settings Settings, fallbackURL, fallbackModel string, fallbackHeaders map[string]string, owner string) Resolution {
	_ = owner // accepted for signature parity; persistence callers use it.

	// Admin-configured path. When the caller pre-resolved the admin row
	// we already have a URL; trust it.
	if s := strings.TrimSpace(settings.EndpointURL); s != "" {
		model := strings.TrimSpace(settings.EndpointModel)
		if model == "" {
			model = fallbackModel
		}
		headers := mergeHeaders(settings.EndpointHeaders, fallbackHeaders)
		return Resolution{
			URL:     s,
			Model:   model,
			Headers: headers,
			Source:  "admin",
		}
	}

	// Fallback path. Mirrors Python's "fall back to the provided values
	// when the setting is empty or the endpoint cannot be resolved".
	if strings.TrimSpace(fallbackURL) != "" || strings.TrimSpace(fallbackModel) != "" || len(fallbackHeaders) > 0 {
		return Resolution{
			URL:     fallbackURL,
			Model:   fallbackModel,
			Headers: copyHeaders(fallbackHeaders),
			Source:  "fallback",
		}
	}

	// Nothing configured and nothing supplied — caller decides what to
	// do (typically: log + return an error). The resolver surfaces
	// Source="empty" so the caller can branch without inspecting
	// individual fields.
	return Resolution{Source: "empty"}
}

// mergeHeaders returns a new map containing every entry from primary
// followed by every entry from secondary that does not already appear
// in primary. Pass nil for either argument to treat it as empty. The
// returned map is always non-nil; callers may freely mutate it.
func mergeHeaders(primary, secondary map[string]string) map[string]string {
	out := make(map[string]string, len(primary)+len(secondary))
	for k, v := range primary {
		out[k] = v
	}
	for k, v := range secondary {
		if _, ok := out[k]; !ok {
			out[k] = v
		}
	}
	return out
}

// copyHeaders returns a shallow copy of m, or nil when m is empty/nil.
// Used to ensure callers cannot mutate the fallback map by accident.
func copyHeaders(m map[string]string) map[string]string {
	if len(m) == 0 {
		return nil
	}
	out := make(map[string]string, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}
