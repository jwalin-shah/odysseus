package agentloop

import (
	"testing"
	"time"
)

func TestComputeFinalMetrics_AggregatesTokensAndTools(t *testing.T) {
	t.Parallel()
	events := []Event{
		TextChunk{Delta: "hello world"}, // 2 tokens (rough)
		TextChunk{Delta: "another"},     // 1 token
		ToolCall{Name: "bash"},
		ToolCall{Name: "bash"},
		Final{Metrics: Metrics{Rounds: 2, Model: "test-model"}},
	}
	got := ComputeFinalMetrics(events, 1*time.Second)
	if got.ToolCalls != 2 {
		t.Errorf("ToolCalls = %d, want 2", got.ToolCalls)
	}
	if got.OutputTokens == 0 {
		t.Errorf("OutputTokens = 0, want > 0")
	}
	if got.Rounds != 2 {
		t.Errorf("Rounds = %d, want 2", got.Rounds)
	}
	if got.Model != "test-model" {
		t.Errorf("Model = %q, want test-model", got.Model)
	}
}
