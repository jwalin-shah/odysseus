package contextcompactor

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
)

func TestContentAsText(t *testing.T) {
	tests := []struct {
		name string
		in   any
		want string
	}{
		{"plain string", "hello world", "hello world"},
		{"list of text blocks", []map[string]any{
			{"type": "text", "text": "first"},
			{"type": "text", "text": "second"},
		}, "first second"},
		{"list of []any blocks", []any{
			map[string]any{"type": "text", "text": "alpha"},
			map[string]any{"type": "image", "image_url": "x"},
			map[string]any{"type": "text", "text": "beta"},
		}, "alpha beta"},
		{"nil", nil, ""},
		{"empty list", []map[string]any{}, ""},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := ContentAsText(tc.in)
			if got != tc.want {
				t.Errorf("ContentAsText(%v) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}
}

func TestSanitizeToolMessages(t *testing.T) {
	tests := []struct {
		name string
		in   []Message
		want []Message
	}{
		{
			name: "orphan tool message dropped",
			in: []Message{
				{"role": "user", "content": "hello"},
				{"role": "tool", "content": "result", "tool_call_id": "abc"},
				{"role": "assistant", "content": "hi"},
			},
			want: []Message{
				{"role": "user", "content": "hello"},
				{"role": "assistant", "content": "hi"},
			},
		},
		{
			name: "tool messages kept after assistant tool_calls",
			in: []Message{
				{"role": "assistant", "tool_calls": []any{map[string]any{"id": "1"}}},
				{"role": "tool", "content": "result", "tool_call_id": "1"},
			},
			want: []Message{
				{"role": "assistant", "tool_calls": []any{map[string]any{"id": "1"}}},
				{"role": "tool", "content": "result", "tool_call_id": "1"},
			},
		},
		{
			name: "dangling assistant tool_calls stripped",
			in: []Message{
				{"role": "assistant", "content": "thinking", "tool_calls": []any{map[string]any{"id": "1"}}},
				{"role": "user", "content": "next"},
			},
			want: []Message{
				{"role": "assistant", "content": "thinking"},
				{"role": "user", "content": "next"},
			},
		},
		{
			name: "dangling tool_calls with text content keeps text",
			in: []Message{
				{"role": "assistant", "content": "reasoning text", "tool_calls": []any{map[string]any{"id": "1"}}},
				{"role": "user", "content": "next"},
			},
			want: []Message{
				{"role": "assistant", "content": "reasoning text"},
				{"role": "user", "content": "next"},
			},
		},
		{
			name: "normal flow untouched",
			in: []Message{
				{"role": "user", "content": "hi"},
				{"role": "assistant", "content": "hello"},
			},
			want: []Message{
				{"role": "user", "content": "hi"},
				{"role": "assistant", "content": "hello"},
			},
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := SanitizeToolMessages(tc.in)
			if len(got) != len(tc.want) {
				t.Fatalf("len(got)=%d, want %d (got=%v)", len(got), len(tc.want), got)
			}
			for i := range got {
				if got[i]["role"] != tc.want[i]["role"] || got[i]["content"] != tc.want[i]["content"] {
					t.Errorf("idx %d: got %v, want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}

func TestMessageTextTokenEstimate(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want int
	}{
		{"empty", "", 4},
		{"short", "hi", 4}, // int(len("hi")*0.3) + 4 = int(0.6) + 4 = 0 + 4
		{"zero length floor", "", 4},
		{"long", strings.Repeat("a", 100), int(float64(100)*0.3) + 4},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := MessageTextTokenEstimate(tc.in)
			if got != tc.want {
				t.Errorf("MessageTextTokenEstimate(%q) = %d, want %d", tc.in, got, tc.want)
			}
		})
	}
}

func TestTruncateTextToTokenBudget(t *testing.T) {
	tests := []struct {
		name      string
		text      string
		budget    int
		wantHead  string // string that should be in the head of the result
		wantTail  string // string that should be in the tail of the result
		wantExact string // exact match if set
	}{
		{
			name:      "tiny budget returns omission",
			text:      strings.Repeat("a", 5000),
			budget:    16,
			wantExact: "[Current user message omitted: it exceeded the model context window.]",
		},
		{
			name:     "head and tail notice appended when too large",
			text:     strings.Repeat("a", 5000),
			budget:   500,
			wantHead: strings.Repeat("a", 50),
			wantTail: "a",
		},
		{
			name:      "exactly fits",
			text:      "short",
			budget:    500,
			wantExact: "short",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := TruncateTextToTokenBudget(tc.text, tc.budget)
			if tc.wantExact != "" {
				if got != tc.wantExact {
					t.Errorf("got %q, want exact %q", got, tc.wantExact)
				}
				return
			}
			if tc.wantHead != "" && !strings.Contains(got, tc.wantHead[:50]) {
				t.Errorf("missing head %q in %q", tc.wantHead[:50], got)
			}
			if tc.wantTail != "" && !strings.HasSuffix(got, tc.wantTail) {
				t.Errorf("missing tail %q in %q", tc.wantTail, got)
			}
			if !strings.Contains(got, "[Notice:") {
				t.Errorf("expected notice in result, got %q", got)
			}
		})
	}
}

func TestTruncateToolCallArgs(t *testing.T) {
	hugeArgs, _ := json.Marshal(map[string]any{"data": strings.Repeat("x", 5000)})
	smallArgs, _ := json.Marshal(map[string]any{"data": "tiny"})

	tests := []struct {
		name    string
		msg     Message
		budget  int
		changed bool
	}{
		{
			name: "oversized tool_call replaced",
			msg: Message{
				"role": "assistant",
				"tool_calls": []any{
					map[string]any{
						"id":   "1",
						"type": "function",
						"function": map[string]any{
							"name":      "create_document",
							"arguments": string(hugeArgs),
						},
					},
				},
			},
			budget:  200,
			changed: true,
		},
		{
			name: "small tool_call untouched",
			msg: Message{
				"role": "assistant",
				"tool_calls": []any{
					map[string]any{
						"id":   "1",
						"type": "function",
						"function": map[string]any{
							"name":      "noop",
							"arguments": string(smallArgs),
						},
					},
				},
			},
			budget:  5000,
			changed: false,
		},
		{
			name: "no tool_calls unchanged",
			msg: Message{
				"role":    "assistant",
				"content": "hello",
			},
			budget:  100,
			changed: false,
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := TruncateToolCallArgs(tc.msg, tc.budget)
			if !tc.changed {
				if len(got) != len(tc.msg) {
					t.Errorf("expected unchanged msg, got %v", got)
				}
				return
			}
			calls, ok := got["tool_calls"].([]any)
			if !ok || len(calls) == 0 {
				t.Fatalf("missing tool_calls in %v", got)
			}
			fn, _ := calls[0].(map[string]any)["function"].(map[string]any)
			if !strings.Contains(fn["arguments"].(string), "_truncated_for_context") {
				t.Errorf("expected truncated placeholder, got %q", fn["arguments"])
			}
		})
	}
}

func TestTruncateMessageToTokenBudget(t *testing.T) {
	tests := []struct {
		name   string
		msg    Message
		budget int
		check  func(t *testing.T, got Message)
	}{
		{
			name: "string content truncated",
			msg: Message{
				"role":    "user",
				"content": strings.Repeat("z", 5000),
			},
			budget: 200,
			check: func(t *testing.T, got Message) {
				s, _ := got["content"].(string)
				if !strings.Contains(s, "[Notice:") {
					t.Errorf("expected notice, got %q", s)
				}
			},
		},
		{
			name: "list content truncated per block",
			msg: Message{
				"role": "user",
				"content": []any{
					map[string]any{"type": "text", "text": strings.Repeat("a", 4000)},
					map[string]any{"type": "image", "image_url": "x"},
				},
			},
			budget: 200,
			check: func(t *testing.T, got Message) {
				list, _ := got["content"].([]any)
				if len(list) != 2 {
					t.Fatalf("expected 2 blocks, got %d", len(list))
				}
				first, _ := list[0].(map[string]any)
				if !strings.Contains(first["text"].(string), "[Notice:") {
					t.Errorf("expected notice in first text block, got %q", first["text"])
				}
			},
		},
		{
			name: "tool-only turn truncated via tool_calls",
			msg: Message{
				"role": "assistant",
				"tool_calls": []any{
					map[string]any{
						"id":   "1",
						"type": "function",
						"function": map[string]any{
							"name":      "create_document",
							"arguments": strings.Repeat("x", 5000),
						},
					},
				},
			},
			budget: 100,
			check: func(t *testing.T, got Message) {
				calls, _ := got["tool_calls"].([]any)
				fn, _ := calls[0].(map[string]any)["function"].(map[string]any)
				if !strings.Contains(fn["arguments"].(string), "_truncated_for_context") {
					t.Errorf("expected truncated placeholder, got %q", fn["arguments"])
				}
			},
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := TruncateMessageToTokenBudget(tc.msg, tc.budget)
			tc.check(t, got)
		})
	}
}

func TestTrimForContext(t *testing.T) {
	// Fixed estimate: 1 token per 3 chars + 4 overhead, scaled down for test
	// budgets. We don't actually need accuracy — only that under-budget is
	// "small" and over-budget is "large".
	estimate := func(msgs []Message) int {
		total := 0
		for _, m := range msgs {
			total += MessageTextTokenEstimate(ContentAsText(m["content"]))
		}
		return total
	}

	t.Run("no-op under budget", func(t *testing.T) {
		msgs := []Message{
			{"role": "system", "content": "you are helpful"},
			{"role": "user", "content": "hi"},
		}
		got := TrimForContext(msgs, 10000, 100, estimate)
		if len(got) != len(msgs) {
			t.Errorf("expected no-op, got %d messages", len(got))
		}
	})

	t.Run("drops extra system messages, keeps preset", func(t *testing.T) {
		msgs := []Message{
			{"role": "system", "content": "preset"},
			{"role": "system", "content": strings.Repeat("rag ", 2000)},
			{"role": "system", "content": strings.Repeat("memo ", 2000)},
			{"role": "user", "content": "hi"},
		}
		got := TrimForContext(msgs, 1000, 100, estimate)
		// Should keep preset + user; drop extras if budget fits.
		hasPreset := false
		for _, m := range got {
			if m["content"] == "preset" {
				hasPreset = true
			}
		}
		if !hasPreset {
			t.Errorf("preset system message dropped: %v", got)
		}
	})

	t.Run("research primer is preserved", func(t *testing.T) {
		primerContent := "RESEARCH_PRIMER_" + strings.Repeat("x", 5000)
		msgs := []Message{
			{"role": "system", "content": "preset"},
			{"role": "system", "content": primerContent, "metadata": map[string]any{"research_spinoff_from": "abc"}},
			{"role": "system", "content": strings.Repeat("rag ", 5000)},
			{"role": "user", "content": "hi"},
		}
		got := TrimForContext(msgs, 5000, 100, estimate)
		hasPrimer := false
		for _, m := range got {
			if m["content"] == primerContent {
				hasPrimer = true
			}
		}
		if !hasPrimer {
			t.Errorf("research primer dropped: %v", got)
		}
	})

	t.Run("drops oldest turns but keeps current user turn", func(t *testing.T) {
		var msgs []Message
		msgs = append(msgs, Message{"role": "system", "content": "preset"})
		for i := 0; i < 20; i++ {
			msgs = append(msgs, Message{"role": "user", "content": strings.Repeat("old ", 200)})
			msgs = append(msgs, Message{"role": "assistant", "content": strings.Repeat("ack ", 200)})
		}
		msgs = append(msgs, Message{"role": "user", "content": "current question"})

		got := TrimForContext(msgs, 3000, 200, estimate)
		// Last message must be the current user turn.
		last := got[len(got)-1]
		if last["content"] != "current question" {
			t.Errorf("current user turn lost: last=%v", last)
		}
		if len(got) >= len(msgs) {
			t.Errorf("expected trimming: got=%d, orig=%d", len(got), len(msgs))
		}
	})

	t.Run("truncates oversized current message with notice", func(t *testing.T) {
		hugeCurrent := strings.Repeat("z", 5000)
		msgs := []Message{
			{"role": "system", "content": "preset"},
			{"role": "user", "content": hugeCurrent},
		}
		got := TrimForContext(msgs, 600, 100, estimate)
		last := got[len(got)-1]
		s, _ := last["content"].(string)
		if !strings.Contains(s, "[Notice:") {
			t.Errorf("expected notice in truncated current message, got %q", s)
		}
	})
}

// fakeSession implements SessionLike for MaybeCompact tests.
type fakeSession struct {
	id      string
	history []Message
}

func (f *fakeSession) History() []Message     { return f.history }
func (f *fakeSession) SetHistory(h []Message) { f.history = h }
func (f *fakeSession) ID() string             { return f.id }

type fakeReplacer struct {
	called   bool
	lastID   string
	lastMsgs []Message
	ret      bool
}

func (f *fakeReplacer) ReplaceMessages(id string, msgs []Message) bool {
	f.called = true
	f.lastID = id
	f.lastMsgs = msgs
	return f.ret
}

func TestMaybeCompact(t *testing.T) {
	t.Run("returns false when under threshold", func(t *testing.T) {
		msgs := []Message{
			{"role": "system", "content": "preset"},
			{"role": "user", "content": "hi"},
		}
		estimate := func(m []Message) int { return 100 }
		sess := &fakeSession{id: "abc", history: msgs}
		got, ctxLen, compacted := MaybeCompact(context.Background(), sess, msgs, Deps{
			EstimateTokens: estimate,
		})
		if compacted {
			t.Errorf("expected not compacted")
		}
		if ctxLen == 0 {
			t.Errorf("expected non-zero contextLength")
		}
		if len(got) != len(msgs) {
			t.Errorf("expected unchanged msgs")
		}
	})

	t.Run("compacts when over threshold and updates session", func(t *testing.T) {
		// 8 convo msgs, threshold is 85% of SmallContextLimit (8192),
		// so we just need used > 0.85*8192 ~= 6964 tokens. We force that
		// by using a fake estimate that returns a huge number.
		estimate := func(m []Message) int { return 9000 }
		var sys []Message
		sys = append(sys, Message{"role": "system", "content": "preset"})
		for i := 0; i < 8; i++ {
			sys = append(sys, Message{"role": "user", "content": "msg"})
			sys = append(sys, Message{"role": "assistant", "content": "ack"})
		}
		// convo = 8 messages, split at 4, older = 4 (2 user + 2 assistant).
		llm := func(ctx context.Context, url, model string, messages []Message, opts LLMCallOptions) (string, error) {
			return "FAKE_SUMMARY", nil
		}
		sess := &fakeSession{id: "sess-1", history: sys}
		repl := &fakeReplacer{ret: true}

		got, _, compacted := MaybeCompact(context.Background(), sess, sys, Deps{
			EstimateTokens:  estimate,
			LLMCall:         llm,
			HistoryReplacer: repl,
		})

		if !compacted {
			t.Errorf("expected compacted=true")
		}
		// sys has 1 system + 16 convo. Convo split_point=8 → recent=8. Result
		// = system_msgs (1) + summary (1) + recent (8) = 10.
		const wantLen = 10
		if len(got) != wantLen {
			t.Errorf("expected %d messages post-compact; got %d (orig %d)", wantLen, len(got), len(sys))
		}
		// Summary message should contain the fake summary string.
		var foundSummary bool
		for _, m := range got {
			if s, _ := m["content"].(string); strings.Contains(s, "FAKE_SUMMARY") {
				foundSummary = true
			}
		}
		if !foundSummary {
			t.Errorf("expected FAKE_SUMMARY in result, got %v", got)
		}
		// Replacer should have been called with the session ID.
		if !repl.called || repl.lastID != "sess-1" {
			t.Errorf("expected replacer called with sess-1, got called=%v id=%q", repl.called, repl.lastID)
		}
	})

	t.Run("falls back gracefully on LLM error", func(t *testing.T) {
		estimate := func(m []Message) int { return 9000 }
		var sys []Message
		sys = append(sys, Message{"role": "system", "content": "preset"})
		for i := 0; i < 8; i++ {
			sys = append(sys, Message{"role": "user", "content": "msg"})
			sys = append(sys, Message{"role": "assistant", "content": "ack"})
		}
		llm := func(ctx context.Context, url, model string, messages []Message, opts LLMCallOptions) (string, error) {
			return "", context.DeadlineExceeded
		}
		sess := &fakeSession{id: "sess-2", history: sys}
		got, _, compacted := MaybeCompact(context.Background(), sess, sys, Deps{
			EstimateTokens: estimate,
			LLMCall:        llm,
		})
		if compacted {
			t.Errorf("expected compacted=false on LLM error")
		}
		if len(got) != len(sys) {
			t.Errorf("expected unchanged messages on LLM error, got %d (orig %d)", len(got), len(sys))
		}
	})

	t.Run("returns false when convo has fewer than 4 messages", func(t *testing.T) {
		estimate := func(m []Message) int { return 9000 }
		msgs := []Message{
			{"role": "system", "content": "preset"},
			{"role": "user", "content": "msg1"},
			{"role": "assistant", "content": "msg2"},
		}
		sess := &fakeSession{id: "sess-3", history: msgs}
		_, _, compacted := MaybeCompact(context.Background(), sess, msgs, Deps{
			EstimateTokens: estimate,
			LLMCall: func(ctx context.Context, url, model string, messages []Message, opts LLMCallOptions) (string, error) {
				t.Errorf("LLMCall should not be invoked")
				return "", nil
			},
		})
		if compacted {
			t.Errorf("expected compacted=false with too-few convo msgs")
		}
	})
}
