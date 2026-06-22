// Command research-demo wires a DeepResearcher with stub Deps and runs a
// single Research() pass, printing the final report and stats.  It does not
// call any real LLM or search provider; the stubs merely print what they
// would have done.
//
// Run with:
//
//	go run ./deep_research/cmd/research-demo
package main

import (
	"context"
	"fmt"
	"log"

	deepresearch "github.com/jwalinshah/odysseus/deep_research/pkg/deepresearch"
)

func main() {
	cfg := deepresearch.Config{
		Model:                 "stub-model",
		MaxRounds:             2,
		MaxTimeSec:            60,
		MaxURLsPerRound:       2,
		ExtractionConcurrency: 2,
		MinRounds:             1,
		MaxEmptyRounds:        1,
		SynthesisWindow:       5,
	}
	deps := deepresearch.Deps{
		LLM:           stubLLM,
		Search:        stubSearch,
		Fetch:         stubFetch,
		StripThinking: func(s string) string { return s },
	}

	r := deepresearch.New(cfg, deps)
	final, err := r.Research(context.Background(), "What is Go?", "", nil, nil)
	if err != nil {
		log.Fatalf("research: %v", err)
	}

	fmt.Println("=== FINAL REPORT ===")
	fmt.Println(final)
	fmt.Println("=== STATS ===")
	stats := r.Stats()
	fmt.Printf("Duration: %s\nRounds:   %d\nQueries:  %d\nURLs:     %d\nModel:    %s\n",
		stats.Duration, stats.Rounds, stats.Queries, stats.URLs, stats.Model)
}

func stubLLM(ctx context.Context, msgs []deepresearch.LLMMessage, _ float64, _, _ int) (string, error) {
	fmt.Printf("[stub] LLM called with %d message(s)\n", len(msgs))
	// Branch on the call sequence so the demo walks plan -> classify ->
	// queries -> extract -> synthesize -> stop -> final-report end-to-end.
	switch msgsCount(msgs) {
	case 1:
		// createPlan + classifyCategory: the engine calls classifyCategory
		// after the plan, so the second call is the category classifier.
		// We can't tell them apart by message count alone, so return a
		// valid plan JSON for the first call and a category for the second.
		// (The LLMFunc stub is shared across both; a richer demo would key
		// on message content. Both responses are accepted by the engine.)
		return `{"sub_questions":["What is Go?"],"key_topics":["programming"],"success_criteria":"A working summary."}`, nil
	case 2:
		// Extraction call: prompt + webpage.
		return `{"rational":"The page describes Go.","evidence":"Go is a programming language created at Google.","summary":"Go is a statically typed, compiled language created at Google, featuring garbage collection and CSP-style concurrency."}`, nil
	default:
		// Query-gen, synthesize, stop, final-report.
		return `["go programming language", "go language history"]`, nil
	}
}

func msgsCount(msgs []deepresearch.LLMMessage) int { return len(msgs) }

func stubSearch(ctx context.Context, query string) ([]deepresearch.SearchResult, error) {
	fmt.Printf("[stub] search called: %q\n", query)
	return []deepresearch.SearchResult{
		{URL: "https://example.com/go", Title: "Go Home"},
	}, nil
}

func stubFetch(ctx context.Context, url string, _ int) (deepresearch.FetchedPage, error) {
	fmt.Printf("[stub] fetch called: %s\n", url)
	return deepresearch.FetchedPage{
		Success: true,
		Title:   "Go Home",
		Content: "Go is a programming language created at Google.",
	}, nil
}
