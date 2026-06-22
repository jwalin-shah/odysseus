package aiint

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// Toggle alias map. Mirrors the Python `_toggle_aliases` dict verbatim:
// users say "shell" / "search" naturally, and the server normalizes them
// to the canonical toggle id before validation.
var toggleAliases = map[string]string{
	"shell":         "bash",
	"terminal":      "bash",
	"search":        "web",
	"websearch":     "web",
	"web_search":    "web",
	"deepresearch":  "research",
	"deep_research": "research",
	"documents":     "document_editor",
	"doc":           "document_editor",
	"docs":          "document_editor",
	"private":       "incognito",
}

// Valid toggle ids. Mirrors the Python `valid_toggles` set.
var validToggles = map[string]bool{
	"web":             true,
	"bash":            true,
	"rag":             true,
	"research":        true,
	"incognito":       true,
	"document_editor": true,
}

// Panel alias map. Mirrors the Python `_panel_aliases` dict.
var panelAliases = map[string]string{
	"documents": "documents", "document": "documents", "doc": "documents",
	"docs": "documents", "library": "documents", "doclib": "documents",
	"gallery": "gallery", "images": "gallery",
	"email": "email", "emails": "email", "inbox": "email", "mail": "email",
	"sessions": "sessions", "chats": "sessions", "history": "sessions",
	"notes": "notes", "note": "notes", "todo": "notes", "todos": "notes",
	"memories": "memories", "memory": "memories", "brain": "memories",
	"skills":   "skills",
	"settings": "settings", "preferences": "settings",
	"cookbook": "cookbook", "models": "cookbook", "llm": "cookbook",
	"serve": "cookbook", "serving": "cookbook",
}

// Theme presets. Mirrors the Python `known_presets` list. Frontend lookup
// lives in static/js/theme.js; the Go port only validates the name.
var themePresets = []string{
	"dark", "light", "midnight", "paper", "cyberpunk", "retrowave",
	"forest", "ocean", "ume", "copper", "terminal", "organs",
	"lavender", "gpt", "claude", "cute",
}

// bgPatterns lists the valid bgPattern values accepted by create_theme.
var bgPatterns = map[string]bool{
	"none": true, "dots": true, "synapse": true, "rain": true,
	"constellations": true, "perlin-flow": true, "petals": true,
	"sparkles": true, "embers": true,
}

// advancedColorKeys lists the key=value pairs create_theme accepts beyond
// the five base hex slots.
var advancedColorKeys = map[string]bool{
	"userBubbleBg": true, "aiBubbleBg": true, "bubbleBorder": true,
	"sidebarBg": true, "sectionAccent": true, "brandColor": true,
	"inputBg": true, "inputBorder": true, "sendBtnBg": true,
	"sendBtnHover": true, "codeBg": true, "codeFg": true,
	"toggleBg": true, "toggleActive": true, "accentPrimary": true,
	"accentError": true,
}

// hexColor matches the #RRGGBB hex format used everywhere in create_theme.
var hexColor = regexp.MustCompile(`^#[0-9a-fA-F]{6}$`)

// UIControl dispatches the ui_control tool. Mirrors Python's
// `do_ui_control` surface in full: toggle, set_mode, switch_model,
// set_theme, create_theme, highlight, clear_highlight, open_panel,
// open_email_reply, get_toggles.
//
// `themes` is the merged set of preset names + any user-custom themes the
// caller has registered (mirrors Python's `_load_prefs().get("custom-themes")`).
func UIControl(content string, mgr *Manager, themes []string) (*Result, error) {
	lines := strings.Split(strings.TrimSpace(content), "\n")
	if len(lines) == 0 || strings.TrimSpace(lines[0]) == "" {
		return errorResult("No action specified"), nil
	}

	parts := strings.SplitN(strings.TrimSpace(lines[0]), " ", 3)
	action := strings.ToLower(parts[0])

	switch action {
	case "toggle":
		return uiToggle(parts)
	case "set_mode":
		return uiSetMode(parts)
	case "switch_model":
		return uiSwitchModel(content, lines, parts, mgr)
	case "set_theme":
		return uiSetTheme(parts, themes)
	case "create_theme":
		return uiCreateTheme(lines[0])
	case "highlight":
		return uiHighlight(parts)
	case "clear_highlight":
		return &Result{OK: true, Details: map[string]any{"ui_event": "clear_highlight"}, Results: "Highlights cleared"}, nil
	case "open_panel":
		return uiOpenPanel(parts)
	case "open_email_reply":
		return uiOpenEmailReply(lines)
	case "get_toggles":
		return &Result{OK: true, Results: "Toggle states are managed client-side in localStorage. Available toggles: web, bash, rag, research, incognito, document_editor. Use 'toggle <name> <on|off>' to change them."}, nil
	default:
		return errorResult(fmt.Sprintf("Unknown action '%s'. Use: toggle, set_mode, switch_model, set_theme, highlight, clear_highlight, get_toggles", action)), nil
	}
}

// parseToggleState mirrors Python's truthy-set: on/true/1/yes/enable/enabled.
func parseToggleState(s string) bool {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "on", "true", "1", "yes", "enable", "enabled":
		return true
	}
	return false
}

func uiToggle(parts []string) (*Result, error) {
	if len(parts) < 3 {
		return errorResult("toggle needs: toggle <name> <on|off>"), nil
	}
	name := strings.ToLower(parts[1])
	if alias, ok := toggleAliases[name]; ok {
		name = alias
	}
	if !validToggles[name] {
		return errorResult(fmt.Sprintf("Unknown toggle '%s'. Valid: %s", name, strings.Join(sortedKeys(validToggles), ", "))), nil
	}
	state := parseToggleState(parts[2])
	stateStr := "off"
	if state {
		stateStr = "on"
	}
	return &Result{
		OK:      true,
		Details: map[string]any{"ui_event": "toggle", "toggle_name": name, "state": state},
		Results: fmt.Sprintf("Toggle '%s' set to %s", name, stateStr),
	}, nil
}

func uiSetMode(parts []string) (*Result, error) {
	if len(parts) < 2 {
		return errorResult("set_mode needs: set_mode <agent|chat>"), nil
	}
	mode := strings.ToLower(parts[1])
	if mode != "agent" && mode != "chat" {
		return errorResult(fmt.Sprintf("Invalid mode '%s'. Use: agent, chat", mode)), nil
	}
	return &Result{
		OK:      true,
		Details: map[string]any{"ui_event": "set_mode", "mode": mode},
		Results: fmt.Sprintf("Mode changed to '%s'", mode),
	}, nil
}

// uiSwitchModel is the one place we hit the ModelResolver seam. The Python
// module additionally writes the resolved (url, model, headers) into the
// current session via _session_manager + a SQL update; here we return the
// resolved values in the Result so callers can do their own writeback.
func uiSwitchModel(content string, lines, parts []string, mgr *Manager) (*Result, error) {
	spec := ""
	if len(parts) > 1 {
		spec = strings.TrimSpace(parts[1])
		if len(parts) > 2 {
			spec = strings.TrimSpace(parts[1] + " " + parts[2])
		}
	}
	if spec == "" && len(lines) > 1 {
		spec = strings.TrimSpace(lines[1])
	}
	if spec == "" {
		return errorResult("switch_model needs a model name"), nil
	}
	if mgr == nil || mgr.Resolver == nil {
		return errorResult("model resolver not configured"), nil
	}
	resolved, err := mgr.Resolver.Resolve(nil, spec, "")
	if err != nil {
		return errorResult(err.Error()), nil
	}
	return &Result{
		OK: true,
		Details: map[string]any{
			"ui_event":     "switch_model",
			"model":        resolved.ModelID,
			"endpoint_url": resolved.URL,
		},
		Results: fmt.Sprintf("Model switched to '%s'", resolved.ModelID),
	}, nil
}

func uiSetTheme(parts []string, themes []string) (*Result, error) {
	theme := ""
	if len(parts) > 1 {
		theme = strings.ToLower(parts[1])
	}
	known := map[string]bool{}
	for _, p := range themePresets {
		known[p] = true
	}
	for _, c := range themes {
		known[c] = true
	}
	if !known[theme] {
		customLabel := ""
		if len(themes) > 0 {
			customLabel = fmt.Sprintf(" | Custom: %s", strings.Join(themes, ", "))
		}
		return errorResult(fmt.Sprintf("Unknown theme '%s'. Available: %s%s", theme, strings.Join(themePresets, ", "), customLabel)), nil
	}
	return &Result{
		OK:      true,
		Details: map[string]any{"ui_event": "set_theme", "theme_name": theme},
		Results: fmt.Sprintf("Theme changed to '%s'", theme),
	}, nil
}

// uiCreateTheme parses a `create_theme <name> <bg> <fg> <panel> <border>
// <accent> [k=v ...]` line. Optional k=v pairs cover advanced hex colors,
// bgPattern, bgEffectColor, bgEffectIntensity, bgEffectSize, frosted.
func uiCreateTheme(firstLine string) (*Result, error) {
	parts := strings.Fields(firstLine)
	if len(parts) < 7 {
		return errorResult("create_theme needs: create_theme <name> <bg> <fg> <panel> <border> <accent> (all hex colors). Optional advanced color key=value pairs (userBubbleBg, aiBubbleBg, bubbleBorder, sidebarBg, sectionAccent, brandColor, inputBg, inputBorder, sendBtnBg, sendBtnHover, codeBg, codeFg, toggleBg, toggleActive, accentPrimary, accentError). Optional background EFFECTS: bgPattern=<none|dots|synapse|rain|constellations|perlin-flow|petals|sparkles|embers>, bgEffectColor=#RRGGBB, bgEffectIntensity=<num e.g. 1>, bgEffectSize=<num e.g. 1>, frosted=true|false"), nil
	}
	name := strings.ToLower(strings.ReplaceAll(parts[1], " ", "-"))
	colors := map[string]string{
		"bg":     parts[2],
		"fg":     parts[3],
		"panel":  parts[4],
		"border": parts[5],
		"red":    parts[6],
	}
	for k, v := range colors {
		if !hexColor.MatchString(v) {
			return errorResult(fmt.Sprintf("Invalid hex color for %s: '%s'. Use format #RRGGBB", k, v)), nil
		}
	}

	advanced := map[string]string{}
	bg := map[string]any{}

	for _, part := range parts[7:] {
		kv := strings.SplitN(part, "=", 2)
		if len(kv) != 2 {
			continue
		}
		k, v := kv[0], kv[1]
		if advancedColorKeys[k] {
			if !hexColor.MatchString(v) {
				return errorResult(fmt.Sprintf("Invalid hex color for advanced key %s: '%s'. Use format #RRGGBB", k, v)), nil
			}
			advanced[k] = v
		} else if k == "bgPattern" {
			if !bgPatterns[v] {
				return errorResult(fmt.Sprintf("Invalid bgPattern '%s'. Use one of: %s", v, strings.Join(sortedKeys(bgPatterns), ", "))), nil
			}
			bg["pattern"] = v
		} else if k == "bgEffectColor" {
			if !hexColor.MatchString(v) {
				return errorResult(fmt.Sprintf("Invalid hex color for bgEffectColor: '%s'. Use format #RRGGBB", v)), nil
			}
			bg["effectColor"] = v
		} else if k == "bgEffectIntensity" || k == "bgEffectSize" {
			f, err := strconv.ParseFloat(v, 64)
			if err != nil {
				return errorResult(fmt.Sprintf("Invalid number for %s: '%s'", k, v)), nil
			}
			key := "effectIntensity"
			if k == "bgEffectSize" {
				key = "effectSize"
			}
			bg[key] = f
		} else if k == "frosted" {
			bg["frosted"] = parseToggleState(v)
		}
	}

	if len(advanced) > 0 {
		colors["advanced"] = advanced["_"] // placeholder; replaced below
		for k, v := range advanced {
			colors[k] = v
		}
		delete(colors, "advanced")
	}

	detail := map[string]any{"ui_event": "create_theme", "theme_name": name, "colors": colors}
	if len(bg) > 0 {
		detail["bg"] = bg
	}

	results := fmt.Sprintf("Custom theme '%s' created and applied", name)
	if len(advanced) > 0 {
		results += fmt.Sprintf(" with %d advanced overrides", len(advanced))
	}
	if len(bg) > 0 {
		// Match the Python trailing summary.
		label := "custom"
		if p, ok := bg["pattern"].(string); ok && p != "" {
			label = p
		} else if f, ok := bg["frosted"].(bool); ok && f {
			label = "frosted"
		}
		results += fmt.Sprintf(" + background effect (%s)", label)
	}

	return &Result{OK: true, Details: detail, Results: results}, nil
}

func uiHighlight(parts []string) (*Result, error) {
	if len(parts) < 2 || strings.TrimSpace(parts[1]) == "" {
		return errorResult("highlight needs: highlight <css-selector> [label]"), nil
	}
	selector := parts[1]
	label := ""
	if len(parts) > 2 {
		label = strings.Join(strings.Fields(parts[2]), " ")
	}
	return &Result{
		OK:      true,
		Details: map[string]any{"ui_event": "highlight", "selector": selector, "label": label},
		Results: fmt.Sprintf("Highlighting '%s'", selector),
	}, nil
}

func uiOpenPanel(parts []string) (*Result, error) {
	panel := ""
	if len(parts) > 1 {
		panel = strings.ToLower(parts[1])
	}
	target, ok := panelAliases[panel]
	if !ok {
		return errorResult(fmt.Sprintf("Unknown panel '%s'. Valid: documents, gallery, email, sessions, notes, memories, skills, settings, cookbook.", panel)), nil
	}
	return &Result{
		OK:      true,
		Details: map[string]any{"ui_event": "open_panel", "panel": target},
		Results: fmt.Sprintf("Opening %s panel", target),
	}, nil
}

// uiOpenEmailReply parses `open_email_reply <uid> [folder] [mode] [body]`.
// Body text on subsequent lines is appended after any inline body on line 1.
func uiOpenEmailReply(lines []string) (*Result, error) {
	firstLine := strings.TrimSpace(lines[0])
	parts := strings.SplitN(firstLine, " ", 5)
	uid := ""
	if len(parts) > 1 {
		uid = strings.TrimSpace(parts[1])
	}
	folder := "INBOX"
	if len(parts) > 2 {
		folder = strings.TrimSpace(parts[2])
	}
	mode := "reply"
	if len(parts) > 3 {
		mode = strings.ToLower(strings.TrimSpace(parts[3]))
	}
	if mode != "reply" && mode != "reply-all" && mode != "ai-reply" {
		mode = "reply"
	}

	inlineBody := ""
	if len(parts) > 4 {
		inlineBody = parts[4]
	}
	restLines := ""
	if len(lines) > 1 {
		restLines = strings.TrimSpace(strings.Join(lines[1:], "\n"))
	}
	body := strings.TrimSpace(inlineBody + "\n" + restLines)
	if restLines == "" {
		body = strings.TrimSpace(inlineBody)
	}

	if uid == "" {
		return errorResult("open_email_reply needs: open_email_reply <uid> [folder] [reply|reply-all|ai-reply] [body text]"), nil
	}

	if body == "" && mode != "ai-reply" {
		return errorResult(fmt.Sprintf(
			"open_email_reply called without body. The agent path REQUIRES a body — "+
				"opening an empty draft is the wrong response when the user asked you to write. "+
				"Re-call with the reply text included: "+
				"`open_email_reply %s %s %s <your reply text here>`. "+
				"Compose the reply now based on the open email's content and the user's request, "+
				"then call this tool again with the body. Do NOT call create_document instead.",
			uid, folderOrDefault(folder), mode)), nil
	}

	detail := map[string]any{
		"ui_event": "open_email_reply",
		"uid":      uid,
		"folder":   folderOrDefault(folder),
		"mode":     mode,
	}
	results := fmt.Sprintf("Opening reply draft for email UID %s", uid)
	if body != "" {
		detail["body"] = body
		results += " with pre-filled body"
	}
	return &Result{OK: true, Details: detail, Results: results}, nil
}

func folderOrDefault(s string) string {
	if s == "" {
		return "INBOX"
	}
	return s
}

func sortedKeys(m map[string]bool) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	// Stable enough for tests; not stable enough for prod.
	for i := 0; i < len(keys); i++ {
		for j := i + 1; j < len(keys); j++ {
			if keys[j] < keys[i] {
				keys[i], keys[j] = keys[j], keys[i]
			}
		}
	}
	return keys
}
