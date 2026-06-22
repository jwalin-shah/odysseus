package aiinteraction

import (
	"fmt"
	"strings"
)

// ParseMemoryAction parses the manage_memory tool content. The Python
// source splits the input on "\n", lower-cases the first token, and
// pulls per-action arguments off subsequent lines. The Go port mirrors
// that flow exactly so a caller can pass the raw content string and
// get back a typed MemoryAction plus, where appropriate, a fully
// populated per-action struct.
//
// Errors carry the "error: " prefix the Python source uses so callers
// can return them as-is to clients that expect {"error": ...}.
func ParseMemoryAction(content string) (*MemoryAction, error) {
	rawLines := strings.Split(strings.TrimSpace(content), "\n")
	if len(rawLines) == 0 || strings.TrimSpace(rawLines[0]) == "" {
		return nil, fmt.Errorf("error: Need at least 1 line: action")
	}
	action := strings.ToLower(strings.TrimSpace(rawLines[0]))
	// Strip the first line — subsequent Lines[0..] are the per-action
	// arguments, each trimmed but preserved (empty lines kept so
	// callers can echo the original line number).
	lines := make([]string, 0, len(rawLines)-1)
	for _, l := range rawLines[1:] {
		lines = append(lines, strings.TrimSpace(l))
	}

	out := &MemoryAction{Action: action, Lines: lines}
	switch action {
	case "list":
		if len(lines) > 0 && lines[0] != "" {
			out.Category = strings.ToLower(lines[0])
		}
	case "add":
		if len(lines) < 1 || lines[0] == "" {
			return out, fmt.Errorf("error: Add needs line 2: memory text")
		}
		out.Text = lines[0]
		if len(lines) > 1 && lines[1] != "" {
			out.Category = strings.ToLower(lines[1])
		} else {
			out.Category = "fact"
		}
	case "edit":
		if len(lines) < 2 || lines[0] == "" {
			return out, fmt.Errorf("error: Edit needs line 2: memory_id, line 3: new text")
		}
		out.MemoryID = lines[0]
		out.NewText = lines[1]
		if out.NewText == "" {
			return out, fmt.Errorf("error: New text cannot be empty")
		}
	case "delete":
		if len(lines) < 1 || lines[0] == "" {
			return out, fmt.Errorf("error: Delete needs line 2: memory_id")
		}
		out.MemoryID = lines[0]
	case "search":
		if len(lines) < 1 || lines[0] == "" {
			return out, fmt.Errorf("error: Search needs line 2: query")
		}
		out.Query = lines[0]
	default:
		return out, fmt.Errorf("error: Unknown action '%s'. Use: list, add, edit, delete, search", action)
	}
	return out, nil
}

// FormatMemoryList mirrors the rendering do_manage_memory does for the
// "list" action. The caller passes the loaded entries plus any
// category filter; the function returns the human-readable summary the
// Python source builds inside the result dict.
//
// The Python source uses two layouts:
//
//   - empty list -> "No memories found" + optional category suffix.
//   - non-empty  -> "Found N memory entries:\n" followed by bullet lines.
//
// The Go port keeps both branches and returns the same strings so
// callers can put them directly into a {"results": "..."} map.
func FormatMemoryList(memories []MemoryEntry, categoryFilter string) string {
	cat := strings.ToLower(strings.TrimSpace(categoryFilter))
	if cat != "" {
		filtered := make([]MemoryEntry, 0, len(memories))
		for _, m := range memories {
			if strings.ToLower(m.Category) == cat {
				filtered = append(filtered, m)
			}
		}
		memories = filtered
	}
	if len(memories) == 0 {
		if cat != "" {
			return fmt.Sprintf("No memories found in category '%s'.", cat)
		}
		return "No memories found."
	}
	var b strings.Builder
	fmt.Fprintf(&b, "Found %d memory entries:\n", len(memories))
	for _, m := range memories {
		c := m.Category
		if c == "" {
			c = "fact"
		}
		id := m.ID
		if len(id) > 8 {
			id = id[:8]
		}
		text := m.Text
		if len(text) > 150 {
			text = text[:150] + "..."
		}
		fmt.Fprintf(&b, "- [%s] `%s` — %s\n", c, id, text)
	}
	return strings.TrimRight(b.String(), "\n")
}

// FormatMemorySearch mirrors the "search" action's rendering. It does
// not do the search — the Python source delegates to
// memory_manager.get_relevant_memories when available and falls back
// to a substring scan. The Go port exposes the rendering only; the
// caller passes the already-filtered entries.
func FormatMemorySearch(results []MemoryEntry, query string) string {
	if len(results) == 0 {
		return fmt.Sprintf("No memories found matching '%s'.", query)
	}
	var b strings.Builder
	fmt.Fprintf(&b, "Found %d matching memories:\n", len(results))
	for _, m := range results {
		c := m.Category
		if c == "" {
			c = "fact"
		}
		id := m.ID
		if len(id) > 8 {
			id = id[:8]
		}
		fmt.Fprintf(&b, "- [%s] `%s` — %s\n", c, id, m.Text)
	}
	return strings.TrimRight(b.String(), "\n")
}

// FilterMemoriesByText is the fallback path do_manage_memory takes when
// the memory manager does not implement get_relevant_memories. It does
// a case-insensitive substring scan and caps the result at 20 entries.
func FilterMemoriesByText(memories []MemoryEntry, query string) []MemoryEntry {
	q := strings.ToLower(strings.TrimSpace(query))
	if q == "" {
		return nil
	}
	const cap = 20
	out := make([]MemoryEntry, 0, cap)
	for _, m := range memories {
		if strings.Contains(strings.ToLower(m.Text), q) {
			out = append(out, m)
			if len(out) >= cap {
				break
			}
		}
	}
	return out
}
