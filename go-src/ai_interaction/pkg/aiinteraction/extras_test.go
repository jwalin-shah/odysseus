package aiinteraction

import (
	"context"
	"errors"
	"strings"
	"testing"
)

var errBoom = errors.New("boom")

// ---------------------------------------------------------------------------
// Shared stub used by every table in this file.
// ---------------------------------------------------------------------------

type memStoreStub struct {
	entries []MemoryEntry
	saveN   int
}

func (m *memStoreStub) Load(string) []MemoryEntry {
	return append([]MemoryEntry{}, m.entries...)
}

func (m *memStoreStub) LoadAll() []MemoryEntry {
	return append([]MemoryEntry{}, m.entries...)
}

func (m *memStoreStub) Save(entries []MemoryEntry) error {
	m.entries = append([]MemoryEntry{}, entries...)
	m.saveN++
	return nil
}

func (m *memStoreStub) AddEntry(text, source, category, owner string) (MemoryEntry, error) {
	e := MemoryEntry{ID: "mem-" + text, Text: text, Category: category, Owner: owner, Timestamp: 1}
	m.entries = append(m.entries, e)
	return e, nil
}

func (m *memStoreStub) RelevantMemories(query string, memories []MemoryEntry, threshold float64, maxItems int) ([]MemoryEntry, bool) {
	return nil, false
}

type memVecStub struct {
	healthy bool
	add     []string
	remove  []string
}

func (m *memVecStub) Healthy() bool             { return m.healthy }
func (m *memVecStub) Add(id, text string) error { m.add = append(m.add, id); return nil }
func (m *memVecStub) Remove(id string) error    { m.remove = append(m.remove, id); return nil }

type prefsStub struct{ themes map[string]any }

func (p prefsStub) CustomThemes() map[string]any { return p.themes }

type pdocsStub struct {
	files []any
	dirs  []string
}

func (p pdocsStub) IndexedFiles() []any          { return p.files }
func (p pdocsStub) IndexedDirectories() []string { return p.dirs }
func (p pdocsStub) RemoveDirectory(string) error { return nil }

type ragStub struct {
	indexed int
	calls   []string
}

func (r *ragStub) IndexPersonalDocuments(directory string) (map[string]int, error) {
	r.calls = append(r.calls, directory)
	return map[string]int{"indexed": r.indexed}, nil
}

type eventStub struct{ fired [][2]string }

func (e *eventStub) Fire(name, owner string) { e.fired = append(e.fired, [2]string{name, owner}) }

// ---------------------------------------------------------------------------
// Pipeline parser / validator / formatter
// ---------------------------------------------------------------------------

func TestParsePipelineSteps(t *testing.T) {
	tests := []struct {
		name    string
		content string
		wantFmt string
		wantLen int
		wantErr string
	}{
		{"empty", "", "", 0, "No pipeline steps provided"},
		{"json_obj", `{"steps":[{"model":"gpt-4","instruction":"x"}]}`, "json", 1, ""},
		{"json_obj_no_steps", `{"foo":1}`, "", 0, "JSON object must contain 'steps'"},
		{"json_list", `[{"model":"gpt-4","instruction":"x"}]`, "json", 1, ""},
		{"json_bad_step", `[{"model":""}]`, "", 0, "Step 1: both 'model' and 'instruction'"},
		{"lines", "gpt-4 | x\nclaude | y", "lines", 2, ""},
		{"lines_no_pipe", "gpt-4 x", "", 0, "Each line must be"},
		{"lines_blank_skip", "\n\ngpt-4 | x\n\n", "lines", 1, ""},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			req, err := ParsePipelineSteps(tc.content)
			if tc.wantErr != "" {
				if err == nil {
					t.Fatalf("want error containing %q, got nil", tc.wantErr)
				}
				if !strings.Contains(err.Error(), tc.wantErr) {
					t.Fatalf("error = %q, want contains %q", err.Error(), tc.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if req.Format != tc.wantFmt {
				t.Errorf("format = %q, want %q", req.Format, tc.wantFmt)
			}
			if len(req.Steps) != tc.wantLen {
				t.Errorf("len(steps) = %d, want %d", len(req.Steps), tc.wantLen)
			}
		})
	}
}

func TestValidatePipelineSteps(t *testing.T) {
	tests := []struct {
		name    string
		steps   []PipelineStep
		wantErr string
	}{
		{"empty", nil, "No pipeline steps provided"},
		{"too_many", makeSteps(MaxPipelineSteps + 1), "Maximum"},
		{"missing_model", []PipelineStep{{Instruction: "x"}}, "model"},
		{"missing_instr", []PipelineStep{{Model: "gpt-4"}}, "instruction"},
		{"ok", []PipelineStep{{Model: "gpt-4", Instruction: "x"}}, ""},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			err := ValidatePipelineSteps(tc.steps)
			if tc.wantErr == "" {
				if err != nil {
					t.Fatalf("unexpected error: %v", err)
				}
				return
			}
			if err == nil || !strings.Contains(err.Error(), tc.wantErr) {
				t.Fatalf("error = %v, want contains %q", err, tc.wantErr)
			}
		})
	}
}

func makeSteps(n int) []PipelineStep {
	out := make([]PipelineStep, n)
	for i := range out {
		out[i] = PipelineStep{Model: "gpt-4", Instruction: "x"}
	}
	return out
}

func TestFormatPipelineResults(t *testing.T) {
	out := FormatPipelineResults([]PipelineStepOutput{
		{Step: 1, Model: "gpt-4", Instruction: "draft", Output: "hello"},
	})
	for _, want := range []string{"# Pipeline Results (1 steps)", "## Step 1: gpt-4", "*Instruction: draft*", "hello"} {
		if !strings.Contains(out, want) {
			t.Errorf("missing %q in:\n%s", want, out)
		}
	}
}

func TestTruncateOutput(t *testing.T) {
	tests := []struct {
		in   string
		want string
	}{
		{"", ""},
		{"short", "short"},
		{strings.Repeat("x", 5000), strings.Repeat("x", 5000)},
		{strings.Repeat("x", 5001), strings.Repeat("x", 5000)},
	}
	for _, tc := range tests {
		got := TruncateOutput(tc.in)
		if got != tc.want {
			t.Errorf("TruncateOutput(len=%d) = %d, want %d", len(tc.in), len(got), len(tc.want))
		}
	}
}

// ---------------------------------------------------------------------------
// RunPipeline
// ---------------------------------------------------------------------------

func TestRunPipeline_HappyPath(t *testing.T) {
	resolver := func(spec, owner string) (ResolvedModel, error) {
		return ResolvedModel{EndpointURL: "https://x/v1/chat/completions", ModelID: spec, Headers: map[string]string{"Authorization": "Bearer x"}}, nil
	}
	llm := func(ctx ctxAlias, url, model string, headers map[string]string, msgs []ChatMessage, to int) (string, error) {
		return "out:" + model, nil
	}
	res, err := RunPipeline(&PipelineRequest{
		Steps: []PipelineStep{
			{Model: "gpt-4", Instruction: "draft"},
			{Model: "gpt-4", Instruction: "refine"},
		},
	}, resolver, llm)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res.Error != "" {
		t.Fatalf("error field: %q", res.Error)
	}
	if len(res.Steps) != 2 {
		t.Fatalf("steps = %d, want 2", len(res.Steps))
	}
	if res.FinalOutput != "out:gpt-4" {
		t.Errorf("final = %q", res.FinalOutput)
	}
}

func TestRunPipeline_NoResolver(t *testing.T) {
	llm := func(ctx ctxAlias, url, model string, headers map[string]string, msgs []ChatMessage, to int) (string, error) {
		return "", nil
	}
	res, _ := RunPipeline(&PipelineRequest{Steps: []PipelineStep{{Model: "x", Instruction: "y"}}}, nil, llm)
	if res.Error == "" {
		t.Fatalf("expected error when resolver is nil")
	}
}

func TestRunPipeline_TooManySteps(t *testing.T) {
	resolver := func(spec, owner string) (ResolvedModel, error) { return ResolvedModel{}, nil }
	llm := func(ctx ctxAlias, url, model string, headers map[string]string, msgs []ChatMessage, to int) (string, error) {
		return "", nil
	}
	res, _ := RunPipeline(&PipelineRequest{Steps: makeSteps(MaxPipelineSteps + 1)}, resolver, llm)
	if res.Error == "" {
		t.Fatalf("expected error when steps > MaxPipelineSteps")
	}
}

func TestRunPipeline_LLMError(t *testing.T) {
	resolver := func(spec, owner string) (ResolvedModel, error) {
		return ResolvedModel{ModelID: spec}, nil
	}
	llm := func(ctx ctxAlias, url, model string, headers map[string]string, msgs []ChatMessage, to int) (string, error) {
		return "", errBoom
	}
	res, _ := RunPipeline(&PipelineRequest{Steps: []PipelineStep{{Model: "gpt-4", Instruction: "x"}}}, resolver, llm)
	if !strings.Contains(res.Error, "Pipeline failed at step 1") {
		t.Fatalf("error = %q, want pipeline failure", res.Error)
	}
}

type ctxAlias = context.Context

// ---------------------------------------------------------------------------
// Memory parser + driver
// ---------------------------------------------------------------------------

func TestParseMemoryAction(t *testing.T) {
	tests := []struct {
		name    string
		content string
		action  string
		fields  MemoryAction
		wantErr string
	}{
		{"list", "list", "list", MemoryAction{}, ""},
		{"list_cat", "list\nfact", "list", MemoryAction{Category: "fact"}, ""},
		{"add", "add\nlikes coffee", "add", MemoryAction{Text: "likes coffee", Category: "fact"}, ""},
		{"add_cat", "add\nlikes tea\npreference", "add", MemoryAction{Text: "likes tea", Category: "preference"}, ""},
		{"add_empty", "add", "add", MemoryAction{}, "Add needs line 2"},
		{"edit", "edit\nabc-123\nnew text", "edit", MemoryAction{MemoryID: "abc-123", NewText: "new text"}, ""},
		{"edit_short", "edit", "edit", MemoryAction{}, "Edit needs line 2"},
		{"delete", "delete\nabc-123", "delete", MemoryAction{MemoryID: "abc-123"}, ""},
		{"search", "search\ncoffee", "search", MemoryAction{Query: "coffee"}, ""},
		{"unknown", "frobnicate", "frobnicate", MemoryAction{}, "Unknown action"},
		{"empty", "", "", MemoryAction{}, "Need at least 1 line"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseMemoryAction(tc.content)
			if tc.wantErr != "" {
				if err == nil || !strings.Contains(err.Error(), tc.wantErr) {
					t.Fatalf("err = %v, want contains %q", err, tc.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got.Action != tc.action {
				t.Errorf("action = %q, want %q", got.Action, tc.action)
			}
			if tc.fields.Category != "" && got.Category != tc.fields.Category {
				t.Errorf("category = %q, want %q", got.Category, tc.fields.Category)
			}
			if tc.fields.Text != "" && got.Text != tc.fields.Text {
				t.Errorf("text = %q, want %q", got.Text, tc.fields.Text)
			}
			if tc.fields.MemoryID != "" && got.MemoryID != tc.fields.MemoryID {
				t.Errorf("memory_id = %q, want %q", got.MemoryID, tc.fields.MemoryID)
			}
			if tc.fields.NewText != "" && got.NewText != tc.fields.NewText {
				t.Errorf("new_text = %q, want %q", got.NewText, tc.fields.NewText)
			}
			if tc.fields.Query != "" && got.Query != tc.fields.Query {
				t.Errorf("query = %q, want %q", got.Query, tc.fields.Query)
			}
		})
	}
}

func TestFormatMemoryList(t *testing.T) {
	tests := []struct {
		name     string
		memories []MemoryEntry
		filter   string
		wantSubs []string
	}{
		{"empty", nil, "", []string{"No memories found."}},
		{"empty_filter", []MemoryEntry{{Category: "fact"}}, "preference", []string{"No memories found in category 'preference'."}},
		{"nonempty", []MemoryEntry{{ID: "abcdef1234", Category: "fact", Text: "hello"}}, "", []string{"Found 1 memory entries", "[fact]", "abcdef12", "hello"}},
		{"truncate_text", []MemoryEntry{{ID: "abcdef1234", Category: "fact", Text: strings.Repeat("x", 200)}}, "", []string{"..."}},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := FormatMemoryList(tc.memories, tc.filter)
			for _, s := range tc.wantSubs {
				if !strings.Contains(got, s) {
					t.Errorf("missing %q in %q", s, got)
				}
			}
		})
	}
}

func TestFilterMemoriesByText(t *testing.T) {
	memories := []MemoryEntry{
		{ID: "1", Text: "Coffee every morning"},
		{ID: "2", Text: "Tea in the afternoon"},
		{ID: "3", Text: "COFFEE!!"},
	}
	got := FilterMemoriesByText(memories, "coffee")
	if len(got) != 2 {
		t.Fatalf("want 2 matches, got %d", len(got))
	}
	if FilterMemoriesByText(memories, "") != nil {
		t.Fatalf("empty query should return nil")
	}
}

func TestRunManageMemory(t *testing.T) {
	tests := []struct {
		name    string
		content string
		seed    []MemoryEntry
		wantSub string
	}{
		{"no_store", "list", nil, "Memory manager not available"},
		{"list_empty", "list", nil, "No memories found."},
		{"add", "add\nlikes coffee", nil, "Memory added: [fact] likes coffee"},
		{"search_hit", "search\ncoffee", []MemoryEntry{{ID: "m1", Text: "likes coffee"}}, "Found 1 matching memories"},
		{"search_miss", "search\nmissing", nil, "No memories found matching 'missing'."},
		{"bad_action", "frobnicate", nil, "Unknown action"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			var store MemoryStore = &memStoreStub{entries: tc.seed}
			if tc.name == "no_store" {
				store = nil
			}
			res, _ := RunManageMemory(tc.content, store, nil, nil, "")
			if !strings.Contains(res.Results+res.Error, tc.wantSub) {
				t.Fatalf("output missing %q: results=%q error=%q", tc.wantSub, res.Results, res.Error)
			}
		})
	}
}

func TestRunManageMemory_VectorAndEvent(t *testing.T) {
	store := &memStoreStub{}
	vec := &memVecStub{healthy: true}
	bus := &eventStub{}
	addRes, _ := RunManageMemory("add\nhello", store, vec, bus, "alice")
	if len(vec.add) != 1 {
		t.Fatalf("vector add count = %d, want 1", len(vec.add))
	}
	if len(bus.fired) != 1 || bus.fired[0][0] != "memory_added" || bus.fired[0][1] != "alice" {
		t.Fatalf("event fired = %+v", bus.fired)
	}
	_ = addRes

	// Edit path: needs an existing entry.
	store.entries = []MemoryEntry{{ID: "m-xyz", Text: "old", Owner: "alice"}}
	editRes, _ := RunManageMemory("edit\nm-xy\nnew text", store, vec, nil, "alice")
	if !strings.Contains(editRes.Results, "Memory updated") {
		t.Fatalf("edit: %q", editRes.Results)
	}

	// Delete path.
	delRes, _ := RunManageMemory("delete\nm-xy", store, vec, nil, "alice")
	if !strings.Contains(delRes.Results, "deleted") {
		t.Fatalf("delete: %q", delRes.Results)
	}
}

func TestRunManageMemory_OwnerMismatch(t *testing.T) {
	store := &memStoreStub{entries: []MemoryEntry{{ID: "abc-1", Text: "x", Owner: "bob"}}}
	res, _ := RunManageMemory("edit\nabc-1\nnew", store, nil, nil, "alice")
	if !strings.Contains(res.Error, "not found") {
		t.Fatalf("want not found, got %q", res.Error)
	}
}

// ---------------------------------------------------------------------------
// RAG parser + driver
// ---------------------------------------------------------------------------

func TestParseRAGAction(t *testing.T) {
	tests := []struct {
		name    string
		content string
		action  string
		dir     string
		wantErr string
	}{
		{"empty", "", "", "", "No action specified"},
		{"list", "list", "list", "", ""},
		{"add", "add_directory\n/notes", "add_directory", "/notes", ""},
		{"add_no_path", "add_directory", "add_directory", "", "needs line 2"},
		{"remove", "remove_directory\n/notes", "remove_directory", "/notes", ""},
		{"unknown", "frobnicate", "frobnicate", "", "Unknown action"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseRAGAction(tc.content)
			if tc.wantErr != "" {
				if err == nil || !strings.Contains(err.Error(), tc.wantErr) {
					t.Fatalf("err = %v, want %q", err, tc.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got.Action != tc.action {
				t.Errorf("action = %q, want %q", got.Action, tc.action)
			}
			if got.Directory != tc.dir {
				t.Errorf("dir = %q, want %q", got.Directory, tc.dir)
			}
		})
	}
}

func TestExpandDirectory(t *testing.T) {
	// Pin HOME to an empty string for the duration of the test so the
	// process-level HOME inherited from the shell doesn't expand "~".
	// t.Setenv restores the original value when the test exits.
	t.Setenv("HOME", "")
	t.Setenv("USERPROFILE", "")
	tests := []struct {
		name string
		in   string
		env  string
		want string
	}{
		{"empty", "", "", ""},
		{"plain", "/etc", "", "/etc"},
		{"tilde_home", "~/x", "/home/u", "/home/u/x"},
		{"tilde_only", "~", "/home/u", "/home/u"},
		{"empty_home_tilde", "~/x", "", "~/x"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			if tc.env != "" {
				t.Setenv("HOME", tc.env)
			} else {
				t.Setenv("HOME", "")
			}
			got := ExpandDirectory(tc.in)
			if got != tc.want {
				t.Errorf("ExpandDirectory(%q) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}
}

func TestFormatRAGList(t *testing.T) {
	tests := []struct {
		name    string
		files   []any
		dirs    []string
		wantSub string
	}{
		{"empty", nil, nil, "No files or directories indexed in RAG."},
		{"dirs_only", nil, []string{"/a"}, "Indexed directories (1)"},
		{"files_only", []any{"a.txt"}, nil, "Indexed files (1)"},
		{"files_dict", []any{map[string]any{"name": "x"}}, nil, "x"},
		{"files_truncate", makeAny(51), nil, "... and 1 more"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := FormatRAGList(tc.files, tc.dirs)
			if !strings.Contains(got, tc.wantSub) {
				t.Errorf("missing %q in:\n%s", tc.wantSub, got)
			}
		})
	}
}

func makeAny(n int) []any {
	out := make([]any, n)
	for i := range out {
		out[i] = "f"
	}
	return out
}

func TestRunManageRAG(t *testing.T) {
	pdocs := pdocsStub{files: []any{"a.txt"}, dirs: []string{"/notes"}}
	rag := &ragStub{indexed: 3}
	tests := []struct {
		name    string
		content string
		wantSub string
		wantErr string
	}{
		{"list", "list", "Indexed files (1)", ""},
		{"add_no_rag", "add_directory\n~/notes", "", "RAG manager not available"},
		{"add_rag", "add_directory\n/notes", "3 files indexed", ""},
		{"remove", "remove_directory\n/notes", "removed from RAG index", ""},
		{"bad_action", "frobnicate", "", "Unknown action"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			var r RAGManager
			if strings.HasPrefix(tc.name, "add_rag") {
				r = rag
			}
			res, _ := RunManageRAG(tc.content, r, pdocs)
			out := res.Results + res.Error
			if tc.wantSub != "" && !strings.Contains(out, tc.wantSub) {
				t.Fatalf("missing %q in %q", tc.wantSub, out)
			}
			if tc.wantErr != "" && !strings.Contains(out, tc.wantErr) {
				t.Fatalf("missing err %q in %q", tc.wantErr, out)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// UI control parser + driver
// ---------------------------------------------------------------------------

func TestParseUIControlAction(t *testing.T) {
	got, err := ParseUIControlAction("toggle shell on")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.ActionName != "toggle" {
		t.Errorf("action = %q", got.ActionName)
	}
	if len(got.Parts) != 2 || got.Parts[0] != "shell" || got.Parts[1] != "on" {
		t.Errorf("parts = %v", got.Parts)
	}
	if _, err := ParseUIControlAction("   "); err == nil {
		t.Fatalf("want error on empty")
	}
}

func TestToggleEvent(t *testing.T) {
	resolver := func(spec, owner string) (ResolvedModel, error) { return ResolvedModel{}, nil }
	_ = resolver
	tests := []struct {
		name    string
		action  string
		wantEvt string
		wantSt  bool
		wantErr string
	}{
		{"on", "toggle shell on", "toggle", true, ""},
		{"alias_search", "toggle search off", "toggle", false, ""},
		{"unknown", "toggle foo on", "", false, "Unknown toggle"},
		{"missing_state", "toggle shell", "", false, "toggle needs"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			act, _ := ParseUIControlAction(tc.action)
			ev, err := ToggleEvent(act)
			if tc.wantErr != "" {
				if err == nil || !strings.Contains(err.Error(), tc.wantErr) {
					t.Fatalf("err = %v, want %q", err, tc.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected: %v", err)
			}
			if ev.UIEvent != tc.wantEvt {
				t.Errorf("event = %q", ev.UIEvent)
			}
			if ev.State == nil || *ev.State != tc.wantSt {
				t.Errorf("state = %v", ev.State)
			}
		})
	}
}

func TestSetModeEvent(t *testing.T) {
	act, _ := ParseUIControlAction("set_mode chat")
	ev, err := SetModeEvent(act)
	if err != nil || ev.Mode != "chat" {
		t.Fatalf("%v %+v", err, ev)
	}
	act, _ = ParseUIControlAction("set_mode foo")
	if _, err := SetModeEvent(act); err == nil {
		t.Fatalf("expected error")
	}
}

func TestSetThemeEvent(t *testing.T) {
	act, _ := ParseUIControlAction("set_theme cyberpunk")
	ev, _ := SetThemeEvent(act, nil)
	if ev.ThemeName != "cyberpunk" {
		t.Fatalf("theme = %q", ev.ThemeName)
	}
	act, _ = ParseUIControlAction("set_theme madeup")
	_, err := SetThemeEvent(act, map[string]any{"custom": map[string]any{}})
	if err == nil || !strings.Contains(err.Error(), "Unknown theme") {
		t.Fatalf("err = %v", err)
	}
}

func TestCreateThemeEvent(t *testing.T) {
	act, _ := ParseUIControlAction("create_theme my-theme #112233 #445566 #778899 #aabbcc #ddeeff userBubbleBg=#000001 bgPattern=dots frosted=true")
	ev, err := CreateThemeEvent(act)
	if err != nil {
		t.Fatalf("unexpected: %v", err)
	}
	if ev.ThemeName != "my-theme" {
		t.Errorf("theme = %q", ev.ThemeName)
	}
	if ev.Colors["bg"] != "#112233" {
		t.Errorf("bg = %v", ev.Colors["bg"])
	}
	if ev.BG["pattern"] != "dots" {
		t.Errorf("bg.pattern = %v", ev.BG["pattern"])
	}
	if ev.BG["frosted"] != true {
		t.Errorf("bg.frosted = %v", ev.BG["frosted"])
	}

	// bad hex
	act, _ = ParseUIControlAction("create_theme bad #zzzzzz #000000 #000000 #000000 #000000")
	if _, err := CreateThemeEvent(act); err == nil {
		t.Fatalf("expected hex validation error")
	}
	// bad bgPattern
	act, _ = ParseUIControlAction("create_theme bad #000000 #000000 #000000 #000000 #000000 bgPattern=mystery")
	if _, err := CreateThemeEvent(act); err == nil {
		t.Fatalf("expected bgPattern error")
	}
	// too few tokens
	act, _ = ParseUIControlAction("create_theme short")
	if _, err := CreateThemeEvent(act); err == nil {
		t.Fatalf("expected length error")
	}
}

func TestHighlightAndClear(t *testing.T) {
	act, _ := ParseUIControlAction("highlight .chat-bubble New message")
	ev, err := HighlightEvent(act)
	if err != nil {
		t.Fatalf("err = %v", err)
	}
	if ev.Selector != ".chat-bubble" || ev.Label != "New message" {
		t.Fatalf("selector=%q label=%q", ev.Selector, ev.Label)
	}
	if ClearHighlightEvent().UIEvent != "clear_highlight" {
		t.Fatalf("clear event mismatch")
	}
}

func TestOpenPanelEvent(t *testing.T) {
	tests := []struct {
		name    string
		in      string
		want    string
		wantErr string
	}{
		{"ok", "open_panel gallery", "gallery", ""},
		{"alias", "open_panel brain", "memories", ""},
		{"unknown", "open_panel foo", "", "Unknown panel"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			act, _ := ParseUIControlAction(tc.in)
			ev, err := OpenPanelEvent(act)
			if tc.wantErr != "" {
				if err == nil || !strings.Contains(err.Error(), tc.wantErr) {
					t.Fatalf("err = %v", err)
				}
				return
			}
			if ev.Panel != tc.want {
				t.Errorf("panel = %q, want %q", ev.Panel, tc.want)
			}
		})
	}
}

func TestOpenEmailReplyEvent(t *testing.T) {
	tests := []struct {
		name     string
		in       string
		wantUID  string
		wantMode string
		wantBody string
		wantErr  string
	}{
		{"ok", "open_email_reply 42 INBOX reply hello there", "42", "reply", "hello there", ""},
		{"ai_reply_no_body_ok", "open_email_reply 99 INBOX ai-reply", "99", "ai-reply", "", ""},
		{"multi_line_body", "open_email_reply 7\nthis is line one\nline two", "7", "reply", "this is line one\nline two", ""},
		{"empty_body", "open_email_reply 1 INBOX reply", "1", "reply", "", "REQUIRES a body"},
		{"bad_mode", "open_email_reply 1 INBOX weirdmode hello", "1", "reply", "hello", ""},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			act, _ := ParseUIControlAction(tc.in)
			ev, err := OpenEmailReplyEvent(act)
			if tc.wantErr != "" {
				if err == nil || !strings.Contains(err.Error(), tc.wantErr) {
					t.Fatalf("err = %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected: %v", err)
			}
			if ev.UID != tc.wantUID || ev.ModeReply != tc.wantMode {
				t.Errorf("uid=%q mode=%q", ev.UID, ev.ModeReply)
			}
			if ev.Body != tc.wantBody {
				t.Errorf("body=%q, want %q", ev.Body, tc.wantBody)
			}
		})
	}
}

func TestSwitchModelEvent(t *testing.T) {
	resolver := func(spec, owner string) (ResolvedModel, error) {
		return ResolvedModel{EndpointURL: "https://x/v1/chat/completions", ModelID: spec, Headers: map[string]string{"Authorization": "Bearer x"}}, nil
	}
	act, _ := ParseUIControlAction("switch_model gpt-4")
	ev, err := SwitchModelEvent(act, "sess-1", "alice", resolver)
	if err != nil {
		t.Fatalf("unexpected: %v", err)
	}
	if ev.Model != "gpt-4" {
		t.Errorf("model = %q", ev.Model)
	}
	act, _ = ParseUIControlAction("switch_model")
	if _, err := SwitchModelEvent(act, "", "", resolver); err == nil {
		t.Fatalf("expected error when model missing")
	}
	// resolver error path
	badResolver := func(spec, owner string) (ResolvedModel, error) {
		return ResolvedModel{}, errBoom
	}
	act, _ = ParseUIControlAction("switch_model missing-model")
	if _, err := SwitchModelEvent(act, "", "", badResolver); err == nil {
		t.Fatalf("expected resolver error")
	}
}

func TestBuildUIControlEvent_Unknown(t *testing.T) {
	_, err := BuildUIControlEvent("frobnicate x", UIControlOptions{})
	if err == nil {
		t.Fatalf("expected unknown action error")
	}
}

func TestGetTogglesEvent(t *testing.T) {
	if !strings.Contains(GetTogglesEvent().Results, "client-side") {
		t.Fatalf("get_toggles text missing")
	}
}

func TestRunUIControl_Smoke(t *testing.T) {
	resolver := func(spec, owner string) (ResolvedModel, error) { return ResolvedModel{ModelID: spec}, nil }
	for _, in := range []string{"toggle shell on", "highlight .x", "clear_highlight"} {
		out, _ := RunUIControl(in, UIControlOptions{Resolver: resolver})
		if out.Results == "" {
			t.Errorf("empty result for %q", in)
		}
	}
}

// ---------------------------------------------------------------------------
// Image parser + classifier
// ---------------------------------------------------------------------------

func TestParseImageRequest(t *testing.T) {
	tests := []struct {
		name    string
		in      string
		want    ImageRequest
		wantErr string
	}{
		{"all", "prompt\nmodel\n1536x1024\nhigh",
			ImageRequest{Prompt: "prompt", Model: "model", Size: "1536x1024", Quality: "high"}, ""},
		{"defaults", "hello",
			ImageRequest{Prompt: "hello", Size: "1024x1024", Quality: "medium"}, ""},
		{"empty", "", ImageRequest{}, "Image prompt is required"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseImageRequest(tc.in)
			if tc.wantErr != "" {
				if err == nil || !strings.Contains(err.Error(), tc.wantErr) {
					t.Fatalf("err = %v", err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected: %v", err)
			}
			if *got != tc.want {
				t.Errorf("got %+v, want %+v", *got, tc.want)
			}
		})
	}
}

func TestClassifyImageModel(t *testing.T) {
	tests := []struct {
		model      string
		gpt, dalle bool
		local      bool
	}{
		{"gpt-image-1", true, false, false},
		{"GPT-IMAGE-1.5", true, false, false},
		{"dall-e-3", false, true, false},
		{"sd-xl", false, false, true},
	}
	for _, tc := range tests {
		g, d, l := ClassifyImageModel(tc.model)
		if g != tc.gpt || d != tc.dalle || l != tc.local {
			t.Errorf("%s: got (%v,%v,%v) want (%v,%v,%v)", tc.model, g, d, l, tc.gpt, tc.dalle, tc.local)
		}
	}
}

func TestNormalizeImageSize(t *testing.T) {
	if NormalizeImageSize("garbage", true, false) != "1024x1024" {
		t.Errorf("gpt bad size should default")
	}
	if NormalizeImageSize("garbage", false, true) != "1024x1024" {
		t.Errorf("dalle bad size should default")
	}
	if NormalizeImageSize("anything", false, false) != "anything" {
		t.Errorf("local diff should accept any size")
	}
	if NormalizeImageSize("1536x1024", true, false) != "1536x1024" {
		t.Errorf("gpt good size should pass")
	}
}

func TestNormalizeImageQuality(t *testing.T) {
	if NormalizeImageQuality("high", false, false) != "" {
		t.Errorf("dalle should strip quality")
	}
	if NormalizeImageQuality("garbage", true, false) != "medium" {
		t.Errorf("gpt bad quality should default medium")
	}
	if NormalizeImageQuality("high", true, false) != "high" {
		t.Errorf("gpt good quality should pass")
	}
}

func TestImageAPIPayload(t *testing.T) {
	p := ImageAPIPayload("gpt-image-1", "p", "1024x1024", "high", true, false, false)
	if p["quality"] != "high" {
		t.Errorf("gpt should include quality")
	}
	p = ImageAPIPayload("dall-e-3", "p", "1024x1024", "high", false, true, false)
	if _, ok := p["quality"]; ok {
		t.Errorf("dalle should omit quality")
	}
	p = ImageAPIPayload("sd", "p", "1024x1024", "", false, false, true)
	if p["quality"] != "medium" {
		t.Errorf("local diff empty quality should default medium")
	}
}

func TestDecodeBase64Image(t *testing.T) {
	// "hello" base64 -> "aGVsbG8="
	got, err := DecodeBase64Image("aGVsbG8=")
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if string(got) != "hello" {
		t.Errorf("got %q", got)
	}
}

// ---------------------------------------------------------------------------
// Dispatcher / stream
// ---------------------------------------------------------------------------

func TestDispatchTool(t *testing.T) {
	resolver := func(spec, owner string) (ResolvedModel, error) {
		return ResolvedModel{EndpointURL: "https://x", ModelID: spec, Headers: map[string]string{}}, nil
	}
	llm := func(ctx ctxAlias, url, model string, headers map[string]string, msgs []ChatMessage, to int) (string, error) {
		return "out:" + model, nil
	}
	deps := DriverDeps{
		Resolver:    resolver,
		LLM:         llm,
		MemoryStore: &memStoreStub{},
		Prefs:       prefsStub{themes: map[string]any{}},
	}

	desc, res := DispatchTool("pipeline", "gpt-4 | x", "", "", deps)
	if !strings.HasPrefix(desc, "pipeline:") {
		t.Errorf("desc = %q", desc)
	}
	if res.FinalOutput != "out:gpt-4" {
		t.Errorf("final = %q", res.FinalOutput)
	}

	desc, res = DispatchTool("manage_memory", "list", "", "", deps)
	if !strings.HasPrefix(desc, "manage_memory:") {
		t.Errorf("desc = %q", desc)
	}

	desc, res = DispatchTool("ui_control", "toggle shell on", "", "", deps)
	if !strings.HasPrefix(desc, "ui_control:") {
		t.Errorf("desc = %q", desc)
	}

	desc, res = DispatchTool("unknown", "x", "", "", deps)
	if res.Error == "" {
		t.Errorf("expected error")
	}
	if !strings.Contains(desc, "unknown") {
		t.Errorf("desc = %q", desc)
	}
}

func TestStreamTool(t *testing.T) {
	resolver := func(spec, owner string) (ResolvedModel, error) {
		return ResolvedModel{ModelID: spec, Headers: map[string]string{}}, nil
	}
	llm := func(ctx ctxAlias, url, model string, headers map[string]string, msgs []ChatMessage, to int) (string, error) {
		return "x", nil
	}
	deps := DriverDeps{Resolver: resolver, LLM: llm}
	ch := StreamTool("pipeline", "gpt-4 | x", "", "", deps)
	var count int
	for ev := range ch {
		count++
		if !ev.Final {
			t.Errorf("expected final event")
		}
	}
	if count != 1 {
		t.Errorf("want 1 event, got %d", count)
	}
}

// ---------------------------------------------------------------------------
// Resolver helper (used by RunUIControl smoke tests above)
// ---------------------------------------------------------------------------

func TestResolveModel_OpenRouter(t *testing.T) {
	store := fakeStore{eps: []EndpointRecord{
		{Name: "or", BaseURL: "https://openrouter.ai/api/v1", CachedModels: []string{"qwen/qwen-2.5"}},
	}}
	rt := func(r EndpointRecord, owner string) (string, string, error) { return r.BaseURL, "or-key", nil }
	res, err := ResolveModel("qwen", ResolveOptions{Store: store, Runtime: rt})
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if res.Headers["HTTP-Referer"] == "" {
		t.Errorf("expected openrouter header")
	}
}
