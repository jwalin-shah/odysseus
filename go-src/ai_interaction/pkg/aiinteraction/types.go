package aiinteraction

// PipelineStep mirrors the per-step dict shape used in do_pipeline:
// {"model": "<model-spec>", "instruction": "<text>"}. The Go port keeps
// the same field names so a Python-side JSON dump can be passed in
// untouched when callers wire the package up against the legacy path.
type PipelineStep struct {
	Model       string `json:"model"`
	Instruction string `json:"instruction"`
}

// PipelineRequest is the parsed representation of the pipeline tool
// input. The Python source supports two formats — JSON {"steps": [...]}
// or list-of-steps JSON, and a "model | instruction" line format — and
// the parser picks one based on a JSON sniff first.
//
// Content is the original raw input (so error messages can echo it).
type PipelineRequest struct {
	Steps []PipelineStep
	// Format is "json" or "lines" depending on which parser was used.
	Format string
	// Content preserves the raw user input for error messages.
	Content string
}

// MemoryAction is the parsed shape of the manage_memory content string.
//
// Content format:
//
//	Line 1: action (list|add|edit|delete|search)
//	Line 2+: action-specific params
type MemoryAction struct {
	Action string // "list" | "add" | "edit" | "delete" | "search" (lower-cased)
	// Lines is the post-action body (everything after line 1) with each
	// element trimmed. Empty entries are preserved so error messages can
	// echo the original line number.
	Lines []string
	// Category is the optional category filter (list, default action).
	// Empty when not supplied.
	Category string
	// Text is the memory text (add action). Empty when not supplied.
	Text string
	// MemoryID is the memory id substring (edit/delete). Empty when not
	// supplied.
	MemoryID string
	// NewText is the replacement text (edit). Empty when not supplied.
	NewText string
	// Query is the search query (search). Empty when not supplied.
	Query string
}

// RAGAction mirrors ParseRAGAction's output.
type RAGAction struct {
	Action    string // "list" | "add_directory" | "remove_directory"
	Directory string
}

// UIControlAction mirrors the structured shape of do_ui_control's
// first line. The ActionName is the lowercase first whitespace-split
// token. Args are everything after that, *unsplit* (the Python source
// re-splits with maxsplit=2 for some actions, so the parser exposes
// the raw first-line segments and a few convenience accessors).
type UIControlAction struct {
	ActionName string
	// Args is the raw remainder of the first line, post-action. This is
	// what the Python source re-splits per-action. Mirrors
	// `parts = lines[0].strip().split(None, 2)` followed by per-action
	// logic.
	Args string
	// Parts is the whitespace-split list of tokens from line 1 (after
	// ActionName). For most actions this is what `parts[1:]` returns in
	// Python.
	Parts []string
	// Lines is the raw input lines, trimmed but not split.
	Lines []string
}

// UIControlEvent is the structured envelope do_ui_control emits. The
// shape mirrors the dicts the Python source returns: each one carries
// a "ui_event" tag plus the relevant fields. The Go port exposes the
// same set of fields so JSON callers can read either the typed struct
// or the generic map.
type UIControlEvent struct {
	UIEvent     string         `json:"ui_event"`
	ToggleName  string         `json:"toggle_name,omitempty"`
	State       *bool          `json:"state,omitempty"`
	Mode        string         `json:"mode,omitempty"`
	Model       string         `json:"model,omitempty"`
	EndpointURL string         `json:"endpoint_url,omitempty"`
	ThemeName   string         `json:"theme_name,omitempty"`
	Colors      map[string]any `json:"colors,omitempty"`
	BG          map[string]any `json:"bg,omitempty"`
	Selector    string         `json:"selector,omitempty"`
	Label       string         `json:"label,omitempty"`
	Panel       string         `json:"panel,omitempty"`
	UID         string         `json:"uid,omitempty"`
	Folder      string         `json:"folder,omitempty"`
	ModeReply   string         `json:"mode_reply,omitempty"`
	Body        string         `json:"body,omitempty"`
	Results     string         `json:"results,omitempty"`
	Extra       map[string]any `json:"-"`
}

// ToMap renders a UIControlEvent as a generic map[string]any. The
// Python source returns dicts whose keys vary per action; this
// helper preserves that shape so callers that round-trip JSON don't
// have to switch on ActionName.
func (e UIControlEvent) ToMap() map[string]any {
	m := map[string]any{"ui_event": e.UIEvent, "results": e.Results}
	if e.ToggleName != "" {
		m["toggle_name"] = e.ToggleName
	}
	if e.State != nil {
		m["state"] = *e.State
	}
	if e.Mode != "" {
		m["mode"] = e.Mode
	}
	if e.Model != "" {
		m["model"] = e.Model
	}
	if e.EndpointURL != "" {
		m["endpoint_url"] = e.EndpointURL
	}
	if e.ThemeName != "" {
		m["theme_name"] = e.ThemeName
	}
	if e.Colors != nil {
		m["colors"] = e.Colors
	}
	if e.BG != nil {
		m["bg"] = e.BG
	}
	if e.Selector != "" {
		m["selector"] = e.Selector
	}
	if e.Label != "" {
		m["label"] = e.Label
	}
	if e.Panel != "" {
		m["panel"] = e.Panel
	}
	if e.UID != "" {
		m["uid"] = e.UID
	}
	if e.Folder != "" {
		m["folder"] = e.Folder
	}
	if e.ModeReply != "" {
		m["mode"] = e.ModeReply
	}
	if e.Body != "" {
		m["body"] = e.Body
	}
	for k, v := range e.Extra {
		m[k] = v
	}
	return m
}

// ImageRequest is the parsed shape of the generate_image content
// string. Fields default to the same defaults the Python source uses.
//
// Content format:
//
//	Line 1: prompt describing the image
//	Line 2: model name (optional)
//	Line 3: size (optional, defaults to 1024x1024)
//	Line 4: quality (optional, defaults to medium)
type ImageRequest struct {
	Prompt  string
	Model   string
	Size    string
	Quality string
}

// ResolvedModel is the tuple (_resolve_model) returns:
// (endpoint_url, model_id, headers).
type ResolvedModel struct {
	EndpointURL string
	ModelID     string
	Headers     map[string]string
}

// ModelSpec is the parsed shape of the input to _resolve_model. The
// Python source accepts either "model_name" or "model_name@endpoint_name"
// and trims whitespace before splitting on the rightmost "@".
type ModelSpec struct {
	// ModelName is the part to the left of "@" (or the whole spec if
	// "@" was absent). Already stripped.
	ModelName string
	// EndpointName is the part to the right of "@". Empty when no "@"
	// was supplied.
	EndpointName string
}

// MemoryEntry is the dict shape the memory manager works with. The
// Python source reads/writes dicts with at least id/text/owner/category;
// the Go port keeps the same field names so a caller wiring the package
// against a real memory store can pass entries straight through.
type MemoryEntry struct {
	ID        string `json:"id"`
	Text      string `json:"text"`
	Category  string `json:"category"`
	Owner     string `json:"owner,omitempty"`
	Timestamp int64  `json:"timestamp,omitempty"`
}
