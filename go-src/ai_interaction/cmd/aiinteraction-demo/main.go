// Command aiinteraction-demo walks through every public surface of the
// aiinteraction package using in-memory stubs for the interfaces the
// Python source wires against a live Flask app + database.
//
// Run with:
//
//	go run ./cmd/aiinteraction-demo
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"strings"

	aii "github.com/odysseus/ai_interaction/pkg/aiinteraction"
)

const usage = `aiinteraction-demo — exercise the aiinteraction package.

USAGE
  aiinteraction-demo [options]

OPTIONS
  --help        show this help and exit
  --list-tests  print the names of every demo scenario, then exit

DESCRIPTION
  Walks the public surface of github.com/odysseus/ai_interaction/pkg/aiinteraction
  using in-memory stubs for the interfaces the Python source wires against a
  live Flask app + database. Prints a short scenario per package function so
  reviewers can eyeball behaviour without spinning up the chat agent.
`

func main() {
	help := flag.Bool("help", false, "show help and exit")
	listTests := flag.Bool("list-tests", false, "print scenario names, then exit")
	flag.Usage = func() { fmt.Fprint(os.Stderr, usage) }
	flag.Parse()
	if *help {
		fmt.Print(usage)
		return
	}
	if *listTests {
		fmt.Println("scenarios:")
		fmt.Println("  pipeline: parse + validate")
		fmt.Println("  manage_memory: add / list / search")
		fmt.Println("  manage_rag: list / add_directory")
		fmt.Println("  ui_control: toggle / set_mode / open_panel / open_email_reply")
		fmt.Println("  generate_image: parse + classify")
		fmt.Println("  model spec + dispatch")
		fmt.Println("  stream: one final event")
		return
	}

	fmt.Println("== aiinteraction demo ==")
	fmt.Println()

	// -----------------------------------------------------------------
	// 1. Pipeline parser (JSON + line format) and step validator.
	// -----------------------------------------------------------------
	fmt.Println("[1] pipeline: parse + validate")
	jsonReq, err := aii.ParsePipelineSteps(`{"steps":[
		{"model":"gpt-4","instruction":"draft"},
		{"model":"claude-sonnet-4","instruction":"critique"}
	]}`)
	if err != nil {
		fmt.Println("  json parse error:", err)
	} else {
		fmt.Printf("  format=%s steps=%d\n", jsonReq.Format, len(jsonReq.Steps))
	}
	linesReq, err := aii.ParsePipelineSteps("gpt-4 | draft\ngpt-4 | refine")
	if err != nil {
		fmt.Println("  lines parse error:", err)
	} else {
		fmt.Printf("  format=%s steps=%d\n", linesReq.Format, len(linesReq.Steps))
	}
	if err := aii.ValidatePipelineSteps(linesReq.Steps); err != nil {
		fmt.Println("  validate error:", err)
	}

	// End-to-end pipeline run with a stub LLM.
	resolver := func(spec, owner string) (aii.ResolvedModel, error) {
		return aii.ResolvedModel{
			EndpointURL: "https://api.openai.com/v1/chat/completions",
			ModelID:     spec,
			Headers:     map[string]string{"Authorization": "Bearer stub"},
		}, nil
	}
	llm := func(ctx context.Context, url, model string, headers map[string]string, msgs []aii.ChatMessage, timeout int) (string, error) {
		return "stub output for " + model, nil
	}
	res, _ := aii.RunPipeline(linesReq, resolver, llm)
	fmt.Printf("  result.results: %s\n", truncate(res.Results, 120))
	fmt.Printf("  steps=%d final=%q\n", len(res.Steps), res.FinalOutput)
	fmt.Println()

	// -----------------------------------------------------------------
	// 2. Memory parser + driver (with in-memory store stub).
	// -----------------------------------------------------------------
	fmt.Println("[2] manage_memory: add / list / search")
	store := &memStore{entries: []aii.MemoryEntry{}}
	addRes, _ := aii.RunManageMemory("add\nlikes coffee", store, nil, nil, "")
	fmt.Printf("  add: %s\n", addRes.Results)
	listRes, _ := aii.RunManageMemory("list", store, nil, nil, "")
	fmt.Printf("  list: %s\n", listRes.Results)
	searchRes, _ := aii.RunManageMemory("search\ncoffee", store, nil, nil, "")
	fmt.Printf("  search: %s\n", searchRes.Results)
	fmt.Println()

	// -----------------------------------------------------------------
	// 3. RAG parser + driver.
	// -----------------------------------------------------------------
	fmt.Println("[3] manage_rag: list / add_directory")
	pdocs := &fakePersonalDocs{files: []any{"doc1.txt", map[string]any{"name": "doc2.md"}}, dirs: []string{"/notes"}}
	listRes, _ = aii.RunManageRAG("list", nil, pdocs)
	fmt.Printf("  list: %s\n", listRes.Results)
	expanded := aii.ExpandDirectory("~/notes")
	fmt.Printf("  expand: ~/notes -> %s\n", expanded)
	fmt.Println()

	// -----------------------------------------------------------------
	// 4. UI control parser + driver (subset of actions).
	// -----------------------------------------------------------------
	fmt.Println("[4] ui_control: toggle / set_mode / open_panel / open_email_reply")
	for _, content := range []string{
		"toggle shell on",
		"set_mode chat",
		"open_panel memories",
		"open_email_reply 42 INBOX reply Sounds good, sending now.",
	} {
		out, _ := aii.RunUIControl(content, aii.UIControlOptions{
			Resolver: resolver,
		})
		fmt.Printf("  %-50s -> %s\n", content, out.Results)
	}
	fmt.Println()

	// -----------------------------------------------------------------
	// 5. Image request parser + classifier.
	// -----------------------------------------------------------------
	fmt.Println("[5] generate_image: parse + classify")
	imgReq, err := aii.ParseImageRequest("a foggy mountain at dawn\ngpt-image-1\n1536x1024\nhigh")
	if err != nil {
		fmt.Println("  parse error:", err)
	} else {
		gpt, dalle, local := aii.ClassifyImageModel(imgReq.Model)
		fmt.Printf("  prompt=%q model=%s size=%s quality=%s\n",
			truncate(imgReq.Prompt, 40), imgReq.Model, imgReq.Size, imgReq.Quality)
		fmt.Printf("  classifier: gpt=%v dalle=%v local=%v\n", gpt, dalle, local)
	}
	fmt.Println()

	// -----------------------------------------------------------------
	// 6. Model spec parser + dispatcher smoke.
	// -----------------------------------------------------------------
	fmt.Println("[6] model spec + dispatch")
	spec, _ := aii.ParseModelSpec("claude-sonnet-4@my-endpoint")
	fmt.Printf("  spec=%+v\n", spec)
	deps := aii.DriverDeps{
		Resolver: resolver,
		LLM:      llm,
		Prefs:    nilPrefs{},
	}
	desc, result := aii.DispatchTool("ui_control", "highlight .chat-bubble New message", "", "", deps)
	fmt.Printf("  desc=%q result.results=%q\n", desc, result.Results)
	fmt.Println()

	// -----------------------------------------------------------------
	// 7. Stream channel smoke.
	// -----------------------------------------------------------------
	fmt.Println("[7] stream: one final event")
	ch := aii.StreamTool("pipeline", "gpt-4 | summarize", "", "", deps)
	for ev := range ch {
		fmt.Printf("  final=%v desc=%q results=%q\n", ev.Final, ev.Desc, ev.Result.Results)
	}
	fmt.Println()
	fmt.Println("== done ==")
}

// memStore is a minimal in-memory MemoryStore for the demo.
type memStore struct {
	entries []aii.MemoryEntry
}

func (m *memStore) Load(string) []aii.MemoryEntry {
	return append([]aii.MemoryEntry{}, m.entries...)
}

func (m *memStore) LoadAll() []aii.MemoryEntry {
	return append([]aii.MemoryEntry{}, m.entries...)
}

func (m *memStore) Save(entries []aii.MemoryEntry) error {
	m.entries = append([]aii.MemoryEntry{}, entries...)
	return nil
}

func (m *memStore) AddEntry(text, source, category, owner string) (aii.MemoryEntry, error) {
	e := aii.MemoryEntry{
		ID:        "mem-" + text,
		Text:      text,
		Category:  category,
		Owner:     owner,
		Timestamp: 0,
	}
	m.entries = append(m.entries, e)
	return e, nil
}

func (m *memStore) RelevantMemories(query string, memories []aii.MemoryEntry, threshold float64, maxItems int) ([]aii.MemoryEntry, bool) {
	return nil, false
}

// fakePersonalDocs is a minimal PersonalDocsManager stub.
type fakePersonalDocs struct {
	files []any
	dirs  []string
}

func (f *fakePersonalDocs) IndexedFiles() []any          { return f.files }
func (f *fakePersonalDocs) IndexedDirectories() []string { return f.dirs }
func (f *fakePersonalDocs) RemoveDirectory(string) error { return nil }

// nilPrefs returns no custom themes.
type nilPrefs struct{}

func (nilPrefs) CustomThemes() map[string]any { return nil }

func truncate(s string, n int) string {
	s = strings.ReplaceAll(s, "\n", " ")
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
