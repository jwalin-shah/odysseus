package agentloop

import (
	"context"
	"encoding/json"
	"testing"
	"time"
)

// fakeProvider is a programmable Provider used by the streaming tests. Each
// round returns the next Script entry; once exhausted, it returns no further
// tool calls, causing the loop to break.
type fakeProvider struct {
	Script []fakeRound
	Round  int
}

type fakeRound struct {
	Deltas []string
	Calls  []ToolCall
	Err    error
}

func (f *fakeProvider) Generate(ctx context.Context, req ProviderRequest) (<-chan string, <-chan []ToolCall, <-chan error) {
	deltas := make(chan string, 16)
	calls := make(chan []ToolCall, 1)
	errs := make(chan error, 1)

	go func() {
		defer close(deltas)
		defer close(calls)
		defer close(errs)

		if f.Round >= len(f.Script) {
			return
		}
		r := f.Script[f.Round]
		f.Round++
		for _, d := range r.Deltas {
			select {
			case deltas <- d:
			case <-ctx.Done():
				return
			}
		}
		select {
		case calls <- r.Calls:
		case <-ctx.Done():
			return
		}
		if r.Err != nil {
			select {
			case errs <- r.Err:
			case <-ctx.Done():
			}
		}
	}()
	return deltas, calls, errs
}

// fakeTool is a minimal Tool used to prove the loop dispatches tool calls.
type fakeTool struct {
	name   string
	output string
	called int
}

func (t *fakeTool) Name() string { return t.name }
func (t *fakeTool) Execute(ctx context.Context, call ToolCall) (ToolResult, error) {
	t.called++
	return ToolResult{ID: call.ID, Output: t.output}, nil
}

// collect drains the events channel into a slice. It returns after the channel
// closes or the deadline elapses.
func collect(t *testing.T, events <-chan Event, errs <-chan error, within time.Duration) []Event {
	t.Helper()
	out := []Event{}
	deadline := time.NewTimer(within)
	defer deadline.Stop()
	for {
		select {
		case ev, ok := <-events:
			if !ok {
				return out
			}
			out = append(out, ev)
		case <-deadline.C:
			t.Fatalf("collect: timed out after %v with %d events", within, len(out))
		}
	}
}

func TestStream_HappyPath_TextOnly(t *testing.T) {
	t.Parallel()
	prov := &fakeProvider{
		Script: []fakeRound{
			{Deltas: []string{"Hello, ", "world!"}, Calls: nil},
		},
	}
	req := Request{
		SessionID: "s1",
		Messages:  []Message{{Role: "user", Content: "hi"}},
		Config: Config{
			Model:    "test-model",
			Provider: prov,
			Timeout:  5 * time.Second,
		},
	}
	events, _ := Stream(context.Background(), req)
	got := collect(t, events, nil, 2*time.Second)

	// Expected order: 2 TextChunks + Final.
	if len(got) < 3 {
		t.Fatalf("want >=3 events, got %d", len(got))
	}
	text := ""
	for _, e := range got[:len(got)-1] {
		if tc, ok := e.(TextChunk); ok {
			text += tc.Delta
		}
	}
	if text != "Hello, world!" {
		t.Fatalf("text concat = %q", text)
	}
	final, ok := got[len(got)-1].(Final)
	if !ok {
		t.Fatalf("last event = %T, want Final", got[len(got)-1])
	}
	if final.Metrics.Cancelled {
		t.Fatal("Metrics.Cancelled should be false on normal finish")
	}
	if final.Metrics.OutputTokens == 0 {
		t.Fatal("Metrics.OutputTokens should be > 0 after streaming text")
	}
}

func TestStream_ToolCallAndResult(t *testing.T) {
	t.Parallel()
	bash := &fakeTool{name: "bash", output: "ok"}

	// Round 1: model emits a bash tool call. Round 2: model emits text only.
	bashCall := ToolCall{
		ID:   "c1",
		Name: "bash",
		Args: json.RawMessage(`{"cmd":"echo hi"}`),
	}
	prov := &fakeProvider{
		Script: []fakeRound{
			{Deltas: []string{""}, Calls: []ToolCall{bashCall}},
			{Deltas: []string{"done."}, Calls: nil},
		},
	}
	req := Request{
		Messages: []Message{{Role: "user", Content: "run a command"}},
		Config: Config{
			Model:    "m",
			Provider: prov,
			Tools:    []Tool{bash},
			Timeout:  5 * time.Second,
		},
	}
	events, _ := Stream(context.Background(), req)
	got := collect(t, events, nil, 2*time.Second)

	// Expect at least: TextChunk("",round1), ToolCall(c1), ToolResult(ok),
	// TextChunk("done.",round2), Final.
	var sawCall, sawResult bool
	for _, e := range got {
		switch v := e.(type) {
		case ToolCall:
			if v.Name == "bash" {
				sawCall = true
			}
		case ToolResult:
			if v.Output == "ok" {
				sawResult = true
			}
		}
	}
	if !sawCall || !sawResult {
		t.Fatalf("missing tool call/result: %+v", got)
	}
	if bash.called != 1 {
		t.Fatalf("bash called %d times, want 1", bash.called)
	}
}

func TestStream_ContextCancel_ClosesWithCancelledMetric(t *testing.T) {
	t.Parallel()
	// Block forever until context cancel — proves cancellation terminates
	// the loop with a Final event whose Metrics.Cancelled is true.
	prov := &fakeProvider{
		Script: []fakeRound{
			{Deltas: nil, Calls: []ToolCall{
				{ID: "c1", Name: "bash", Args: json.RawMessage(`{}`)},
			}},
		},
	}
	bash := &blockingTool{name: "bash"}
	req := Request{
		Messages: []Message{{Role: "user", Content: "test"}},
		Config: Config{
			Model:    "m",
			Provider: prov,
			Tools:    []Tool{bash},
			Timeout:  10 * time.Second,
		},
	}
	ctx, cancel := context.WithCancel(context.Background())
	events, _ := Stream(ctx, req)
	// Give the loop a moment to enter the round 1 tool execution.
	time.Sleep(20 * time.Millisecond)
	cancel()
	got := collect(t, events, nil, 2*time.Second)
	last := got[len(got)-1].(Final)
	if !last.Metrics.Cancelled {
		t.Fatalf("Metrics.Cancelled = false, want true; metrics=%+v", last.Metrics)
	}
}

// blockingTool blocks on context.Done so cancellation can be observed
// mid-tool-execution.
type blockingTool struct{ name string }

func (b *blockingTool) Name() string { return b.name }
func (b *blockingTool) Execute(ctx context.Context, call ToolCall) (ToolResult, error) {
	<-ctx.Done()
	return ToolResult{ID: call.ID, Output: "cancelled"}, ctx.Err()
}

func TestStream_MaxRounds_StopsAtLimit(t *testing.T) {
	t.Parallel()
	// Always emit a tool call → loop should hit MaxRounds cap.
	bash := &fakeTool{name: "bash", output: "ok"}
	prov := &fakeProvider{}
	for i := 0; i < 5; i++ {
		prov.Script = append(prov.Script, fakeRound{
			Deltas: []string{""},
			Calls:  []ToolCall{{ID: "c", Name: "bash", Args: json.RawMessage(`{}`)}},
		})
	}
	req := Request{
		Messages: []Message{{Role: "user", Content: "loop"}},
		Config: Config{
			Model:     "m",
			Provider:  prov,
			Tools:     []Tool{bash},
			MaxRounds: 3,
			Timeout:   5 * time.Second,
		},
	}
	events, _ := Stream(context.Background(), req)
	got := collect(t, events, nil, 2*time.Second)
	last := got[len(got)-1].(Final)
	if !last.Metrics.RoundsHitCap {
		t.Fatalf("RoundsHitCap = false, want true; metrics=%+v", last.Metrics)
	}
	if last.Metrics.Cancelled {
		t.Fatal("Cancelled should be false on normal cap-exit")
	}
}

func TestLoop_RunawayDetected_StopsLoop(t *testing.T) {
	t.Parallel()
	// Force 16 identical bash calls → runaway detection triggers a break
	// with RunawayTool set in the Final metrics.
	bash := &fakeTool{name: "bash", output: "ok"}
	prov := &fakeProvider{}
	for i := 0; i < 20; i++ {
		prov.Script = append(prov.Script, fakeRound{
			Deltas: []string{""},
			Calls:  []ToolCall{{ID: "c", Name: "bash", Args: json.RawMessage(`{"cmd":"ls"}`)}},
		})
	}
	req := Request{
		Messages: []Message{{Role: "user", Content: "loop"}},
		Config: Config{
			Model:     "m",
			Provider:  prov,
			Tools:     []Tool{bash},
			MaxRounds: 100,
			Timeout:   5 * time.Second,
		},
	}
	events, _ := Stream(context.Background(), req)
	got := collect(t, events, nil, 3*time.Second)
	last := got[len(got)-1].(Final)
	if last.Metrics.RunawayTool == "" {
		t.Fatalf("RunawayTool empty; metrics=%+v", last.Metrics)
	}
	if last.Metrics.RunawayTool != "bash" {
		t.Fatalf("RunawayTool = %q, want bash", last.Metrics.RunawayTool)
	}
}
