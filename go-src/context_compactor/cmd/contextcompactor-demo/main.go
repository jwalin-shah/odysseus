// Package main is a small wiring demo for go-src/context_compactor. It loads
// a hard-coded fixture of conversation messages, runs TrimForContext against a
// synthetic context_length, and prints before/after token counts. No network.
package main

import (
	"context"
	"fmt"
	"os"

	contextcompactor "github.com/odysseus/context_compactor/pkg/contextcompactor"
)

func main() {
	messages := []contextcompactor.Message{
		{"role": "system", "content": "You are a helpful assistant named Odysseus."},
		{"role": "system", "content": fmt.Sprintf("RAG snippet: %s", repeat("lorem ipsum dolor sit amet ", 200))},
		{"role": "system", "content": fmt.Sprintf("Memo: %s", repeat("remember this preference ", 200))},
		{"role": "user", "content": "Earlier question about authentication."},
		{"role": "assistant", "content": "Earlier answer about OAuth flows."},
		{"role": "user", "content": "Middle question about caching."},
		{"role": "assistant", "content": "Middle answer about TTL and invalidation."},
		{"role": "user", "content": "Recent question about deployment."},
		{"role": "assistant", "content": "Recent answer about containers and CI."},
		{"role": "user", "content": "Current question: how do I roll back a bad release?"},
	}

	const contextLength = 1200
	const reserveTokens = 100

	estimate := func(msgs []contextcompactor.Message) int {
		total := 0
		for _, m := range msgs {
			total += contextcompactor.MessageTextTokenEstimate(contextcompactor.ContentAsText(m["content"]))
		}
		return total
	}

	before := estimate(messages)
	fmt.Printf("before: %d tokens (%d messages)\n", before, len(messages))

	trimmed := contextcompactor.TrimForContext(messages, contextLength, reserveTokens, estimate)
	after := estimate(trimmed)
	fmt.Printf("after:  %d tokens (%d messages)\n", after, len(trimmed))

	fmt.Println("\n--- post-trim outline ---")
	for i, m := range trimmed {
		role, _ := m["role"].(string)
		content, _ := m["content"].(string)
		if len(content) > 80 {
			content = content[:80] + "..."
		}
		fmt.Printf("[%02d] %-9s %s\n", i, role, content)
	}

	// Optionally exercise MaybeCompact path so the wiring is observable end-to-end.
	sess := &demoSession{id: "demo", history: messages}
	compacted, ctxLen, wasCompacted := contextcompactor.MaybeCompact(context.Background(), sess, messages, contextcompactor.Deps{
		EstimateTokens: estimate,
		EndpointURL:    "https://example.invalid/v1",
		Model:          "demo-model",
	})
	fmt.Printf("\nMaybeCompact: wasCompacted=%v contextLength=%d resultMessages=%d\n", wasCompacted, ctxLen, len(compacted))
	if wasCompacted && len(compacted) > 0 {
		fmt.Println("(would have called LLM at https://example.invalid/v1/demo-model — skipped for offline demo)")
	}

	_ = os.Stdout
}

func repeat(s string, n int) string {
	out := make([]byte, 0, len(s)*n)
	for i := 0; i < n; i++ {
		out = append(out, s...)
	}
	return string(out)
}

type demoSession struct {
	id      string
	history []contextcompactor.Message
}

func (d *demoSession) History() []contextcompactor.Message     { return d.history }
func (d *demoSession) SetHistory(h []contextcompactor.Message) { d.history = h }
func (d *demoSession) ID() string                              { return d.id }
