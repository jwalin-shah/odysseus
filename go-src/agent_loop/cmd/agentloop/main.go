// Command agentloop drives a 2-round streaming agent loop with a fake LLM and
// prints events to stdout. It serves as a smoke-test for the agentloop
// package and as a worked example of the public API.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/odysseus/agent_loop/pkg/agentloop"
)

type fakeLLM struct {
	round int
}

func (f *fakeLLM) Generate(ctx context.Context, req agentloop.ProviderRequest) (<-chan string, <-chan []agentloop.ToolCall, <-chan error) {
	deltas := make(chan string, 16)
	calls := make(chan []agentloop.ToolCall, 1)
	errs := make(chan error, 1)
	go func() {
		defer close(deltas)
		defer close(calls)
		defer close(errs)
		switch f.round {
		case 0:
			f.round++
			deltas <- "Thinking... "
			deltas <- "I'll check the calendar. "
			calls <- []agentloop.ToolCall{{
				ID:   "call_1",
				Name: "bash",
				Args: json.RawMessage(`{"cmd":"date"}`),
			}}
		case 1:
			f.round++
			deltas <- "It is "
			deltas <- "now."
		}
	}()
	return deltas, calls, errs
}

type echoTool struct{}

func (e *echoTool) Name() string { return "bash" }
func (e *echoTool) Execute(ctx context.Context, c agentloop.ToolCall) (agentloop.ToolResult, error) {
	return agentloop.ToolResult{ID: c.ID, Output: "ok"}, nil
}

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	events, errs := agentloop.Stream(ctx, agentloop.Request{
		SessionID: "demo",
		Messages:  []agentloop.Message{{Role: "user", Content: "what time is it?"}},
		Config: agentloop.Config{
			Model:     "fake-model",
			Provider:  &fakeLLM{},
			Tools:     []agentloop.Tool{&echoTool{}},
			MaxRounds: 2,
			Timeout:   5 * time.Second,
		},
	})

	for ev := range events {
		switch e := ev.(type) {
		case agentloop.TextChunk:
			fmt.Print(e.Delta)
		case agentloop.ToolCall:
			fmt.Printf("\n[tool_call] %s %s\n", e.Name, string(e.Args))
		case agentloop.ToolResult:
			fmt.Printf("[tool_result] %s\n", e.Output)
		case agentloop.Final:
			fmt.Printf("\n[final] rounds=%d tools=%d output_tokens=%d cancelled=%v\n",
				e.Metrics.Rounds, e.Metrics.ToolCalls, e.Metrics.OutputTokens, e.Metrics.Cancelled)
		}
	}
	for e := range errs {
		if e != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", e)
			os.Exit(1)
		}
	}
}
