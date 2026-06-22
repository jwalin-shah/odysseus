// Package contextcompactor provides auto-compaction of conversation history
// when approaching a model's context window. It is the Go port of
// src/context_compactor.py.
//
// The package exposes helpers for flattening multimodal content, sanitizing
// orphan/dangling tool messages, estimating token counts, trimming messages
// against a context budget, and (in async.go) summarizing older turns via an
// injected LLM call.
package contextcompactor

import (
	"encoding/json"
	"strings"
)

// Message mirrors the OpenAI message shape used by the rest of the system.
// Defined locally so the package stays decoupled from any DB/ORM.
type Message = map[string]any

const (
	// CompactThreshold triggers compaction when usage crosses this fraction of
	// the model's context window.
	CompactThreshold = 0.85

	// SummaryMaxTokens caps the token budget for the self-summary request.
	SummaryMaxTokens = 1024

	// SmallContextLimit identifies models that get aggressive trimming.
	SmallContextLimit = 8192
)

// SelfSummarySystemPrompt is the structured, dense summary prompt used by
// MaybeCompact. Placeholders {count} and {n} are substituted at call time.
var SelfSummarySystemPrompt = `You are summarizing a conversation to preserve context after compaction. Produce a structured summary that lets the conversation continue seamlessly.

Use this format:

## Conversation Summary
**Turns summarized:** {count}  |  **Compactions so far:** {n}

### User Goal
One sentence describing what the user is trying to accomplish.

### What Was Done
- Bullet points of completed actions, decisions made, and key outputs
- Include specific file paths, function names, variable names, URLs, and config values
- Note any errors encountered and how they were resolved

### Current State
What is the system/code/task state right now? What was the last thing discussed?

### Pending / Next Steps
- What remains to be done
- Any open questions or blockers

### Key Context
- Important constraints, preferences, or decisions that must not be forgotten
- Specific values: model names, ports, paths, credentials references, versions

Keep the summary under 1000 tokens. Be dense — every token should carry information. Do not include pleasantries or meta-commentary.`

// ContentAsText flattens a message's content to plain text.
//
// Handles the three shapes that flow through history: a plain string, a
// multimodal list of content blocks (vision/image attachments), and None
// (assistant turns that carried only native tool_calls persist content as
// None). Returns "" for anything without text so callers can safely slice
// the result.
func ContentAsText(content any) string {
	switch v := content.(type) {
	case string:
		return v
	case []any:
		var b strings.Builder
		for _, item := range v {
			m, ok := item.(map[string]any)
			if !ok {
				continue
			}
			if t, _ := m["text"].(string); t != "" {
				b.WriteString(t)
				b.WriteString(" ")
			}
		}
		return strings.TrimRight(b.String(), " ")
	case []map[string]any:
		var b strings.Builder
		for _, item := range v {
			if t, _ := item["text"].(string); t != "" {
				b.WriteString(t)
				b.WriteString(" ")
			}
		}
		return strings.TrimRight(b.String(), " ")
	}
	return ""
}

// SanitizeToolMessages drops orphaned `tool` messages and dangling assistant
// `tool_calls`.
//
// OpenAI's API requires every `role:"tool"` message to immediately follow an
// assistant message that carries `tool_calls` (or another tool message in the
// same batch). Front-trimming the history can cut the assistant `tool_calls`
// parent while keeping its tool responses, which triggers: "messages with role
// 'tool' must be a response to a preceding message with 'tool_calls'". This
// pass repairs that:
//   - drops `tool` messages with no valid preceding tool_calls
//   - drops assistant `tool_calls` messages whose tool responses were all
//     trimmed away (some providers reject unanswered tool_calls)
func SanitizeToolMessages(msgs []Message) []Message {
	// Pass 1: drop orphan tool messages.
	cleaned := make([]Message, 0, len(msgs))
	inBatch := false
	for _, m := range msgs {
		role, _ := m["role"].(string)
		if role == "tool" {
			if inBatch {
				cleaned = append(cleaned, m)
			}
			// else: orphan — drop
			continue
		}
		if role == "assistant" && hasToolCalls(m) {
			inBatch = true
		} else {
			inBatch = false
		}
		cleaned = append(cleaned, m)
	}

	// Pass 2: drop assistant tool_calls messages that have NO following tool
	// response (dangling).
	out := make([]Message, 0, len(cleaned))
	for i, m := range cleaned {
		role, _ := m["role"].(string)
		if role == "assistant" && hasToolCalls(m) {
			var nxt Message
			if i+1 < len(cleaned) {
				nxt = cleaned[i+1]
			}
			nextRole, _ := nxt["role"].(string)
			if nxt == nil || nextRole != "tool" {
				// Dangling tool_calls — keep the message but strip the
				// tool_calls so it's a plain assistant turn.
				stripped := Message{}
				for k, v := range m {
					if k == "tool_calls" {
						continue
					}
					stripped[k] = v
				}
				if contentStr, _ := stripped["content"].(string); strings.TrimSpace(contentStr) == "" {
					continue
				}
				m = stripped
			}
		}
		out = append(out, m)
	}
	return out
}

// MessageTextTokenEstimate matches src.model_context.estimate_tokens' rough
// chars * 0.3 estimate. Returns a small floor for non-string input.
func MessageTextTokenEstimate(text string) int {
	if text == "" {
		return 4
	}
	return int(float64(len(text))*0.3) + 4
}

// TruncateTextToTokenBudget trims a too-large current user message instead of
// dropping it entirely.
func TruncateTextToTokenBudget(text string, tokenBudget int) string {
	if tokenBudget <= 32 {
		return "[Current user message omitted: it exceeded the model context window.]"
	}

	// Match src.model_context.estimate_tokens' rough chars * 0.3 estimate.
	maxChars := maxInt(200, int(float64(tokenBudget-16)/0.3))
	if len(text) <= maxChars {
		return text
	}

	notice := "\n\n[Notice: the pasted message was too large for this model's context window, so Odysseus kept the beginning and end.]"
	keepChars := maxInt(200, maxChars-len(notice))
	headLen := maxInt(100, int(float64(keepChars)*0.7))
	tailLen := maxInt(80, keepChars-headLen)
	return strings.TrimRight(text[:headLen], " \t\n") + notice + "\n\n" + strings.TrimLeft(text[len(text)-tailLen:], " \t\n")
}

// TruncateToolCallArgs shrinks oversized assistant `tool_calls` arguments to
// fit `tokenBudget`. A tool-only turn persists `content=None` with its whole
// payload in `tool_calls[].function.arguments`, which the text-content
// truncation can't reach — so the message could stay over budget and the
// upstream call would 400. Replace each argument string that overflows its
// share of the budget with a small valid-JSON placeholder, preserving
// `id`/`type`/`function.name`. Returns msg unchanged when there is nothing
// oversized.
func TruncateToolCallArgs(msg Message, tokenBudget int) Message {
	toolCalls, ok := msg["tool_calls"].([]any)
	if !ok || len(toolCalls) == 0 {
		return msg
	}
	// Budget left after whatever content survived (estimate_tokens counts tool
	// arguments too, so measure content alone here).
	contentTokens := estimateContentTokens(msg)
	perCall := maxInt(16, maxInt(0, tokenBudget-contentTokens)/len(toolCalls))

	newCalls := make([]any, 0, len(toolCalls))
	changed := false
	for _, tc := range toolCalls {
		tcMap, isMap := tc.(map[string]any)
		if !isMap {
			newCalls = append(newCalls, tc)
			continue
		}
		fn, _ := tcMap["function"].(map[string]any)
		args, _ := fn["arguments"].(string)
		if args != "" && MessageTextTokenEstimate(args) > perCall {
			newFn := map[string]any{}
			for k, v := range fn {
				newFn[k] = v
			}
			placeholder, _ := json.Marshal(map[string]any{"_truncated_for_context": len(args)})
			newFn["arguments"] = string(placeholder)
			newTc := map[string]any{}
			for k, v := range tcMap {
				newTc[k] = v
			}
			newTc["function"] = newFn
			newCalls = append(newCalls, newTc)
			changed = true
		} else {
			newCalls = append(newCalls, tc)
		}
	}
	if !changed {
		return msg
	}
	out := map[string]any{}
	for k, v := range msg {
		out[k] = v
	}
	out["tool_calls"] = newCalls
	return out
}

// TruncateMessageToTokenBudget returns a copy of msg whose text content (and
// tool-call args) fit tokenBudget.
func TruncateMessageToTokenBudget(msg Message, tokenBudget int) Message {
	out := map[string]any{}
	for k, v := range msg {
		out[k] = v
	}
	content := out["content"]
	if s, ok := content.(string); ok {
		out["content"] = TruncateTextToTokenBudget(s, tokenBudget)
	} else if list, ok := content.([]any); ok {
		remaining := tokenBudget
		newContent := make([]any, 0, len(list))
		for _, item := range list {
			m, isMap := item.(map[string]any)
			if !isMap {
				newContent = append(newContent, item)
				continue
			}
			if t, _ := m["type"].(string); t != "text" {
				newContent = append(newContent, item)
				continue
			}
			text, _ := m["text"].(string)
			truncated := TruncateTextToTokenBudget(text, remaining)
			cloned := map[string]any{}
			for k, v := range m {
				cloned[k] = v
			}
			cloned["text"] = truncated
			newContent = append(newContent, cloned)
			remaining -= MessageTextTokenEstimate(truncated)
		}
		out["content"] = newContent
	}
	return TruncateToolCallArgs(out, tokenBudget)
}

// TrimForContext trims system messages to fit within context_length. For
// small-context models, progressively strips RAG/memory system messages
// (keeping preset system prompt + any research_spinoff primer), then older
// conversation turns. Reserves space for the response.
//
// The estimateTokens function should mirror src.model_context.estimate_tokens
// — a rough chars * 0.3 estimate plus per-message overhead. Callers that
// don't have one handy can pass defaultEstimateTokens.
func TrimForContext(messages []Message, contextLength int, reserveTokens int, estimateTokens func([]Message) int) []Message {
	if estimateTokens == nil {
		estimateTokens = defaultEstimateTokens
	}
	budget := contextLength - reserveTokens
	used := estimateTokens(messages)
	if used <= budget {
		return messages
	}

	systemMsgs := []Message{}
	protectedMsgs := []Message{}
	convoMsgs := []Message{}
	for _, msg := range messages {
		if protected, _ := msg["_protected"].(bool); protected {
			protectedMsgs = append(protectedMsgs, msg)
		} else if role, _ := msg["role"].(string); role == "system" {
			systemMsgs = append(systemMsgs, msg)
		} else {
			convoMsgs = append(convoMsgs, msg)
		}
	}

	protectedTokens := estimateTokens(protectedMsgs)
	budget -= protectedTokens

	// Priority: keep first system msg (preset prompt) + any research primers;
	// drop others (memory, RAG, memo).
	var primers []Message
	nonPrimer := []Message{}
	for _, m := range systemMsgs {
		if isResearchPrimer(m) {
			primers = append(primers, m)
		} else {
			nonPrimer = append(nonPrimer, m)
		}
	}
	var essentialSystem []Message
	if len(nonPrimer) > 0 {
		essentialSystem = append(essentialSystem, nonPrimer[0])
	}
	essentialSystem = append(essentialSystem, primers...)
	extraSystem := []Message{}
	if len(nonPrimer) > 1 {
		extraSystem = append(extraSystem, nonPrimer[1:]...)
	}

	// Try dropping extra system messages one by one (from the end).
	trimmed := append([]Message{}, essentialSystem...)
	trimmed = append(trimmed, convoMsgs...)
	if estimateTokens(trimmed) <= budget {
		result := append([]Message{}, essentialSystem...)
		for _, msg := range extraSystem {
			candidate := append([]Message{}, result...)
			candidate = append(candidate, msg)
			candidate = append(candidate, convoMsgs...)
			if estimateTokens(candidate) <= budget {
				result = append(result, msg)
			} else {
				break
			}
		}
		final := append([]Message{}, result...)
		final = append(final, protectedMsgs...)
		final = append(final, convoMsgs...)
		return SanitizeToolMessages(final)
	}

	// Still too big — truncate the first system message (but keep more than
	// 500 chars).
	if len(essentialSystem) > 0 {
		sysText, _ := essentialSystem[0]["content"].(string)
		if len(sysText) > 2000 {
			truncatedSys := Message{
				"role":    "system",
				"content": sysText[:2000] + "\n[System prompt truncated for context limits]",
			}
			essentialSystem[0] = truncatedSys
			trimmed = append([]Message{}, essentialSystem...)
			trimmed = append(trimmed, convoMsgs...)
			if estimateTokens(trimmed) <= budget {
				final := append([]Message{}, essentialSystem...)
				final = append(final, protectedMsgs...)
				final = append(final, convoMsgs...)
				return SanitizeToolMessages(final)
			}
		}
	}

	// Still too big — drop older conversation turns BUT always keep the
	// current user turn. If a pasted message alone exceeds the model context,
	// truncate that message with a visible notice instead of dropping it.
	const protectRecent = 10
	var currentMsg []Message
	if len(convoMsgs) > 0 {
		currentMsg = convoMsgs[len(convoMsgs)-1:]
	}
	priorConvo := []Message{}
	if len(convoMsgs) > 0 {
		priorConvo = convoMsgs[:len(convoMsgs)-1]
	}
	if len(priorConvo) >= protectRecent {
		oldMsgs := append([]Message{}, priorConvo[:len(priorConvo)-(protectRecent-1)]...)
		recentMsgs := append([]Message{}, priorConvo[len(priorConvo)-(protectRecent-1):]...)
		recentMsgs = append(recentMsgs, currentMsg...)
		for len(oldMsgs) > 0 && estimateTokens(append(append([]Message{}, essentialSystem...), append(oldMsgs, recentMsgs...)...)) > budget {
			oldMsgs = oldMsgs[1:]
		}
		convoMsgs = append(oldMsgs, recentMsgs...)
	} else {
		convoMsgs = append(append([]Message{}, priorConvo...), currentMsg...)
		working := append([]Message{}, priorConvo...)
		for len(working) > 0 && estimateTokens(append(append(append([]Message{}, essentialSystem...), working...), currentMsg...)) > budget {
			working = working[1:]
		}
		convoMsgs = append(working, currentMsg...)
	}

	// If the current message itself is too large, shrink only that message.
	if len(currentMsg) > 0 && estimateTokens(append(append(append([]Message{}, essentialSystem...), protectedMsgs...), convoMsgs...)) > budget {
		prefix := append([]Message{}, essentialSystem...)
		prefix = append(prefix, protectedMsgs...)
		if len(convoMsgs) > 1 {
			prefix = append(prefix, convoMsgs[:len(convoMsgs)-1]...)
		}
		available := maxInt(64, budget-estimateTokens(prefix))
		last := convoMsgs[len(convoMsgs)-1]
		convoMsgs[len(convoMsgs)-1] = TruncateMessageToTokenBudget(last, available)
	}

	result := append([]Message{}, essentialSystem...)
	result = append(result, protectedMsgs...)
	result = append(result, convoMsgs...)
	return SanitizeToolMessages(result)
}

// defaultEstimateTokens is a rough chars * 0.3 estimate plus per-message
// overhead, used when no estimateTokens function is supplied.
func defaultEstimateTokens(msgs []Message) int {
	total := 0
	for _, m := range msgs {
		total += MessageTextTokenEstimate(ContentAsText(m["content"]))
	}
	return total
}

func estimateContentTokens(msg Message) int {
	return defaultEstimateTokens([]Message{
		{"role": msgOrDefault(msg, "role", "assistant"), "content": msg["content"]},
	})
}

func msgOrDefault(m Message, key, def string) string {
	if v, ok := m[key].(string); ok && v != "" {
		return v
	}
	return def
}

func hasToolCalls(m Message) bool {
	_, ok := m["tool_calls"]
	if !ok {
		return false
	}
	if list, ok := m["tool_calls"].([]any); ok && len(list) > 0 {
		return true
	}
	return false
}

func isResearchPrimer(m Message) bool {
	meta, ok := m["metadata"].(map[string]any)
	if !ok {
		return false
	}
	_, has := meta["research_spinoff_from"]
	return has
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
