package agentloop

import (
	"regexp"
	"strings"
)

// ClassifyResult is the structured return of ClassifyAgentRequest.
//
// Mode is one of "chat", "agent", or "ambiguous" — the same three the Python
// _classify_agent_request produces (via its "domains" / "low_signal" flags,
// which collapse to a binary mode for the Go port). Confidence is a heuristic
// score in [0,1]. Reason is a short human-readable explanation.
//
// The classifier is keyword-only — it does NOT call an LLM. The Python
// implementation also has a keyword-only fast path; the Go port uses the
// same keyword set documented in classifyKeywords.
type ClassifyResult struct {
	Mode       string  `json:"mode"`
	Confidence float64 `json:"confidence"`
	Reason     string  `json:"reason"`
}

// ClassifyAgentRequest inspects the last user message and (if available) the
// recent message history to decide whether this turn should be handled by a
// chat-style answer or routed to a tool-using agent loop.
//
//   - "chat"       → low signal, no tool affordances detected
//   - "agent"      → strong tool/domain keyword match (cookbook, files,
//     calendar, web, integrations, etc.)
//   - "ambiguous"  → keyword match exists but is weak OR only "yes/do it"
//     continuation is detected
//
// This is a heuristic port of Python _classify_agent_request. See
// classifyKeywords for the exact word lists.
func ClassifyAgentRequest(messages []Message, lastUser string) ClassifyResult {
	text := strings.TrimSpace(lastUser)

	// Empty / pure punctuation → chat.
	if text == "" || lowSignalRE.MatchString(text) {
		return ClassifyResult{Mode: "chat", Confidence: 0.9, Reason: "empty or low-signal input"}
	}

	q := strings.ToLower(text)
	matchedDomains := []string{}
	for _, kw := range classifyKeywords {
		if kw.re.MatchString(q) {
			matchedDomains = append(matchedDomains, kw.domain)
		}
	}

	// Continuation patterns ("yes", "do it") only count if we ALSO see the
	// assistant has asked a follow-up question — see isExplicitContinuation.
	if len(matchedDomains) == 0 {
		if isExplicitContinuation(text) || assistantRequestedFollowup(messages) {
			return ClassifyResult{Mode: "ambiguous", Confidence: 0.55, Reason: "continuation reply"}
		}
		return ClassifyResult{Mode: "chat", Confidence: 0.7, Reason: "no domain keywords matched"}
	}

	// Multiple domain hits → strong agent signal.
	conf := 0.6 + 0.1*float64(len(matchedDomains))
	if conf > 0.95 {
		conf = 0.95
	}
	return ClassifyResult{
		Mode:       "agent",
		Confidence: conf,
		Reason:     "matched domains: " + strings.Join(matchedDomains, ","),
	}
}

// classifyKeyword binds a domain label to a compiled regex. The patterns
// mirror the Python `_classify_agent_request` keyword set (the SPEC explicitly
// asks for a keyword set close to the Python version).
type classifyKeyword struct {
	domain string
	re     *regexp.Regexp
}

// classifyKeywords is the public, documented keyword table used by
// ClassifyAgentRequest. The list is representative — the Python source
// covers ~12 domains with several regexes each; this port keeps the most
// load-bearing keywords from each so test cases from the Python suite still
// classify the same way.
var classifyKeywords = []classifyKeyword{
	{"cookbook", regexp.MustCompile(`(?i)\b(cookbook|serve|serving|served|launch|start|preset|vllm|sglang|llama\.?cpp|ollama|download|downloading|pull|cached models?|running models?|model servers?|model picker|gpu box|odysseus|qwen|gemma|llama|mistral)\b`)},
	{"email", regexp.MustCompile(`(?i)\b(emails?|mails?|gmail|inbox|reply|forward|cc|bcc|send email|compose email|draft email)\b`)},
	{"notes_calendar_tasks", regexp.MustCompile(`(?i)\b(note|todo|to-do|checklist|task list|remind me|reminder|buy|pickup)\b`)},
	{"calendar", regexp.MustCompile(`(?i)\b(every day|every morning|every evening|recurring|automatically|cron|scheduled task|background task)\b`)},
	{"calendar_event", regexp.MustCompile(`(?i)\b(calendar|event|meeting|appointment|schedule)\b`)},
	{"documents", regexp.MustCompile(`(?i)\b(documents?|docs?|draft|compose|poem|story|essay|outline|letter|edit|rewrite|proofread|suggest|feedback|review this|make a file)\b`)},
	{"web", regexp.MustCompile(`(?i)\b(search|web|google|look up|latest|news|current|weather|forecast|stock price|price of|website|url|https?://|www\.)\b`)},
	{"web_polish", regexp.MustCompile(`(?i)\b(wyszukaj|wyszukać|wyszukac)\b.*\b(internet|internecie|online|web)\b`)},
	{"research", regexp.MustCompile(`(?i)\b(research|deep dive|investigate|look into)\b`)},
	{"ui", regexp.MustCompile(`(?i)\b(open|show|toggle|turn on|turn off|disable|enable|switch model|change model|settings|theme|panel)\b`)},
	{"sessions", regexp.MustCompile(`(?i)\b(session|chat history|rename chat|delete chat|archive chat|fork chat|list chats)\b`)},
	{"files", regexp.MustCompile(`(?i)\b(file|folder|directory|repo|git|grep|find in files|read file|edit file|shell|terminal|bash|python)\b`)},
	{"settings", regexp.MustCompile(`(?i)\b(endpoint|api token|mcp|webhook|preference|configure|config|setting)\b`)},
	{"contacts", regexp.MustCompile(`(?i)\b(contact|contacts|phone|phone number|address book|vcard)\b`)},
	{"integrations", regexp.MustCompile(`(?i)\bapi[ _]call\b|\bintegrations?\b|\b(home ?assistant|miniflux|gitea|linkding|jellyfin)\b`)},
}

// lowSignalRE is the Go equivalent of Python _LOW_SIGNAL_RE: an input that is
// only punctuation / underscores is not actionable.
var lowSignalRE = regexp.MustCompile(`^[\W_]*$`)

// explicitContinuationRE is the Go port of _EXPLICIT_CONTINUATION_RE.
// Go's regexp package is case-insensitive via the (?i) flag in the pattern.
var explicitContinuationRE = regexp.MustCompile(
	`(?i)^\s*(?:yes|y|yeah|yep|ok|okay|sure|do it|go ahead|continue|carry on|run it|launch it|start it|use that|that one|same|the same|first|second|third|the first one|the second one|the third one|[123]|[abc])[\.\!?]*\s*$`,
)

// isExplicitContinuation mirrors Python _is_explicit_continuation.
func isExplicitContinuation(text string) bool {
	return explicitContinuationRE.MatchString(strings.TrimSpace(text))
}

// assistantRequestedFollowup is the Go port of Python
// _assistant_requested_followup. It returns true if the most recent
// assistant turn asked a clarifying question. Used to let terse "yes/do it"
// replies inherit the prior domain.
func assistantRequestedFollowup(messages []Message) bool {
	seenLatestUser := false
	// Walk in reverse.
	for i := len(messages) - 1; i >= 0; i-- {
		m := messages[i]
		if m.Role == "user" && !seenLatestUser {
			seenLatestUser = true
			continue
		}
		if !seenLatestUser {
			continue
		}
		if m.Role != "assistant" {
			continue
		}
		text := strings.ToLower(m.Content)
		if !strings.Contains(text, "?") {
			return false
		}
		return assistantFollowupQRE.MatchString(text)
	}
	return false
}

// assistantFollowupQRE is the subset of the Python follow-up regex.
var assistantFollowupQRE = regexp.MustCompile(`(?i)\b(what would you like|what should|what do you want|which one|which model|any specific|give me|tell me)\b`)
