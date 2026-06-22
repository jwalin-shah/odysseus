package agentloop

import "context"

// VerifierResult is the Go port of the verification outcome produced by the
// Python _run_verifier_subagent. In Python the function returns a list of
// failure reasons ([]string, empty = pass); the Go port collapses that to a
// struct with an OK flag + free-text Notes.
type VerifierResult struct {
	OK    bool     `json:"ok"`
	Notes string   `json:"notes,omitempty"`
	Fail  []string `json:"fail,omitempty"`
}

// RunVerifierSubagent is a STUB. The Python implementation dispatches a fresh
// "verifier" LLM call with NO shared history and asks it to judge whether
// the agent's actions actually satisfy the user's request. Wiring that in
// Go requires an LLM client (httpx / OpenAI SDK) plus prompt construction.
//
// This stub returns a canned OK result after a brief simulated latency, so
// callers depending on a synchronous "did the work satisfy the request?"
// signal can keep flowing. Replace this with a real verifier by implementing
// the Provider interface for the verifier model and reusing RunVerifierSubagent's
// signature.
//
// PORTED-STUB
func RunVerifierSubagent(ctx context.Context, instruction, actionsSnapshot string) VerifierResult {
	// 10ms simulated latency so callers exercising the deadline path don't
	// get a zero-cost "always passes" result.
	select {
	case <-timeAfter(10 * millis):
	case <-ctx.Done():
		return VerifierResult{OK: false, Notes: "verifier cancelled"}
	}
	return VerifierResult{OK: true, Notes: "stub"}
}
