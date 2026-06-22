package contextcompactor

import (
	"context"
	"fmt"
	"strings"
)

// LLMCallOptions configures a single LLM call from MaybeCompact.
type LLMCallOptions struct {
	Temperature    float64
	MaxTokens      int
	TimeoutSeconds int
}

// EstimateTokensFn mirrors src.model_context.estimate_tokens — a rough
// chars * 0.3 estimate. Injected so the package stays decoupled from
// src/model_context.py.
type EstimateTokensFn func([]Message) int

// LLMCallFn abstracts the LLM HTTP call. The Python port calls
// src.llm_core.llm_call_async; in Go we inject a function-typed dependency so
// the package has no external deps.
type LLMCallFn func(ctx context.Context, url, model string, messages []Message, opts LLMCallOptions) (string, error)

// ResolveEndpointFn abstracts src.endpoint_resolver.resolve_endpoint. Returns
// (url, model, headers, ok). When ok is false, the caller should fall back to
// the session endpoint.
type ResolveEndpointFn func(purpose, owner string) (url, model string, headers map[string]string, ok bool)

// SessionLike is the minimal surface MaybeCompact needs from a session.
// History() / SetHistory() back the in-memory fallback path; ID() is used by
// HistoryReplacer.
type SessionLike interface {
	History() []Message
	SetHistory([]Message)
	ID() string
}

// HistoryReplacer abstracts the optional persistent storage path. Implementations
// typically delegate to a session manager (see
// core.models.get_session_manager_instance).
type HistoryReplacer interface {
	ReplaceMessages(sessionID string, msgs []Message) bool
}

// Deps bundles the optional injected dependencies for MaybeCompact. Any nil
// field degrades gracefully: nil EstimateTokens falls back to
// defaultEstimateTokens; nil ResolveEndpoint falls back to the supplied
// endpoint/model; nil LLMCallFn makes MaybeCompact a no-op that returns
// wasCompacted=false; nil HistoryReplacer skips the persistence step.
type Deps struct {
	EstimateTokens  EstimateTokensFn
	LLMCall         LLMCallFn
	ResolveEndpoint ResolveEndpointFn
	HistoryReplacer HistoryReplacer
	Owner           string
	EndpointURL     string
	Model           string
	Headers         map[string]string
}

// MaybeCompact checks context usage and compacts the older half of the
// conversation if it crosses CompactThreshold. Returns (messages,
// contextLength, wasCompacted).
//
// Compaction preserves every system message (they're the conversation's
// knowledge base) and prepends a single `[Conversation summary ...]` system
// message in front of the recent half. On any LLM error it degrades
// gracefully and returns the original messages with wasCompacted=false so
// the caller's own trim pass can take over.
func MaybeCompact(
	ctx context.Context,
	session SessionLike,
	messages []Message,
	deps Deps,
) ([]Message, int, bool) {
	estimate := deps.EstimateTokens
	if estimate == nil {
		estimate = defaultEstimateTokens
	}

	contextLength := estimateContextLength(deps.EndpointURL, deps.Model, deps.ResolveEndpoint)
	used := estimate(messages)
	pct := 0.0
	if contextLength > 0 {
		pct = (float64(used) / float64(contextLength)) * 100
	}

	if pct < CompactThreshold*100 {
		return messages, contextLength, false
	}

	// Split into system preface and conversation.
	var systemMsgs []Message
	var convoMsgs []Message
	for _, msg := range messages {
		if role, _ := msg["role"].(string); role == "system" {
			systemMsgs = append(systemMsgs, msg)
		} else {
			convoMsgs = append(convoMsgs, msg)
		}
	}

	if len(convoMsgs) < 4 {
		return messages, contextLength, false
	}

	// Split conversation: summarize older half, keep recent half.
	splitPoint := len(convoMsgs) / 2
	older := convoMsgs[:splitPoint]
	recent := convoMsgs[splitPoint:]

	// Build the text to summarize.
	var convoB strings.Builder
	for _, msg := range older {
		role := "USER"
		if r, ok := msg["role"].(string); ok && r != "" {
			role = strings.ToUpper(r)
		}
		text := ContentAsText(msg["content"])
		if len(text) > 2000 {
			text = text[:2000]
		}
		fmt.Fprintf(&convoB, "%s: %s\n", role, text)
	}

	// Count prior compactions from existing summary messages.
	compactionCount := 0
	for _, m := range systemMsgs {
		if content, _ := m["content"].(string); strings.Contains(content, "[Conversation summary") {
			compactionCount++
		}
	}

	// Use utility model if configured, otherwise fall back to session model.
	compactURL := deps.EndpointURL
	compactModel := deps.Model
	var compactHeaders map[string]string
	if deps.ResolveEndpoint != nil {
		if u, mod, h, ok := deps.ResolveEndpoint("utility", deps.Owner); ok {
			compactURL = u
			compactModel = mod
			compactHeaders = h
		}
	}
	if compactHeaders == nil {
		compactHeaders = deps.Headers
	}

	prompt := strings.Replace(SelfSummarySystemPrompt, "{count}", fmt.Sprintf("%d", len(older)), 1)
	prompt = strings.Replace(prompt, "{n}", fmt.Sprintf("%d", compactionCount+1), 1)
	summaryMessages := []Message{
		{"role": "system", "content": prompt},
		{"role": "user", "content": convoB.String()},
	}

	if deps.LLMCall == nil {
		return messages, contextLength, false
	}

	opts := LLMCallOptions{
		Temperature:    0.2,
		MaxTokens:      SummaryMaxTokens,
		TimeoutSeconds: 30,
	}
	summary, err := deps.LLMCall(ctx, compactURL, compactModel, summaryMessages, opts)
	if err != nil {
		// Degrade gracefully: keep the conversation intact rather than silently
		// dropping the older half. Caller's own trim pass handles length.
		return messages, contextLength, false
	}

	summaryMsg := Message{
		"role":    "system",
		"content": fmt.Sprintf("[Conversation summary — earlier messages were compacted]\n%s", summary),
	}

	compacted := append([]Message{}, systemMsgs...)
	compacted = append(compacted, summaryMsg)
	compacted = append(compacted, recent...)

	updateSessionHistory(session, deps.HistoryReplacer, splitPoint, summary, len(systemMsgs))

	return compacted, contextLength, true
}

// estimateContextLength resolves the model's context window. With no resolver
// available, callers can pre-set deps.EndpointURL/Model and we'll pass
// them through; otherwise we fall back to SmallContextLimit so the threshold
// check still fires against a sensible baseline.
func estimateContextLength(url, model string, resolve ResolveEndpointFn) int {
	if resolve != nil {
		if u, mod, _, ok := resolve("primary", ""); ok && u != "" && mod != "" {
			_ = u
			_ = mod
		}
	}
	// The Python port calls src.model_context.get_context_length(endpoint_url, model).
	// Without that module available we return SmallContextLimit as a conservative
	// default that keeps the threshold check well-defined.
	_ = url
	_ = model
	return SmallContextLimit
}

// updateSessionHistory mirrors _update_session_history from the Python port.
// `splitPoint` is indexed against convo_msgs (system-stripped); session.History
// includes leading system messages, so the actual slice starts at
// systemMsgCount + splitPoint. We prepend session.History[:systemMsgCount]
// so persona/preset/RAG system messages survive compaction.
func updateSessionHistory(
	session SessionLike,
	replacer HistoryReplacer,
	splitPoint int,
	summary string,
	systemMsgCount int,
) {
	if session == nil {
		return
	}

	history := session.History()
	effectiveSplit := systemMsgCount + splitPoint
	if effectiveSplit >= len(history) {
		return
	}

	systemPrefix := append([]Message{}, history[:systemMsgCount]...)
	recentHistory := append([]Message{}, history[effectiveSplit:]...)
	summaryMsg := Message{
		"role":     "system",
		"content":  fmt.Sprintf("[Conversation summary]\n%s", summary),
		"metadata": map[string]any{"compacted": true, "summarized_count": splitPoint},
	}
	newHistory := append([]Message{}, systemPrefix...)
	newHistory = append(newHistory, summaryMsg)
	newHistory = append(newHistory, recentHistory...)

	if replacer != nil && session.ID() != "" {
		if replacer.ReplaceMessages(session.ID(), newHistory) {
			return
		}
	}
	session.SetHistory(newHistory)
}
