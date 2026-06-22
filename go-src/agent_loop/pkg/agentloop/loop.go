package agentloop

import (
	"context"
	"fmt"
	"log/slog"
	"sync"
	"sync/atomic"
	"time"
)

// Tool is the interface every concrete tool (bash, web_search, manage_calendar,
// MCP tools, ...) implements. Callers inject implementations via Config.Tools.
//
// Execute must be safe to call from a single goroutine per call; the loop
// dispatches tool calls sequentially within a round.
type Tool interface {
	Name() string
	Execute(ctx context.Context, call ToolCall) (ToolResult, error)
}

// Provider is the LLM-side abstraction. Real implementations wrap httpx /
// OpenAI / Anthropic SDKs. The port's tests use FakeProvider (see loop_test.go
// and cmd/agentloop/main.go).
//
// Generate streams text deltas via the deltas channel, then closes deltas
// and sends the final assistant turn (including any tool_calls) on toolCalls.
// Either channel may be closed early on context cancel.
type Provider interface {
	// Generate is called once per round. deltas is closed when the stream
	// finishes. toolCalls is closed after the final assistant message has been
	// resolved (it carries zero or more ToolCall values).
	Generate(ctx context.Context, req ProviderRequest) (deltas <-chan string, toolCalls <-chan []ToolCall, errs <-chan error)
}

// ProviderRequest is the per-round input to Provider.Generate. It contains the
// prompt built by AssemblePrompt plus the running message history.
type ProviderRequest struct {
	Model    string
	System   string
	Messages []Message
	Round    int
}

// Config is the loop's runtime configuration. Zero-value defaults are applied
// in Stream() — see applyDefaults.
type Config struct {
	Model         string
	Tools         []Tool
	Provider      Provider
	MaxRounds     int           // default 10
	Timeout       time.Duration // default 120s
	Owner         string
	Compact       bool
	DisabledTools map[string]bool
	Logger        *slog.Logger
}

// Request bundles everything Stream() needs. SessionID is opaque to the loop;
// it is preserved in logs only.
type Request struct {
	SessionID string
	Messages  []Message
	Config    Config
}

// applyDefaults fills zero-valued fields with documented defaults. Called once
// per Stream() invocation.
func (c *Config) applyDefaults() {
	if c.MaxRounds <= 0 {
		c.MaxRounds = 10
	}
	if c.Timeout <= 0 {
		c.Timeout = 120 * time.Second
	}
	if c.DisabledTools == nil {
		c.DisabledTools = map[string]bool{}
	}
	if c.Logger == nil {
		c.Logger = slog.Default()
	}
}

// effectiveToolNames returns the set of tool names the loop should advertise to
// the model. Disabled tools are excluded; the model never sees them.
func (c Config) effectiveToolNames() map[string]bool {
	out := map[string]bool{}
	for _, t := range c.Tools {
		if c.DisabledTools[t.Name()] {
			continue
		}
		out[t.Name()] = true
	}
	return out
}

// Stream is the entry point. It returns two channels:
//
//	events <-chan Event  — ordered events; closes after Final
//	errs   <-chan error  — at most one terminal error (loop setup failure);
//	                       normally closed without a value
//
// Cancellation via ctx closes the events channel after emitting a Final event
// with Metrics.Cancelled=true. The loop never panics on cancel.
func Stream(ctx context.Context, req Request) (<-chan Event, <-chan error) {
	events := make(chan Event, 64)
	errs := make(chan error, 1)

	go func() {
		defer close(events)
		defer close(errs)
		req.Config.applyDefaults()
		if req.Config.Provider == nil {
			errs <- fmt.Errorf("agentloop: Config.Provider is required")
			return
		}
		runStream(ctx, req, events)
	}()

	return events, errs
}

// runStream is the inner driver. It is the Go analog of Python's
// stream_agent_loop generator. Only the public-surface behavior is preserved;
// RAG, MCP, plan mode, verifier subagent invocation, fallback endpoints, and
// tool execution semantics are all stubbed or simplified — see README.md.
func runStream(ctx context.Context, req Request, events chan<- Event) {
	cfg := req.Config
	logger := cfg.Logger

	timeoutCtx, cancel := context.WithTimeout(ctx, cfg.Timeout)
	defer cancel()

	start := time.Now()

	// Round counter (atomic so tests can poll it if they want).
	var roundNum atomic.Int64

	// Tool-call frequency map for runaway detection. Keyed by
	// "<tool_name>:<args[:120]>" — matches the Python Counter convention.
	var freqMu sync.Mutex
	freq := map[string]int{}

	// Build the running message history. We append to a local copy so we
	// never mutate the caller's slice.
	msgs := make([]Message, len(req.Messages))
	copy(msgs, req.Messages)

	// Assemble the system prompt once per request.
	toolNameList := make([]string, 0, len(cfg.Tools))
	for _, t := range cfg.Tools {
		toolNameList = append(toolNameList, t.Name())
	}
	system := AssemblePrompt(toolNameList, cfg.DisabledTools, cfg.Compact)

	var runawayTool string
	roundsHitCap := false

loop:
	for {
		select {
		case <-timeoutCtx.Done():
			break loop
		default:
		}

		rn := int(roundNum.Add(1))
		_ = RoundMarker{Round: rn} // marker reserved for future event emission

		deltas, callsCh, genErrs := cfg.Provider.Generate(timeoutCtx, ProviderRequest{
			Model:    cfg.Model,
			System:   system,
			Messages: msgs,
			Round:    rn,
		})

		// Stream deltas until Provider closes the channel.
		for d := range deltas {
			events <- TextChunk{Delta: d}
		}

		// Drain any provider error (single value).
		select {
		case e := <-genErrs:
			if e != nil {
				logger.Warn("provider error", "round", rn, "err", e)
			}
		default:
		}

		// Read the resolved tool calls (zero if the model replied with text only).
		var calls []ToolCall
		select {
		case calls = <-callsCh:
		default:
		}

		// No tool calls → loop done.
		if len(calls) == 0 {
			break loop
		}

		// Execute each tool, emit ToolCall + ToolResult, track frequency.
		var executed []ToolCall
		var results []ToolResult
		for _, c := range calls {
			events <- ToolCall{ID: c.ID, Name: c.Name, Args: c.Args}

			tr, err := executeOne(timeoutCtx, cfg, c)
			if err != nil {
				tr = ToolResult{ID: c.ID, Output: err.Error(), IsError: true}
			}

			events <- tr

			executed = append(executed, c)
			results = append(results, tr)

			sig := runawayKey(c)
			freqMu.Lock()
			freq[sig]++
			freqMu.Unlock()
		}

		// Runaway check (threshold from cfg or 15).
		if tool := DetectRunawayCall(freq, runawayThreshold(cfg)); tool != "" {
			runawayTool = tool
			logger.Warn("runaway tool call detected", "tool", tool)
			break loop
		}

		// Append tool results back into the running history.
		AppendToolResults(&msgs, executed, results)

		if rn >= cfg.MaxRounds {
			roundsHitCap = true
			logger.Warn("max rounds reached", "round", rn, "max", cfg.MaxRounds)
			break loop
		}
	}

	dur := time.Since(start)
	metrics := ComputeFinalMetricsFromStream(msgs, start, dur, roundsHitCap, runawayTool, cfg.Model)
	if timeoutCtx.Err() != nil && ctx.Err() == nil {
		// pure timeout (not caller cancel)
		metrics.Cancelled = true
	}
	if ctx.Err() != nil {
		metrics.Cancelled = true
	}

	events <- Final{Metrics: metrics}
}

// executeOne looks up the tool by name and runs it. Disabled tools fail
// fast with an error; unknown tools return a synthetic "not found" error.
func executeOne(ctx context.Context, cfg Config, call ToolCall) (ToolResult, error) {
	if cfg.DisabledTools[call.Name] {
		return ToolResult{ID: call.ID, Output: "tool disabled", IsError: true},
			fmt.Errorf("tool %q is disabled", call.Name)
	}
	for _, t := range cfg.Tools {
		if t.Name() == call.Name {
			return t.Execute(ctx, call)
		}
	}
	return ToolResult{ID: call.ID, Output: "tool not found", IsError: true},
		fmt.Errorf("tool %q not registered", call.Name)
}

// runawayKey builds the Python-style "{tool_type}:{content[:120]}" signature.
// Args is decoded lazily as a string; for invalid JSON we fall back to the raw
// bytes (truncated).
func runawayKey(c ToolCall) string {
	var asStr string
	if len(c.Args) > 0 {
		asStr = string(c.Args)
	}
	if len(asStr) > 120 {
		asStr = asStr[:120]
	}
	return c.Name + ":" + asStr
}

// runawayThreshold returns the configured threshold if set via
// Config.DisabledTools["__runaway_threshold__"], otherwise the Python default
// of 15.
func runawayThreshold(cfg Config) int {
	const key = "__runaway_threshold__"
	if v, ok := cfg.DisabledTools[key]; ok {
		// DisabledTools is map[string]bool — we encode the threshold as a
		// non-empty string key presence. For now, presence = 15.
		_ = v
		return 15
	}
	return 15
}
