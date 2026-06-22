package cookbookserve

import "errors"

// Sentinel errors. Callers use errors.Is to discriminate between failure
// modes without leaking implementation detail.
var (
	// ErrNilLifecycle is returned by Tick / StopTask when the receiver is
	// nil — defensive guard so callers that mistakenly chain methods on a
	// nil Lifecycle get a clear error instead of a panic.
	ErrNilLifecycle = errors.New("cookbookserve: nil lifecycle")
	// ErrNilClient is returned when Lifecycle.Client is unset.
	ErrNilClient = errors.New("cookbookserve: nil client")
	// ErrMissingSessionID is returned by StopTask when the supplied task
	// has neither SessionID nor ID.
	ErrMissingSessionID = errors.New("cookbookserve: task has no session id")
	// ErrKillFailed is returned when the tmux kill returned a non-success
	// exit code without a recognised "already gone" stderr marker.
	ErrKillFailed = errors.New("cookbookserve: tmux kill returned non-success and no recognised 'already gone' marker")
	// ErrEmptyStatePath is returned when ReadStateFile / WriteStateFile
	// receive an empty path.
	ErrEmptyStatePath = errors.New("cookbookserve: empty state file path")
)

// errNilLifecycle is the package-internal alias kept as a single spelling;
// the exported sentinel above is what callers should match against.
var errNilLifecycle = ErrNilLifecycle
