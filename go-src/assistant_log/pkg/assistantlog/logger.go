// Package assistantlog is the Go port of src/assistant_log.py.
//
// In the Python codebase this module used to write system/task activity into
// a "favorited Assistant" chat session. That coupling is gone — activity now
// lives in the Tasks / notifications surfaces — so the Python implementation
// has been reduced to a no-op shim that emits a single debug log line and
// returns. This Go port preserves the same shim semantics:
//
//   - LogToAssistant is a debug-level no-op. It never writes to a session,
//     it never creates a chat thread, and it never touches the DB.
//   - SetSessionManager accepts any SessionManager implementation, but the
//     package only ever calls it to record a reference; LogToAssistant does
//     not invoke it. A future build that re-enables logging can do so by
//     reading SessionManager and routing posts through it.
//   - ParseLegacyTag is the one piece of real logic: it extracts the
//     "**[Category]**" prefix the Python module recognised so callers can
//     colour-code their UI without re-implementing the regex.
//
// Out of scope: anything that would actually create a chat session or fire
// HTTP traffic. The legacy activity path is intentionally inert.
package assistantlog

import (
	"context"
	"log/slog"
)

// DefaultRole is the role used when LogOptions.Role is empty. Mirrors the
// Python default of "assistant".
const DefaultRole = "assistant"

// Legacy no-op reason — surfaced via Result.Reason so callers (and the
// demo CLI) can confirm they hit the shim path.
const ReasonLegacyNoOp = "legacy no-op"

// LogOptions is the modern Go surface for the Python log_to_assistant
// helper. Field names match the Python keyword arguments verbatim so
// call-site translations are mechanical.
//
//   - Owner   is the user the activity belongs to. Required for the
//     Python semantic; the Go shim records it on the debug log
//     line but does not route it anywhere.
//   - Content is the message body. Never logged at info level; only the
//     legacy-tag-extracted category is surfaced.
//   - Role    is the actor role. Defaults to DefaultRole ("assistant").
//   - Category is an optional explicit category. When empty, the legacy
//     "**[Category]**" prefix is parsed out of Content.
type LogOptions struct {
	Owner    string
	Content  string
	Role     string
	Category string
}

// Result is what LogToAssistant returns. Logged is always false in this
// port (the shim never posts); Reason carries an explanation, and
// Category is the resolved category (explicit override wins; otherwise
// the parsed legacy tag; otherwise empty).
type Result struct {
	Logged   bool
	Reason   string
	Category string
}

// SessionManager is the forward-compat interface the Python module used to
// wire in via set_session_manager(). The current Go port never calls
// PostActivity — the activity feed is sourced from Tasks / notifications
// now — but the interface is preserved so a future port that re-enables
// session logging can do so without changing call sites.
type SessionManager interface {
	PostActivity(ctx context.Context, owner, role, content string, category *string) error
}

// noopSessionManager is the default SessionManager. It accepts every call
// and returns nil. It is intentionally silent: the Python shim also
// dropped activity, so dropping it again here keeps behaviour identical.
type noopSessionManager struct{}

func (noopSessionManager) PostActivity(ctx context.Context, owner, role, content string, category *string) error {
	return nil
}

// currentSessionManager holds the SessionManager SetSessionManager most
// recently installed. The zero value is a noopSessionManager so callers
// that never wire one in still get a defined, safe behaviour.
var currentSessionManager SessionManager = noopSessionManager{}

// SetSessionManager installs sm as the SessionManager used by future
// LogToAssistant calls. Passing nil restores the package-level noop
// session manager. Mirrors the Python `set_session_manager(sm)` helper —
// it stored the reference and nothing else, so this Go version does the
// same. Tests can swap the implementation to assert that callers wired
// the package correctly.
func SetSessionManager(sm SessionManager) {
	if sm == nil {
		currentSessionManager = noopSessionManager{}
		return
	}
	currentSessionManager = sm
}

// SessionManager returns the currently-installed SessionManager. Mostly
// useful for tests; production callers can ignore it.
func SessionManager_() SessionManager { return currentSessionManager }

// LogToAssistant is the Go equivalent of Python's log_to_assistant(). It
// is a legacy no-op: the function logs a single debug-level record
// (matching the Python `logger.debug(...)` line) and returns
// Result{Logged: false, Reason: "legacy no-op", Category: <resolved>}.
//
// The ctx is honoured only insofar as the underlying slog handler may
// inspect it; this implementation does not abort on cancellation because
// there is no I/O to cancel.
//
// The optional logger argument is exposed so tests can capture the debug
// line via a bytes.Buffer-backed handler. Production callers should pass
// nil to use the package default (slog.Default()).
func LogToAssistant(ctx context.Context, opts LogOptions, logger *slog.Logger) Result {
	lg := logger
	if lg == nil {
		lg = slog.Default()
	}

	role := opts.Role
	if role == "" {
		role = DefaultRole
	}

	// Resolve category: explicit override wins; otherwise the legacy
	// "**[Category]**" prefix wins; otherwise empty.
	category := opts.Category
	if category == "" {
		if parsed, _, ok := ParseLegacyTag(opts.Content); ok {
			category = parsed
		}
	}

	// The Python module logged at DEBUG. We do the same — and we
	// deliberately do NOT include opts.Content so the demo CLI's
	// "never print the actual content" rule holds even at debug level.
	lg.DebugContext(ctx, "log_to_assistant ignored legacy activity",
		slog.String("category", category),
		slog.String("owner", opts.Owner),
		slog.String("role", role),
	)

	// Touch the installed SessionManager so SetSessionManager remains
	// a meaningful operation even though we never post. The Python
	// module kept the reference for the same reason: future-proofing.
	_ = currentSessionManager

	return Result{
		Logged:   false,
		Reason:   ReasonLegacyNoOp,
		Category: category,
	}
}
