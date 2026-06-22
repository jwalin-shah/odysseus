package aiinteraction

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// ParseUIControlAction mirrors the first-line split do_ui_control does:
//
//	parts = lines[0].strip().split(None, 2)
//
// The Go port exposes the raw split (no 2-token cap; per-action
// functions re-split as needed) and the trimmed Lines so callers can
// implement each action's body without re-tokenising.
//
// Most actions re-split `parts[0]` themselves with various limits; this
// helper exposes the un-split first line so callers can mirror the
// Python source's `lines[0].strip().split(None, 2)` faithfully.
func ParseUIControlAction(content string) (*UIControlAction, error) {
	trimmed := strings.TrimSpace(content)
	if trimmed == "" {
		return nil, fmt.Errorf("error: No action specified")
	}
	rawLines := strings.Split(trimmed, "\n")
	lines := make([]string, len(rawLines))
	for i, l := range rawLines {
		lines[i] = strings.TrimSpace(l)
	}
	first := lines[0]
	// First token is the action; remainder is the args.
	tokens := strings.Fields(first)
	if len(tokens) == 0 {
		return nil, fmt.Errorf("error: No action specified")
	}
	action := strings.ToLower(tokens[0])
	parts := append([]string{}, tokens[1:]...)
	args := strings.TrimSpace(first[len(tokens[0]):])
	return &UIControlAction{
		ActionName: action,
		Args:       args,
		Parts:      parts,
		Lines:      lines,
	}, nil
}

// ToggleEvent parses the "toggle" action. Mirrors the inline body in
// do_ui_control: resolve aliases, validate the toggle name, parse the
// state from a tristate set, and emit the corresponding UIControlEvent.
func ToggleEvent(action *UIControlAction) (*UIControlEvent, error) {
	if len(action.Parts) < 2 {
		return nil, fmt.Errorf("error: toggle needs: toggle <name> <on|off>")
	}
	rawName := strings.ToLower(action.Parts[0])
	stateStr := strings.ToLower(action.Parts[1])
	state := Truthy(stateStr)
	canonical := ToggleAliases[rawName]
	if canonical == "" {
		canonical = rawName
	}
	if !KnownToggle(canonical) {
		return nil, fmt.Errorf("error: Unknown toggle '%s'. Valid: %s", rawName, strings.Join(KnownToggles, ", "))
	}
	stateOut := state
	return &UIControlEvent{
		UIEvent:    "toggle",
		ToggleName: canonical,
		State:      &stateOut,
		Results:    fmt.Sprintf("Toggle '%s' set to %s", canonical, onOff(stateOut)),
	}, nil
}

// SetModeEvent parses the "set_mode" action.
func SetModeEvent(action *UIControlAction) (*UIControlEvent, error) {
	if len(action.Parts) < 1 {
		return nil, fmt.Errorf("error: set_mode needs: set_mode <agent|chat>")
	}
	mode := strings.ToLower(action.Parts[0])
	if mode != "agent" && mode != "chat" {
		return nil, fmt.Errorf("error: Invalid mode '%s'. Use: agent, chat", mode)
	}
	return &UIControlEvent{
		UIEvent: "set_mode",
		Mode:    mode,
		Results: fmt.Sprintf("Mode changed to '%s'", mode),
	}, nil
}

// SetThemeEvent parses the "set_theme" action. The Python source reads
// user-defined custom themes from routes.prefs_routes._load(); the Go
// port accepts a CustomThemes map the caller supplies so tests don't
// have to wire a prefs route.
func SetThemeEvent(action *UIControlAction, customThemes map[string]any) (*UIControlEvent, error) {
	if len(action.Parts) < 1 {
		return nil, fmt.Errorf("error: set_theme needs: set_theme <preset>")
	}
	name := strings.ToLower(action.Parts[0])
	if !KnownTheme(name) {
		extra := ""
		if len(customThemes) > 0 {
			keys := make([]string, 0, len(customThemes))
			for k := range customThemes {
				keys = append(keys, k)
			}
			extra = " | Custom: " + strings.Join(keys, ", ")
		}
		return nil, fmt.Errorf("error: Unknown theme '%s'. Available: %s%s", name, strings.Join(KnownThemePresets, ", "), extra)
	}
	return &UIControlEvent{
		UIEvent:   "set_theme",
		ThemeName: name,
		Results:   fmt.Sprintf("Theme changed to '%s'", name),
	}, nil
}

// CreateThemeEvent parses the "create_theme" action. Mirrors the
// inline body in do_ui_control: at least 7 positional tokens, hex
// color validation, optional advanced key=val pairs, optional
// background-effect key=val pairs.
//
// The Python source re-splits lines[0] without a splitlimit so the
// caller passes action.Lines[0] already un-split — this helper
// re-splits the raw line via fieldsFunc-split so it preserves the
// key=val tokens (which contain "=").
func CreateThemeEvent(action *UIControlAction) (*UIControlEvent, error) {
	raw := ""
	if len(action.Lines) > 0 {
		raw = action.Lines[0]
	}
	tokens := strings.Fields(raw)
	if len(tokens) < 7 {
		return nil, fmt.Errorf("error: create_theme needs: create_theme <name> <bg> <fg> <panel> <border> <accent> (all hex colors). Optional advanced color key=value pairs (userBubbleBg, aiBubbleBg, bubbleBorder, sidebarBg, sectionAccent, brandColor, inputBg, inputBorder, sendBtnBg, sendBtnHover, codeBg, codeFg, toggleBg, toggleActive, accentPrimary, accentError). Optional background EFFECTS: bgPattern=<none|dots|synapse|rain|constellations|perlin-flow|petals|sparkles|embers>, bgEffectColor=#RRGGBB, bgEffectIntensity=<num e.g. 1>, bgEffectSize=<num e.g. 1>, frosted=true|false")
	}
	name := strings.ToLower(strings.ReplaceAll(tokens[1], " ", "-"))
	colors := map[string]any{
		"bg":     tokens[2],
		"fg":     tokens[3],
		"panel":  tokens[4],
		"border": tokens[5],
		"red":    tokens[6],
	}
	for k, v := range colors {
		if !hexColorPattern.MatchString(v.(string)) {
			return nil, fmt.Errorf("error: Invalid hex color for %s: '%s'. Use format #RRGGBB", k, v)
		}
	}
	advanced := map[string]string{}
	bg := map[string]any{}
	advKeys := setFromSlice(AdvancedThemeKeys)
	for _, kv := range tokens[7:] {
		eq := strings.Index(kv, "=")
		if eq < 0 {
			continue
		}
		k := kv[:eq]
		v := kv[eq+1:]
		if _, ok := advKeys[k]; ok {
			if !hexColorPattern.MatchString(v) {
				return nil, fmt.Errorf("error: Invalid hex color for advanced key %s: '%s'. Use format #RRGGBB", k, v)
			}
			advanced[k] = v
			continue
		}
		switch k {
		case "bgPattern":
			if !inSet(BGPatterns, v) {
				return nil, fmt.Errorf("error: Invalid bgPattern '%s'. Use one of: %s", v, strings.Join(BGPatterns, ", "))
			}
			bg["pattern"] = v
		case "bgEffectColor":
			if !hexColorPattern.MatchString(v) {
				return nil, fmt.Errorf("error: Invalid hex color for bgEffectColor: '%s'. Use format #RRGGBB", v)
			}
			bg["effectColor"] = v
		case "bgEffectIntensity":
			n, err := strconv.ParseFloat(v, 64)
			if err != nil {
				return nil, fmt.Errorf("error: Invalid number for %s: '%s'", k, v)
			}
			bg["effectIntensity"] = n
		case "bgEffectSize":
			n, err := strconv.ParseFloat(v, 64)
			if err != nil {
				return nil, fmt.Errorf("error: Invalid number for %s: '%s'", k, v)
			}
			bg["effectSize"] = n
		case "frosted":
			bg["frosted"] = Truthy(strings.ToLower(v))
		}
	}
	out := &UIControlEvent{
		UIEvent:   "create_theme",
		ThemeName: name,
		Results:   fmt.Sprintf("Custom theme '%s' created and applied", name),
	}
	if len(advanced) > 0 {
		colors["advanced"] = advanced
	}
	out.Colors = colors
	if len(bg) > 0 {
		out.BG = bg
	}
	if len(advanced) > 0 {
		out.Results += fmt.Sprintf(" with %d advanced overrides", len(advanced))
	}
	if len(bg) > 0 {
		pattern := ""
		if p, ok := bg["pattern"].(string); ok {
			pattern = p
		}
		frosted := false
		if f, ok := bg["frosted"].(bool); ok {
			frosted = f
		}
		tail := pattern
		if tail == "" && frosted {
			tail = "frosted"
		} else if tail == "" {
			tail = "custom"
		}
		out.Results += fmt.Sprintf(" + background effect (%s)", tail)
	}
	return out, nil
}

// HighlightEvent parses the "highlight" action.
func HighlightEvent(action *UIControlAction) (*UIControlEvent, error) {
	if len(action.Parts) < 1 || strings.TrimSpace(action.Parts[0]) == "" {
		return nil, fmt.Errorf("error: highlight needs: highlight <css-selector> [label]")
	}
	selector := action.Parts[0]
	label := strings.Join(action.Parts[1:], " ")
	return &UIControlEvent{
		UIEvent:  "highlight",
		Selector: selector,
		Label:    label,
		Results:  fmt.Sprintf("Highlighting '%s'", selector),
	}, nil
}

// ClearHighlightEvent emits the "clear_highlight" event.
func ClearHighlightEvent() *UIControlEvent {
	return &UIControlEvent{
		UIEvent: "clear_highlight",
		Results: "Highlights cleared",
	}
}

// OpenPanelEvent parses the "open_panel" action with alias resolution.
func OpenPanelEvent(action *UIControlAction) (*UIControlEvent, error) {
	if len(action.Parts) < 1 {
		return nil, fmt.Errorf("error: open_panel needs: open_panel <name>")
	}
	panel := strings.ToLower(action.Parts[0])
	target := PanelAliases[panel]
	if target == "" {
		return nil, fmt.Errorf("error: Unknown panel '%s'. Valid: %s.", panel, strings.Join(KnownPanels, ", "))
	}
	return &UIControlEvent{
		UIEvent: "open_panel",
		Panel:   target,
		Results: fmt.Sprintf("Opening %s panel", target),
	}, nil
}

// OpenEmailReplyEvent parses the "open_email_reply" action. The
// Python source accepts:
//
//	open_email_reply <uid> [folder] [reply|reply-all|ai-reply] [body]
//	<body on subsequent lines>
//
// and rejects empty bodies unless mode == "ai-reply" (which triggers a
// frontend-side AI-reply path that generates its own body).
func OpenEmailReplyEvent(action *UIControlAction) (*UIControlEvent, error) {
	// Re-tokenise the first line up to 5 fields. The Python source uses
	// `split(maxsplit=4)`.
	var first string
	if len(action.Lines) > 0 {
		first = action.Lines[0]
	}
	// Manual split to keep the source behaviour: maxsplit=4 splits the
	// first line into 5 fields max, so a body that begins on the same
	// line as the mode token is preserved.
	tokens := manualSplitN(first, 5)
	if len(tokens) < 2 {
		return nil, fmt.Errorf("error: open_email_reply needs: open_email_reply <uid> [folder] [reply|reply-all|ai-reply] [body text]")
	}
	uid := strings.TrimSpace(tokens[1])
	folder := "INBOX"
	if len(tokens) > 2 && strings.TrimSpace(tokens[2]) != "" {
		folder = strings.TrimSpace(tokens[2])
	}
	mode := "reply"
	if len(tokens) > 3 {
		mode = strings.ToLower(strings.TrimSpace(tokens[3]))
	}
	if mode != "reply" && mode != "reply-all" && mode != "ai-reply" {
		mode = "reply"
	}
	inlineBody := ""
	if len(tokens) > 4 {
		inlineBody = tokens[4]
	}
	restLines := ""
	if len(action.Lines) > 1 {
		restLines = strings.TrimSpace(strings.Join(action.Lines[1:], "\n"))
	}
	body := strings.TrimSpace(inlineBody + " " + restLines)
	body = strings.TrimSpace(body)
	if uid == "" {
		return nil, fmt.Errorf("error: open_email_reply needs: open_email_reply <uid> [folder] [reply|reply-all|ai-reply] [body text]")
	}
	if body == "" && mode != "ai-reply" {
		return nil, fmt.Errorf("error: open_email_reply called without body. The agent path REQUIRES a body — opening an empty draft is the wrong response when the user asked you to write. Re-call with the reply text included: `open_email_reply %s %s %s <your reply text here>`. Compose the reply now based on the open email's content and the user's request, then call this tool again with the body. Do NOT call create_document instead.", uid, folder, mode)
	}
	out := &UIControlEvent{
		UIEvent:   "open_email_reply",
		UID:       uid,
		Folder:    folder,
		ModeReply: mode,
		Results:   fmt.Sprintf("Opening reply draft for email UID %s", uid),
	}
	if body != "" {
		out.Results += " with pre-filled body"
		out.Body = body
	}
	return out, nil
}

// GetTogglesEvent mirrors the "get_toggles" action. The Python source
// emits a single {"results": "..."} string noting that toggles are
// managed client-side. The Go port keeps the same text.
func GetTogglesEvent() *UIControlEvent {
	return &UIControlEvent{
		Results: "Toggle states are managed client-side in localStorage. Available toggles: web, bash, rag, research, incognito, document_editor. Use 'toggle <name> <on|off>' to change them.",
	}
}

// SwitchModelEvent mirrors the "switch_model" action. The Python source
// resolves the model via _resolve_model and updates the active
// session's endpoint/model. The Go port exposes the resolution as a
// callback so the caller decides how to update storage.
//
// The resolver callback is required (returning "" signals the model
// was not found). Headers are passed through verbatim.
func SwitchModelEvent(action *UIControlAction, sessionID, owner string, resolve ModelResolver) (*UIControlEvent, error) {
	modelSpec := ""
	if len(action.Parts) > 0 {
		modelSpec = strings.TrimSpace(strings.Join(action.Parts, " "))
	}
	if modelSpec == "" && len(action.Lines) > 1 {
		modelSpec = strings.TrimSpace(action.Lines[1])
	}
	if modelSpec == "" {
		return nil, fmt.Errorf("error: switch_model needs a model name")
	}
	resolved, err := resolve(modelSpec, owner)
	if err != nil {
		return nil, fmt.Errorf("error: %s", err.Error())
	}
	out := &UIControlEvent{
		UIEvent:     "switch_model",
		Model:       resolved.ModelID,
		EndpointURL: resolved.EndpointURL,
		Results:     fmt.Sprintf("Model switched to '%s'", resolved.ModelID),
		Extra: map[string]any{
			"session_id": sessionID,
			"headers":    resolved.Headers,
		},
	}
	return out, nil
}

// BuildUIControlEvent dispatches on the parsed action name and returns
// the matching UIControlEvent. Callers supply the optional surfaces
// the per-action handlers need (custom themes, model resolver).
func BuildUIControlEvent(content string, opts UIControlOptions) (*UIControlEvent, error) {
	action, err := ParseUIControlAction(content)
	if err != nil {
		return nil, err
	}
	switch action.ActionName {
	case "toggle":
		return ToggleEvent(action)
	case "set_mode":
		return SetModeEvent(action)
	case "switch_model":
		return SwitchModelEvent(action, opts.SessionID, opts.Owner, opts.Resolver)
	case "set_theme":
		return SetThemeEvent(action, opts.CustomThemes)
	case "create_theme":
		return CreateThemeEvent(action)
	case "highlight":
		return HighlightEvent(action)
	case "clear_highlight":
		ev := ClearHighlightEvent()
		return ev, nil
	case "open_panel":
		return OpenPanelEvent(action)
	case "open_email_reply":
		return OpenEmailReplyEvent(action)
	case "get_toggles":
		ev := GetTogglesEvent()
		return ev, nil
	default:
		return nil, fmt.Errorf("error: Unknown action '%s'. Use: toggle, set_mode, switch_model, set_theme, highlight, clear_highlight, get_toggles", action.ActionName)
	}
}

// UIControlOptions configures the surfaces BuildUIControlEvent needs
// for the actions that talk to other parts of the system.
type UIControlOptions struct {
	SessionID    string
	Owner        string
	CustomThemes map[string]any
	Resolver     ModelResolver
}

// hexColorPattern is the regex used to validate "#RRGGBB" hex colors.
// The Python source uses the same pattern verbatim.
var hexColorPattern = regexp.MustCompile(`^#[0-9a-fA-F]{6}$`)

// onOff renders a state boolean as "on" / "off".
func onOff(state bool) string {
	if state {
		return "on"
	}
	return "off"
}

// setFromSlice returns a set-like map[string]struct{} view of s.
func setFromSlice(s []string) map[string]struct{} {
	out := make(map[string]struct{}, len(s))
	for _, v := range s {
		out[v] = struct{}{}
	}
	return out
}

// inSet reports whether s contains v.
func inSet(s []string, v string) bool {
	for _, x := range s {
		if x == v {
			return true
		}
	}
	return false
}

// manualSplitN splits s on whitespace with a maxsplit cap. The
// behaviour mirrors Python's `str.split(maxsplit=4)`: trailing runs of
// whitespace plus everything after the cap goes into the last token.
//
// Go's strings.FieldsN does not preserve the trailing tail in the last
// token (it drops it), so we re-implement the loop here to match.
func manualSplitN(s string, n int) []string {
	if n <= 0 {
		return nil
	}
	fields := make([]string, 0, n)
	i := 0
	for i < len(s) {
		// skip leading whitespace
		for i < len(s) && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n' || s[i] == '\r') {
			i++
		}
		if i >= len(s) {
			break
		}
		start := i
		for i < len(s) && s[i] != ' ' && s[i] != '\t' && s[i] != '\n' && s[i] != '\r' {
			i++
		}
		fields = append(fields, s[start:i])
		if len(fields) == n-1 {
			// Capture the remainder (including any leading whitespace)
			// into the last token. Trim leading whitespace only.
			rest := strings.TrimLeft(s[i:], " \t\n\r")
			if rest != "" {
				fields = append(fields, rest)
			}
			return fields
		}
	}
	return fields
}
