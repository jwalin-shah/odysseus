package agentloop

import "testing"

func TestClassify_ChatKeyword_ChatMode(t *testing.T) {
	t.Parallel()
	res := ClassifyAgentRequest(nil, "what is the capital of France?")
	if res.Mode != "chat" {
		t.Fatalf("Mode = %q, want chat", res.Mode)
	}
}

func TestClassify_AgentKeyword_AgentMode(t *testing.T) {
	t.Parallel()
	res := ClassifyAgentRequest(nil, "search the web for the latest news on quantum computing")
	if res.Mode != "agent" {
		t.Fatalf("Mode = %q, want agent", res.Mode)
	}
	if res.Confidence <= 0.5 {
		t.Fatalf("Confidence = %f, want > 0.5", res.Confidence)
	}
}

func TestClassify_NoKeywords_Ambiguous(t *testing.T) {
	t.Parallel()
	// Continuation reply ("yes") with no other signal — ambiguous mode.
	res := ClassifyAgentRequest([]Message{
		{Role: "assistant", Content: "What would you like to do?"},
	}, "yes")
	if res.Mode != "ambiguous" {
		t.Fatalf("Mode = %q, want ambiguous", res.Mode)
	}
}

// Verify a Polish-language web-search request classifies as agent (matches
// the web_polish domain). This mirrors test_polish_internet_search_request in
// the Python suite.
func TestClassify_PolishWebSearch_AgentMode(t *testing.T) {
	t.Parallel()
	res := ClassifyAgentRequest(nil, "Wyszukaj w internecie i podaj temperaturę w Lubartowie dzisiaj")
	if res.Mode != "agent" {
		t.Fatalf("Mode = %q, want agent", res.Mode)
	}
	if !contains(res.Reason, "web") && !contains(res.Reason, "web_polish") {
		t.Fatalf("Reason should mention web domain, got %q", res.Reason)
	}
}

func contains(s, substr string) bool {
	for i := 0; i+len(substr) <= len(s); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
