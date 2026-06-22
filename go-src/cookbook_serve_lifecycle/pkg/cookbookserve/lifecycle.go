// Package cookbookserve implements the scheduler-owned cookbook serve
// lifecycle: it periodically reads a state file, finds tasks whose
// _scheduledStopAtMs window has passed, kills the underlying tmux session,
// deletes the auto-registered model endpoint for "serve" tasks, and rewrites
// the state file atomically.
//
// This is the Go port of src/cookbook_serve_lifecycle.py. The package is
// decoupled from any HTTP transport — callers inject a Client implementation
// so tests can run with a fake. The real wiring lives in
// cmd/cookbooklifecycle-demo/main.go and uses net/http over the same internal
// API that the Python module calls via httpx.
package cookbookserve

import (
	"context"
	"io"
	"log"
	"time"
)

// Default tick parameters mirror the Python asyncio loop.
const (
	// DefaultTickInterval is the gap between two successive Tick calls.
	DefaultTickInterval = 60 * time.Second
	// DefaultInitialSleep is the upfront sleep that lets the rest of
	// startup settle before the first tick runs (matches Python's
	// `await asyncio.sleep(20)` at the top of the loop).
	DefaultInitialSleep = 20 * time.Second
)

// Client is the I/O boundary used by Lifecycle. Tests inject a fake; the real
// wiring lives in *HTTPClient.
type Client interface {
	// ListEndpoints returns every registered model endpoint. Used by the
	// endpoint-deletion step to match the auto-registered URL the
	// scheduler-launched serve created.
	ListEndpoints(ctx context.Context) ([]Endpoint, error)
	// DeleteEndpoint drops a registered endpoint by id.
	DeleteEndpoint(ctx context.Context, id string) error
	// ExecCommand runs `command` through the same shell-exec endpoint the
	// cookbook UI uses to kill tmux sessions.
	ExecCommand(ctx context.Context, command string) (ExecResult, error)
}

// Lifecycle is the cookbook serve lifecycle ticker. All I/O boundaries are
// injected so the loop can be exercised without a network or real timers.
type Lifecycle struct {
	// Client is required. NewLifecycle wires a nil-safe default that
	// errors out on first use, so misconfiguration is caught at run time
	// rather than silently no-oping.
	Client Client

	// StateFilePath is the path to the cookbook state JSON. Required.
	StateFilePath string

	// TickInterval controls the gap between two Tick calls. Zero or
	// negative falls back to DefaultTickInterval.
	TickInterval time.Duration

	// InitialSleep is the upfront delay before the first tick. Zero or
	// negative falls back to DefaultInitialSleep.
	InitialSleep time.Duration

	// Logger receives the lifecycle's informational and warning messages.
	// Nil falls back to a discarded logger so callers don't have to wire
	// one in tests.
	Logger *log.Logger

	// NowMs returns the current Unix time in milliseconds. Defaults to
	// time.Now().UnixMilli(); tests override it to drive deterministic
	// "past / future" decisions without sleeping.
	NowMs func() int64
}

// NewLifecycle returns a Lifecycle with sensible defaults wired in. Callers
// still need to set Client and StateFilePath (or override them post-hoc).
func NewLifecycle() *Lifecycle {
	return &Lifecycle{
		TickInterval: DefaultTickInterval,
		InitialSleep: DefaultInitialSleep,
		Logger:       log.New(io.Discard, "", 0),
	}
}

func (l *Lifecycle) logger() *log.Logger {
	if l == nil || l.Logger == nil {
		return log.New(io.Discard, "", 0)
	}
	return l.Logger
}

// effectiveTickInterval returns the validated tick interval, falling back to
// DefaultTickInterval for zero/negative values.
func (l *Lifecycle) effectiveTickInterval() time.Duration {
	if l == nil || l.TickInterval <= 0 {
		return DefaultTickInterval
	}
	return l.TickInterval
}

// effectiveInitialSleep returns the validated initial sleep, falling back to
// DefaultInitialSleep for zero/negative values.
func (l *Lifecycle) effectiveInitialSleep() time.Duration {
	if l == nil || l.InitialSleep <= 0 {
		return DefaultInitialSleep
	}
	return l.InitialSleep
}

func (l *Lifecycle) nowMs() int64 {
	if l != nil && l.NowMs != nil {
		return l.NowMs()
	}
	return time.Now().UnixMilli()
}

// Run drives the forever loop. It sleeps InitialSleep first, then ticks every
// TickInterval until ctx is cancelled or its deadline is hit. Errors from a
// single Tick are logged and the loop continues — only ctx cancellation stops
// it. Returns ctx.Err() when the context ends.
func (l *Lifecycle) Run(ctx context.Context) error {
	if l == nil {
		return errNilLifecycle
	}
	if d := l.effectiveInitialSleep(); d > 0 {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(d):
		}
	}
	ticker := time.NewTicker(l.effectiveTickInterval())
	defer ticker.Stop()
	for {
		if err := l.Tick(ctx); err != nil {
			l.logger().Printf("cookbook_serve_lifecycle tick failed: %v", err)
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
		}
	}
}
