package aiinteraction

import (
	"strings"
	"sync"
)

// AnthropicModels is the same hardcoded model list that
// src/llm_core.py:279 uses to match user input against the Anthropic
// provider. The Go port keeps the list verbatim so resolution against
// the "anthropic" provider matches the Python behaviour exactly.
var AnthropicModels = []string{
	"claude-opus-4-20250514", "claude-opus-4",
	"claude-sonnet-4-20250514", "claude-sonnet-4", "claude-sonnet-4-5-20250929", "claude-sonnet-4-5",
	"claude-haiku-4-20250514", "claude-haiku-4", "claude-haiku-3-5-20241022", "claude-haiku-3-5",
}

// KnownThemePresets mirrors the THEMES array in static/js/theme.js, also
// listed in the docstring of do_ui_control.
var KnownThemePresets = []string{
	"dark", "light", "midnight", "paper", "cyberpunk", "retrowave",
	"forest", "ocean", "ume", "copper", "terminal", "organs",
	"lavender", "gpt", "claude", "cute",
}

// KnownToggles mirrors the toggle validation set in do_ui_control. The
// Python source keeps this inline inside the function.
var KnownToggles = []string{
	"web", "bash", "rag", "research", "incognito", "document_editor",
}

// ToggleAliases maps friendly user-supplied names to the canonical
// toggle names. Mirrors the inline `_toggle_aliases` dict in do_ui_control.
var ToggleAliases = map[string]string{
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

// PanelAliases mirrors the `_panel_aliases` dict in do_ui_control.
var PanelAliases = map[string]string{
	"documents":   "documents",
	"document":    "documents",
	"doc":         "documents",
	"docs":        "documents",
	"library":     "documents",
	"doclib":      "documents",
	"gallery":     "gallery",
	"images":      "gallery",
	"email":       "email",
	"emails":      "email",
	"inbox":       "email",
	"mail":        "email",
	"sessions":    "sessions",
	"chats":       "sessions",
	"history":     "sessions",
	"notes":       "notes",
	"note":        "notes",
	"todo":        "notes",
	"todos":       "notes",
	"memories":    "memories",
	"memory":      "memories",
	"brain":       "memories",
	"skills":      "skills",
	"settings":    "settings",
	"preferences": "settings",
	"cookbook":    "cookbook",
	"models":      "cookbook",
	"llm":         "cookbook",
	"serve":       "cookbook",
	"serving":     "cookbook",
}

// KnownPanels is the closed set of canonical panel names do_ui_control
// will emit.
var KnownPanels = []string{
	"documents", "gallery", "email", "sessions", "notes",
	"memories", "skills", "settings", "cookbook",
}

// BGPatterns mirrors `_BG_PATTERNS` in do_ui_control.
var BGPatterns = []string{
	"none", "dots", "synapse", "rain", "constellations",
	"perlin-flow", "petals", "sparkles", "embers",
}

// AdvancedThemeKeys mirrors the `adv_keys` set in do_ui_control.
var AdvancedThemeKeys = []string{
	"userBubbleBg", "aiBubbleBg", "bubbleBorder", "sidebarBg",
	"sectionAccent", "brandColor", "inputBg", "inputBorder",
	"sendBtnBg", "sendBtnHover", "codeBg", "codeFg",
	"toggleBg", "toggleActive", "accentPrimary", "accentError",
}

// ValidGPTSizes mirrors valid_gpt_sizes in do_generate_image.
var ValidGPTSizes = []string{"1024x1024", "1024x1536", "1536x1024", "auto"}

// ValidDalle3Sizes mirrors valid_dalle3_sizes in do_generate_image.
var ValidDalle3Sizes = []string{"1024x1024", "1024x1792", "1792x1024"}

// ImageQualities mirrors the accepted values for the quality field in
// do_generate_image (used for gpt-image-* and local diffusion models).
var ImageQualities = []string{"low", "medium", "high", "auto"}

// ImageFallbackCandidates mirrors the auto-detect fallback list in
// do_generate_image. The first one that resolves wins.
var ImageFallbackCandidates = []string{"gpt-image-1.5", "gpt-image-1", "dall-e-3"}

// TristateTrue is the set of strings treated as truthy by the UI
// control tool when toggling settings.
var TristateTrue = map[string]struct{}{
	"on": {}, "true": {}, "1": {}, "yes": {},
	"enable": {}, "enabled": {},
}

// Truthy reports whether s (already lower-cased) is in TristateTrue.
func Truthy(s string) bool {
	_, ok := TristateTrue[s]
	return ok
}

// KnownPanel reports whether name is in the closed set of canonical
// panel names.
func KnownPanel(name string) bool {
	for _, p := range KnownPanels {
		if p == name {
			return true
		}
	}
	return false
}

// KnownTheme reports whether name is in the built-in preset list.
func KnownTheme(name string) bool {
	for _, p := range KnownThemePresets {
		if p == name {
			return true
		}
	}
	return false
}

// KnownToggle reports whether name is in the closed set of toggles.
func KnownToggle(name string) bool {
	for _, p := range KnownToggles {
		if p == name {
			return true
		}
	}
	return false
}

// KnownImageQuality reports whether q is a valid image-quality value.
func KnownImageQuality(q string) bool {
	for _, p := range ImageQualities {
		if p == q {
			return true
		}
	}
	return false
}

// ---------------------------------------------------------------------------
// Package state — generated images directory.
//
// Python reads GENERATED_IMAGES_DIR from src.constants. The Go port keeps
// a single package-level path that can be overridden in tests via
// SetGeneratedImagesDir. The lock makes the swap race-free for parallel
// tests.
// ---------------------------------------------------------------------------

var (
	imagesDirMu     sync.RWMutex
	imagesDirCached string
)

// DefaultGeneratedImagesDir returns the path used to store generated
// images when no override is set. Mirrors the Python default of
// $DATA_DIR/generated_images, except DATA_DIR is read from
// $ODYSSEUS_DATA_DIR and falls back to "./data" (matching the
// Python "DATA_DIR = os.environ.get('ODYSSEUS_DATA_DIR', './data')"
// fallback in src/constants.py).
func DefaultGeneratedImagesDir() string {
	return joinPath(getDataDir(), "generated_images")
}

// GetGeneratedImagesDir returns the current generated-images directory,
// applying any test override first. The Python source uses a module
// import; the Go port keeps the same effective path in package state.
func GetGeneratedImagesDir() string {
	imagesDirMu.RLock()
	v := imagesDirCached
	imagesDirMu.RUnlock()
	if v != "" {
		return v
	}
	return DefaultGeneratedImagesDir()
}

// SetGeneratedImagesDir overrides the generated-images directory. Pass
// "" to clear the override and fall back to DefaultGeneratedImagesDir.
func SetGeneratedImagesDir(dir string) {
	imagesDirMu.Lock()
	imagesDirCached = dir
	imagesDirMu.Unlock()
}

// joinPath is a tiny os-path shim that always returns forward slashes
// (the package only emits web-facing paths, so platform-specific
// separators are not interesting).
func joinPath(parts ...string) string {
	out := ""
	for i, p := range parts {
		if p == "" {
			continue
		}
		if i > 0 && !strings.HasSuffix(out, "/") && !strings.HasPrefix(p, "/") {
			out += "/"
		}
		out += p
	}
	return out
}
