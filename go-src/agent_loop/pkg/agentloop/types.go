// Package agentloop is the Go port of Odysseus' src/agent_loop.py — the
// streaming multi-round agent loop with tool calls, runaway detection, and
// prompt assembly.
//
// This port covers the PUBLIC SURFACE and the streaming loop signature. The
// full Python module is ~3,190 LOC and is tightly coupled to FastAPI, ChromaDB,
// httpx, MCP, and dozens of helper modules (tool_index, tool_security,
// llm_core, parser, ...). This port replaces those provider-specific bits
// behind the Tool and Provider interfaces; callers inject implementations.
//
// See README.md for the full stub/port inventory.
package agentloop

import "encoding/json"

// Event is the sum type for everything the streaming agent loop emits. Each
// concrete event type carries a private eventTag marker so a switch over the
// concrete type is enough — there is no string discriminator field.
//
// The ordering is: zero or more TextChunk events, optional ToolCall + ToolResult
// pairs per round, optional RoundMarker events between rounds, and exactly one
// Final event before the channel closes. Context cancellation triggers a
// Final event whose Metrics.Cancelled is true.
type Event interface {
	eventTag() string
}

// TextChunk is a streaming text delta. Concatenating every TextChunk.Delta
// produces the assistant's final visible reply.
type TextChunk struct {
	Delta string
}

// RoundMarker is emitted at the start of each new round. Useful for UIs that
// want to render a "thinking..." indicator while tools execute.
type RoundMarker struct {
	Round int
}

// ToolCall is a single function-call invocation produced by the model. Args is
// raw JSON so the caller (and the Tool implementation) can decode it lazily.
type ToolCall struct {
	ID   string
	Name string
	Args json.RawMessage
}

// ToolResult is the outcome of executing one ToolCall. IsError is set when the
// tool returned an error or the call panicked; Output is the JSON-or-text
// payload the tool produced.
type ToolResult struct {
	ID      string
	Output  string
	IsError bool
}

// Final is the terminal event for the loop. It carries aggregate metrics and
// is always emitted before the channel closes (including on context cancel).
type Final struct {
	Metrics Metrics
}

// eventTag returns a stable string per concrete event type. Useful for
// debugging logs only; production code should switch on the concrete type.
func (TextChunk) eventTag() string   { return "text" }
func (RoundMarker) eventTag() string { return "round" }
func (ToolCall) eventTag() string    { return "tool_call" }
func (ToolResult) eventTag() string  { return "tool_result" }
func (Final) eventTag() string       { return "final" }

// Message is a single chat turn in the conversation. Content is plain text;
// for tool invocations the loop emits ToolCall/ToolResult events alongside
// the TextChunk stream. Role is one of "user", "assistant", "system".
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// Metrics summarizes the completed (or cancelled) agent loop. Fields are
// zero-valued when not applicable.
type Metrics struct {
	InputTokens  int     `json:"input_tokens"`
	OutputTokens int     `json:"output_tokens"`
	ToolCalls    int     `json:"tool_calls"`
	Rounds       int     `json:"rounds"`
	DurationMS   int64   `json:"duration_ms"`
	TokensPerSec float64 `json:"tokens_per_second"`
	Cancelled    bool    `json:"cancelled"`
	RoundsHitCap bool    `json:"rounds_hit_cap"`
	RunawayTool  string  `json:"runaway_tool,omitempty"`
	Model        string  `json:"model,omitempty"`
}
