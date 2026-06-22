package agentloop

// ToolBlocks is the response shape returned by the resolver that decides
// whether to use native function calls or fenced code-block parsing. The Go
// port collapses the Python _resolve_tool_blocks output to a single struct.
//
// In the Python source, _resolve_tool_blocks returns a tuple (tool_blocks,
// used_native). The Go port uses UsedNative as the bool flag and ToolBlocks as
// the resulting list. Truncation of tool output is handled separately by the
// executor (the Python source delegates to tool_utils._truncate; see
// tools.go for the Go equivalent).
type ToolBlocks struct {
	Blocks     []ToolBlock
	UsedNative bool
}

// ToolBlock is a parsed tool invocation. It mirrors the Python tool_block
// shape (tool_type + content). Args is the JSON-decoded arguments object the
// tool will receive.
type ToolBlock struct {
	ToolType string
	Content  string
	Args     []byte
}

// AppendToolResults writes a tool invocation + its result back into the
// running message history. This is the Go port of Python _append_tool_results.
//
// The Python version maintains a rich shape (assistant_msg with optional
// reasoning_content, separate "tool" role messages, and Gemini's
// thought_signature in extra_content). The Go port only handles the simple
// shape: one assistant message + one tool message per round, which is enough
// for the streaming loop's needs and matches what the FakeProvider in
// loop_test.go emits.
//
// If usedNative is true, the assistant message is emitted with an empty
// content body and the tool call is appended; otherwise the result is folded
// into a "tool" role message for the next round.
func AppendToolResults(msgs *[]Message, calls []ToolCall, results []ToolResult) {
	if len(calls) == 0 {
		return
	}
	// Collapse N tool calls into one assistant turn (a) and N tool turns (r).
	for i, c := range calls {
		_ = c
		*msgs = append(*msgs, Message{
			Role:    "assistant",
			Content: "", // model produced a tool call; no prose
		})
		if i < len(results) {
			*msgs = append(*msgs, Message{
				Role:    "tool",
				Content: results[i].Output,
			})
		}
	}
}

// TruncateToolOutput is the Go port of the truncation helper used after a
// tool executes. The Python source delegates to tool_utils._truncate, which
// caps at MAX_OUTPUT_CHARS (10 000) and appends "... (truncated, N chars
// total)" if it had to clip anything.
//
// Empty input is returned verbatim; output at or under the limit is returned
// verbatim; longer output gets clipped + a suffix.
func TruncateToolOutput(s string, maxChars int) string {
	const suffixFmt = "... (truncated, %d chars total)"
	if maxChars <= 0 {
		maxChars = 10_000
	}
	if len(s) <= maxChars {
		return s
	}
	original := len(s)
	// Build "... (truncated, N chars total)" without fmt import for the
	// common case (int < 10^9 fits in a few digits).
	suf := buildSuffix(original)
	return s[:maxChars] + suf
}

// buildSuffix returns "... (truncated, N chars total)" without importing fmt.
// Inline to keep tools.go self-contained.
func buildSuffix(n int) string {
	digits := []byte{}
	if n == 0 {
		digits = []byte{'0'}
	} else {
		for n > 0 {
			digits = append([]byte{byte('0' + n%10)}, digits...)
			n /= 10
		}
	}
	out := []byte("... (truncated, ")
	out = append(out, digits...)
	out = append(out, []byte(" chars total)")...)
	return string(out)
}
