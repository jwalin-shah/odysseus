package aiint

import (
	"context"
	"errors"
	"strings"
	"testing"
)

// stubLLM captures the messages + model passed to Complete and returns
// canned responses in order.
type stubLLM struct {
	calls     int
	models    []string
	responses []string
}

func (s *stubLLM) Complete(_ context.Context, _, modelID string, _ map[string]string, _ []ChatMessage) (string, error) {
	s.calls++
	s.models = append(s.models, modelID)
	if len(s.responses) > 0 {
		resp := s.responses[0]
		s.responses = s.responses[1:]
		return resp, nil
	}
	return "stub-out", nil
}

// stubResolver2 is used by Dispatch tests so we don't pull in ui_control's
// type. It accepts any spec and returns the spec as the resolved model id.
type stubResolver2 struct{ err error }

func (s *stubResolver2) Resolve(_ context.Context, spec, _ string) (ResolvedModel, error) {
	if s.err != nil {
		return ResolvedModel{}, s.err
	}
	return ResolvedModel{URL: "http://stub/v1/chat/completions", ModelID: spec, Headers: map[string]string{}}, nil
}

// stubImage is a deterministic ImageRunner.
type stubImage struct {
	out ImageResult
	err error
}

func (s *stubImage) Generate(_ context.Context, prompt, _, _, _, _ string) (ImageResult, error) {
	if s.err != nil {
		return ImageResult{}, s.err
	}
	if s.out.Prompt == "" {
		s.out.Prompt = prompt
	}
	return s.out, nil
}

func TestDispatch_UnknownTool(t *testing.T) {
	desc, result, err := Dispatch("not_a_tool", "anything", &Manager{})
	if err != nil {
		t.Fatalf("unknown tool should not return err, got %v", err)
	}
	if result.OK {
		t.Fatalf("expected ok=false, got %+v", result)
	}
	if !strings.Contains(result.Error, "Unknown AI interaction tool") {
		t.Fatalf("expected unknown-tool error, got %q", result.Error)
	}
	if !strings.Contains(desc, "unknown ai tool") {
		t.Fatalf("expected 'unknown ai tool' desc, got %q", desc)
	}
}

func TestDispatch_ManageMemory_NoManager(t *testing.T) {
	desc, result, err := Dispatch("manage_memory", "list", &Manager{})
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if !strings.Contains(result.Error, "Memory manager not available") {
		t.Fatalf("expected 'Memory manager not available', got %q", result.Error)
	}
	if !strings.Contains(desc, "manage_memory") {
		t.Fatalf("expected desc to mention manage_memory, got %q", desc)
	}
}

func TestDispatch_ManageMemory_WithManager(t *testing.T) {
	mgr := &Manager{Memory: newMemMgr(MemoryEntry{ID: "abc12345", Text: "go", Category: "fact", Owner: "alice"})}
	desc, result, _ := Dispatch("manage_memory", "list", mgr)
	if !result.OK {
		t.Fatalf("expected ok=true, got %+v", result)
	}
	if !strings.Contains(result.Results, "go") {
		t.Fatalf("expected 'go' in list, got %q", result.Results)
	}
	if !strings.Contains(desc, "manage_memory: list") {
		t.Fatalf("expected manage_memory:list desc, got %q", desc)
	}
}

func TestDispatch_ManageRAG_List_NoPDocs(t *testing.T) {
	mgr := &Manager{RAG: &stubRAG{}}
	_, result, _ := Dispatch("manage_rag", "list", mgr)
	if !result.OK {
		t.Fatalf("expected ok=true with informational message, got %+v", result)
	}
}

func TestDispatch_UIControl_Panel(t *testing.T) {
	_, result, _ := Dispatch("ui_control", "open_panel memories", &Manager{})
	if !result.OK {
		t.Fatalf("expected ok=true, got %+v", result)
	}
	if result.Details["panel"] != "memories" {
		t.Fatalf("expected panel=memories, got %v", result.Details["panel"])
	}
}

func TestDispatch_GenerateImage_NoRunner_ErrUnsupported(t *testing.T) {
	_, _, err := Dispatch("generate_image", "prompt", &Manager{})
	if !errors.Is(err, ErrUnsupported) {
		t.Fatalf("expected ErrUnsupported, got %v", err)
	}
}

func TestDispatch_GenerateImage_WithRunner(t *testing.T) {
	runner := &stubImage{out: ImageResult{URL: "/img.png", ID: "img-1", Model: "gpt-image-1", Size: "1024x1024", Quality: "medium", Summary: "Generated"}}
	mgr := &Manager{Image: runner}
	_, result, err := Dispatch("generate_image", "a foggy mountain", mgr)
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if !result.OK {
		t.Fatalf("expected ok=true, got %+v", result)
	}
	if result.Details["image_url"] != "/img.png" {
		t.Fatalf("expected image_url in details, got %+v", result.Details)
	}
}

func TestDispatch_Pipeline_Success(t *testing.T) {
	llm := &stubLLM{responses: []string{"first output", "second output"}}
	mgr := &Manager{LLM: llm, Resolver: &stubResolver2{}}
	content := `{"steps":[{"model":"a","instruction":"first"},{"model":"b","instruction":"second"}]}`
	_, result, _ := Dispatch("pipeline", content, mgr)
	if !result.OK {
		t.Fatalf("expected ok=true, got %+v", result)
	}
	if llm.calls != 2 {
		t.Fatalf("expected 2 LLM calls, got %d", llm.calls)
	}
	if !strings.Contains(result.Results, "Pipeline Results") {
		t.Fatalf("expected pipeline markdown, got %q", result.Results[:200])
	}
	if !strings.Contains(result.Results, "first output") || !strings.Contains(result.Results, "second output") {
		t.Fatalf("expected both outputs in markdown, got %q", result.Results)
	}
}

func TestDispatch_Pipeline_ResolverMissing(t *testing.T) {
	mgr := &Manager{LLM: &stubLLM{}}
	_, result, _ := Dispatch("pipeline", "a | do thing", mgr)
	if result.OK {
		t.Fatalf("expected ok=false without resolver, got %+v", result)
	}
	if !strings.Contains(result.Error, "Resolver") {
		t.Fatalf("expected resolver-required error, got %q", result.Error)
	}
}

func TestDispatch_Pipeline_LineFormat(t *testing.T) {
	llm := &stubLLM{responses: []string{"ok"}}
	mgr := &Manager{LLM: llm, Resolver: &stubResolver2{}}
	_, result, _ := Dispatch("pipeline", "model-a | do thing", mgr)
	if !result.OK {
		t.Fatalf("expected ok, got %+v", result)
	}
}

func TestDispatch_Pipeline_NoSteps(t *testing.T) {
	mgr := &Manager{LLM: &stubLLM{}, Resolver: &stubResolver2{}}
	_, result, _ := Dispatch("pipeline", "", mgr)
	if result.OK {
		t.Fatalf("expected ok=false for empty content, got %+v", result)
	}
}

func TestDispatch_Pipeline_LLMErrors(t *testing.T) {
	llm := &errLLM{}
	mgr := &Manager{LLM: llm, Resolver: &stubResolver2{}}
	_, result, _ := Dispatch("pipeline", "a | do thing", mgr)
	if result.OK {
		t.Fatalf("expected ok=false on LLM error, got %+v", result)
	}
	if !strings.Contains(result.Error, "Pipeline failed at step") {
		t.Fatalf("expected pipeline failure message, got %q", result.Error)
	}
}

type errLLM struct{}

func (errLLM) Complete(_ context.Context, _, _ string, _ map[string]string, _ []ChatMessage) (string, error) {
	return "", errors.New("boom")
}
