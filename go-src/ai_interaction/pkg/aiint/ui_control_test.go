package aiint

import (
	"context"
	"fmt"
	"strings"
	"testing"
)

func TestUIControl_Toggle_OnAndOff(t *testing.T) {
	r, err := UIControl("toggle web on", nil, nil)
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if r.Details["toggle_name"] != "web" || r.Details["state"] != true {
		t.Fatalf("unexpected toggle detail: %+v", r.Details)
	}
	if !strings.Contains(r.Results, "set to on") {
		t.Fatalf("expected 'set to on' in results, got %q", r.Results)
	}

	r, _ = UIControl("toggle web off", nil, nil)
	if r.Details["state"] != false || !strings.Contains(r.Results, "set to off") {
		t.Fatalf("unexpected off result %+v", r)
	}
}

func TestUIControl_Toggle_Aliases(t *testing.T) {
	cases := []struct{ alias, canonical string }{
		{"shell", "bash"},
		{"terminal", "bash"},
		{"search", "web"},
		{"websearch", "web"},
		{"web_search", "web"},
		{"deepresearch", "research"},
		{"deep_research", "research"},
		{"documents", "document_editor"},
		{"doc", "document_editor"},
		{"docs", "document_editor"},
		{"private", "incognito"},
	}
	for _, c := range cases {
		r, _ := UIControl("toggle "+c.alias+" on", nil, nil)
		if !r.OK {
			t.Fatalf("alias %q should resolve to %q, got error %q", c.alias, c.canonical, r.Error)
		}
		if r.Details["toggle_name"] != c.canonical {
			t.Fatalf("alias %q expected canonical %q, got %q", c.alias, c.canonical, r.Details["toggle_name"])
		}
	}
}

func TestUIControl_Toggle_Unknown(t *testing.T) {
	r, _ := UIControl("toggle bogus on", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "Unknown toggle") {
		t.Fatalf("expected 'Unknown toggle', got %q", r.Error)
	}
}

func TestUIControl_Toggle_TruthyValues(t *testing.T) {
	for _, v := range []string{"on", "true", "1", "yes", "enable", "enabled"} {
		r, _ := UIControl("toggle web "+v, nil, nil)
		if !r.OK || r.Details["state"] != true {
			t.Fatalf("expected truthy for %q, got %+v", v, r)
		}
	}
}

func TestUIControl_SetMode_Valid(t *testing.T) {
	r, _ := UIControl("set_mode agent", nil, nil)
	if !r.OK || r.Details["mode"] != "agent" {
		t.Fatalf("expected agent mode, got %+v", r)
	}
	r, _ = UIControl("set_mode chat", nil, nil)
	if !r.OK || r.Details["mode"] != "chat" {
		t.Fatalf("expected chat mode, got %+v", r)
	}
}

func TestUIControl_SetMode_Invalid(t *testing.T) {
	r, _ := UIControl("set_mode banana", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "Invalid mode") {
		t.Fatalf("expected 'Invalid mode', got %q", r.Error)
	}
}

func TestUIControl_SetMode_Missing(t *testing.T) {
	r, _ := UIControl("set_mode", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
}

// stubResolver is a deterministic ModelResolver for switch_model tests.
type stubResolver struct {
	spec     string
	resolved ResolvedModel
	err      error
}

func (s *stubResolver) Resolve(_ context.Context, spec, _ string) (ResolvedModel, error) {
	s.spec = spec
	if s.err != nil {
		return ResolvedModel{}, s.err
	}
	return s.resolved, nil
}

func TestUIControl_SwitchModel_Success(t *testing.T) {
	res := &stubResolver{resolved: ResolvedModel{
		URL:     "https://api.openai.com/v1/chat/completions",
		ModelID: "gpt-4o",
		Headers: map[string]string{"Authorization": "Bearer x"},
	}}
	mgr := &Manager{Resolver: res}
	r, err := UIControl("switch_model gpt-4o", mgr, nil)
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if res.spec != "gpt-4o" {
		t.Fatalf("expected resolver to receive 'gpt-4o', got %q", res.spec)
	}
	if r.Details["model"] != "gpt-4o" {
		t.Fatalf("expected model in detail, got %+v", r.Details)
	}
}

func TestUIControl_SwitchModel_ResolverError(t *testing.T) {
	res := &stubResolver{err: fmt.Errorf("model not found")}
	mgr := &Manager{Resolver: res}
	r, _ := UIControl("switch_model ghost", mgr, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "model not found") {
		t.Fatalf("expected resolver error in result, got %q", r.Error)
	}
}

func TestUIControl_SetTheme_Known(t *testing.T) {
	r, _ := UIControl("set_theme dark", nil, nil)
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	if r.Details["theme_name"] != "dark" {
		t.Fatalf("unexpected theme_name: %v", r.Details["theme_name"])
	}
}

func TestUIControl_SetTheme_CustomTheme(t *testing.T) {
	r, _ := UIControl("set_theme mybrand", nil, []string{"mybrand", "another"})
	if !r.OK {
		t.Fatalf("expected ok with custom theme, got %+v", r)
	}
}

func TestUIControl_SetTheme_Unknown(t *testing.T) {
	r, _ := UIControl("set_theme madeup", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "Unknown theme") {
		t.Fatalf("expected 'Unknown theme', got %q", r.Error)
	}
}

func TestUIControl_CreateTheme_ValidHex(t *testing.T) {
	r, _ := UIControl("create_theme test #112233 #445566 #778899 #aabbcc #ddeeff", nil, nil)
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	if r.Details["theme_name"] != "test" {
		t.Fatalf("unexpected theme name: %v", r.Details["theme_name"])
	}
	colors := r.Details["colors"].(map[string]string)
	for _, k := range []string{"bg", "fg", "panel", "border", "red"} {
		if !strings.HasPrefix(colors[k], "#") || len(colors[k]) != 7 {
			t.Fatalf("color %s malformed: %q", k, colors[k])
		}
	}
}

func TestUIControl_CreateTheme_InvalidHex(t *testing.T) {
	r, _ := UIControl("create_theme bad nothex #445566 #778899 #aabbcc #ddeeff", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "Invalid hex color") {
		t.Fatalf("expected 'Invalid hex color', got %q", r.Error)
	}
}

func TestUIControl_CreateTheme_AdvancedKeys(t *testing.T) {
	r, _ := UIControl("create_theme adv #112233 #445566 #778899 #aabbcc #ddeeff userBubbleBg=#000001 aiBubbleBg=#000002", nil, nil)
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	colors := r.Details["colors"].(map[string]string)
	if colors["userBubbleBg"] != "#000001" || colors["aiBubbleBg"] != "#000002" {
		t.Fatalf("expected advanced keys in colors, got %+v", colors)
	}
}

func TestUIControl_CreateTheme_BgPattern(t *testing.T) {
	r, _ := UIControl("create_theme fx #112233 #445566 #778899 #aabbcc #ddeeff bgPattern=dots bgEffectIntensity=2 bgEffectSize=0.5 frosted=true", nil, nil)
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	bg, ok := r.Details["bg"].(map[string]any)
	if !ok {
		t.Fatalf("expected bg map, got %T", r.Details["bg"])
	}
	if bg["pattern"] != "dots" {
		t.Fatalf("expected pattern=dots, got %v", bg["pattern"])
	}
	if bg["effectIntensity"].(float64) != 2 {
		t.Fatalf("expected effectIntensity=2, got %v", bg["effectIntensity"])
	}
	if bg["frosted"] != true {
		t.Fatalf("expected frosted=true, got %v", bg["frosted"])
	}
	if !strings.Contains(r.Results, "background effect") {
		t.Fatalf("expected background-effect summary, got %q", r.Results)
	}
}

func TestUIControl_CreateTheme_BgPatternInvalid(t *testing.T) {
	r, _ := UIControl("create_theme bad #112233 #445566 #778899 #aabbcc #ddeeff bgPattern=glitter", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false for invalid pattern, got %+v", r)
	}
	if !strings.Contains(r.Error, "Invalid bgPattern") {
		t.Fatalf("expected 'Invalid bgPattern', got %q", r.Error)
	}
}

func TestUIControl_Highlight_MissingSelector(t *testing.T) {
	r, _ := UIControl("highlight", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "highlight needs") {
		t.Fatalf("expected helpful error, got %q", r.Error)
	}
}

func TestUIControl_Highlight_WithLabel(t *testing.T) {
	r, _ := UIControl("highlight .toolbar my-label", nil, nil)
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	if r.Details["selector"] != ".toolbar" {
		t.Fatalf("expected selector .toolbar, got %v", r.Details["selector"])
	}
	if r.Details["label"] != "my-label" {
		t.Fatalf("expected label 'my-label', got %v", r.Details["label"])
	}
}

func TestUIControl_ClearHighlight(t *testing.T) {
	r, _ := UIControl("clear_highlight", nil, nil)
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	if r.Details["ui_event"] != "clear_highlight" {
		t.Fatalf("unexpected ui_event: %v", r.Details["ui_event"])
	}
}

func TestUIControl_OpenPanel_Aliases(t *testing.T) {
	cases := []struct{ in, want string }{
		{"documents", "documents"}, {"doc", "documents"}, {"library", "documents"},
		{"gallery", "gallery"}, {"images", "gallery"},
		{"email", "email"}, {"inbox", "email"}, {"mail", "email"},
		{"sessions", "sessions"}, {"chats", "sessions"},
		{"notes", "notes"}, {"todo", "notes"},
		{"memories", "memories"}, {"memory", "memories"}, {"brain", "memories"},
		{"skills", "skills"},
		{"settings", "settings"}, {"preferences", "settings"},
		{"cookbook", "cookbook"}, {"models", "cookbook"}, {"llm", "cookbook"},
	}
	for _, c := range cases {
		r, _ := UIControl("open_panel "+c.in, nil, nil)
		if !r.OK {
			t.Fatalf("alias %q should resolve to %q, got error %q", c.in, c.want, r.Error)
		}
		if r.Details["panel"] != c.want {
			t.Fatalf("alias %q expected panel %q, got %q", c.in, c.want, r.Details["panel"])
		}
	}
}

func TestUIControl_OpenPanel_Invalid(t *testing.T) {
	r, _ := UIControl("open_panel nonsense", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "Unknown panel") {
		t.Fatalf("expected 'Unknown panel', got %q", r.Error)
	}
}

func TestUIControl_OpenEmailReply_MissingBodyNonAI(t *testing.T) {
	r, _ := UIControl("open_email_reply 42 INBOX reply", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false (body required), got %+v", r)
	}
	if !strings.Contains(r.Error, "REQUIRES a body") {
		t.Fatalf("expected body-required error, got %q", r.Error)
	}
}

func TestUIControl_OpenEmailReply_AcceptsAIWithoutBody(t *testing.T) {
	r, _ := UIControl("open_email_reply 42 INBOX ai-reply", nil, nil)
	if !r.OK {
		t.Fatalf("expected ok for ai-reply without body, got %+v", r)
	}
	if r.Details["mode"] != "ai-reply" {
		t.Fatalf("expected mode=ai-reply, got %v", r.Details["mode"])
	}
}

func TestUIControl_OpenEmailReply_AcceptsBodyForReply(t *testing.T) {
	r, _ := UIControl("open_email_reply 42 INBOX reply\nHello back!", nil, nil)
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	if r.Details["body"] != "Hello back!" {
		t.Fatalf("expected body 'Hello back!', got %v", r.Details["body"])
	}
}

func TestUIControl_OpenEmailReply_MissingUID(t *testing.T) {
	r, _ := UIControl("open_email_reply", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "needs:") {
		t.Fatalf("expected helpful error, got %q", r.Error)
	}
}

func TestUIControl_GetToggles(t *testing.T) {
	r, _ := UIControl("get_toggles", nil, nil)
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	if !strings.Contains(r.Results, "Available toggles") {
		t.Fatalf("expected toggle-state passthrough, got %q", r.Results)
	}
}

func TestUIControl_Empty(t *testing.T) {
	r, _ := UIControl("", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "No action specified") {
		t.Fatalf("expected 'No action specified', got %q", r.Error)
	}
}

func TestUIControl_Unknown(t *testing.T) {
	r, _ := UIControl("frobnicate", nil, nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "Unknown action") {
		t.Fatalf("expected 'Unknown action', got %q", r.Error)
	}
}
