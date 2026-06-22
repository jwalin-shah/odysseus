package aiint

import (
	"fmt"
	"strings"
	"time"
)

// ManageMemory dispatches the manage_memory tool. Mirrors Python's
// `do_manage_memory` action set: list, add, edit, delete, search.
//
// `content` follows the Python line format:
//
//	line 1: action
//	line 2+: action-specific params
func ManageMemory(content string, mgr MemoryManager, vec MemoryVector, owner string) (*Result, error) {
	if mgr == nil {
		return errorResult("Memory manager not available"), nil
	}

	lines := splitNonEmptyLines(content)
	if len(lines) == 0 {
		return errorResult("Need at least 1 line: action"), nil
	}
	action := strings.ToLower(strings.TrimSpace(lines[0]))

	switch action {
	case "list":
		return memoryList(mgr, owner, lines)
	case "add":
		// Use the raw split so we can detect whitespace-only line 2 and emit
		// "Memory text cannot be empty" rather than "Add needs line 2".
		return memoryAdd(mgr, vec, owner, rawLines(content))
	case "edit":
		return memoryEdit(mgr, vec, owner, rawLines(content), time.Now().Unix())
	case "delete":
		return memoryDelete(mgr, vec, owner, rawLines(content))
	case "search":
		return memorySearch(mgr, owner, rawLines(content))
	default:
		return errorResult(fmt.Sprintf("Unknown action '%s'. Use: list, add, edit, delete, search", action)), nil
	}
}

// splitNonEmptyLines splits on \n and drops empty/whitespace-only entries.
// Used for actions that don't need raw shape (list).
func splitNonEmptyLines(content string) []string {
	var out []string
	for _, l := range strings.Split(content, "\n") {
		l = strings.TrimSpace(l)
		if l != "" {
			out = append(out, l)
		}
	}
	return out
}

// rawLines splits on \n and trims each line but preserves the line count
// (including whitespace-only entries) so callers can distinguish "missing
// line N" from "empty line N".
func rawLines(content string) []string {
	out := make([]string, 0, strings.Count(content, "\n")+1)
	for _, l := range strings.Split(content, "\n") {
		out = append(out, strings.TrimSpace(l))
	}
	return out
}

func memoryList(mgr MemoryManager, owner string, lines []string) (*Result, error) {
	categoryFilter := ""
	if len(lines) > 1 {
		categoryFilter = strings.ToLower(strings.TrimSpace(lines[1]))
	}

	entries := mgr.Load(owner)
	filtered := entries[:0:0]
	for _, e := range entries {
		if categoryFilter != "" && strings.ToLower(e.Category) != categoryFilter {
			continue
		}
		filtered = append(filtered, e)
	}
	if len(filtered) == 0 {
		msg := "No memories found"
		if categoryFilter != "" {
			msg += " in category '" + categoryFilter + "'"
		}
		return &Result{OK: true, Results: msg + "."}, nil
	}

	var linesOut []string
	linesOut = append(linesOut, fmt.Sprintf("Found %d memory entries:\n", len(filtered)))
	for _, e := range filtered {
		text := e.Text
		if len(text) > 150 {
			text = text[:150] + "..."
		}
		linesOut = append(linesOut, formatMemoryLine(e, text))
	}
	return &Result{OK: true, Results: strings.Join(linesOut, "\n")}, nil
}

func memoryAdd(mgr MemoryManager, vec MemoryVector, owner string, lines []string) (*Result, error) {
	if len(lines) < 2 {
		return errorResult("Add needs line 2: memory text"), nil
	}
	text := strings.TrimSpace(lines[1])
	category := "fact"
	if len(lines) > 2 && strings.TrimSpace(lines[2]) != "" {
		category = strings.ToLower(strings.TrimSpace(lines[2]))
	}
	if text == "" {
		return errorResult("Memory text cannot be empty"), nil
	}

	entry, err := mgr.AddEntry(text, "ai_agent", category, owner)
	if err != nil {
		return errorResult(fmt.Sprintf("add failed: %v", err)), nil
	}
	// Append to persistent store via Save(LoadAll() + [new]).
	all := mgr.LoadAll()
	all = append(all, entry)
	if err := mgr.Save(all); err != nil {
		return errorResult(fmt.Sprintf("save failed: %v", err)), nil
	}

	// Update vector index if available.
	if vec != nil && vec.Healthy() {
		_ = vec.Add(entry.ID, text) // best-effort, swallow errors
	}

	return &Result{
		OK:      true,
		Action:  "add",
		Details: map[string]any{"memory_id": entry.ID},
		Results: fmt.Sprintf("Memory added: [%s] %s", category, text),
	}, nil
}

func memoryEdit(mgr MemoryManager, vec MemoryVector, owner string, lines []string, now int64) (*Result, error) {
	if len(lines) < 3 {
		return errorResult("Edit needs line 2: memory_id, line 3: new text"), nil
	}
	memID := strings.TrimSpace(lines[1])
	newText := strings.TrimSpace(lines[2])
	if newText == "" {
		return errorResult("New text cannot be empty"), nil
	}

	all := mgr.LoadAll()
	fullID := ""
	updated := false
	for i, e := range all {
		if !strings.HasPrefix(e.ID, memID) {
			continue
		}
		if owner != "" && e.Owner != "" && e.Owner != owner {
			// Ownership mismatch — hide existence.
			return errorResult(fmt.Sprintf("Memory '%s' not found", memID)), nil
		}
		e.Text = newText
		e.Owner = owner // refresh owner on edit so future owner-filter is consistent
		all[i] = e
		fullID = e.ID
		updated = true
		break
	}
	if !updated {
		return errorResult(fmt.Sprintf("Memory '%s' not found", memID)), nil
	}
	if err := mgr.Save(all); err != nil {
		return errorResult(fmt.Sprintf("save failed: %v", err)), nil
	}

	// Vector index follows edit (best-effort).
	if vec != nil && vec.Healthy() {
		_ = vec.Add(fullID, newText)
	}

	return &Result{
		OK:      true,
		Action:  "edit",
		Details: map[string]any{"memory_id": memID, "timestamp": now},
		Results: fmt.Sprintf("Memory updated: %s", newText),
	}, nil
}

func memoryDelete(mgr MemoryManager, vec MemoryVector, owner string, lines []string) (*Result, error) {
	if len(lines) < 2 {
		return errorResult("Delete needs line 2: memory_id"), nil
	}
	memID := strings.TrimSpace(lines[1])

	all := mgr.LoadAll()
	keep := all[:0:0]
	fullID := ""
	deleted := false
	for _, e := range all {
		if !deleted && strings.HasPrefix(e.ID, memID) {
			if owner != "" && e.Owner != "" && e.Owner != owner {
				return errorResult(fmt.Sprintf("Memory '%s' not found", memID)), nil
			}
			fullID = e.ID
			deleted = true
			continue
		}
		keep = append(keep, e)
	}
	if !deleted {
		return errorResult(fmt.Sprintf("Memory '%s' not found", memID)), nil
	}
	if err := mgr.Save(keep); err != nil {
		return errorResult(fmt.Sprintf("save failed: %v", err)), nil
	}

	// Remove from vector index.
	if vec != nil && fullID != "" && vec.Healthy() {
		_ = vec.Remove(fullID)
	}

	return &Result{
		OK:      true,
		Action:  "delete",
		Details: map[string]any{"memory_id": memID},
		Results: fmt.Sprintf("Memory '%s' deleted", memID),
	}, nil
}

func memorySearch(mgr MemoryManager, owner string, lines []string) (*Result, error) {
	if len(lines) < 2 {
		return errorResult("Search needs line 2: query"), nil
	}
	query := strings.TrimSpace(lines[1])
	if query == "" {
		return errorResult("Search query cannot be empty"), nil
	}
	entries := mgr.Load(owner)
	q := strings.ToLower(query)
	results := make([]MemoryEntry, 0, 20)
	for _, e := range entries {
		if strings.Contains(strings.ToLower(e.Text), q) {
			results = append(results, e)
			if len(results) >= 20 {
				break
			}
		}
	}
	if len(results) == 0 {
		return &Result{OK: true, Results: fmt.Sprintf("No memories found matching '%s'.", query)}, nil
	}
	var linesOut []string
	linesOut = append(linesOut, fmt.Sprintf("Found %d matching memories:\n", len(results)))
	for _, e := range results {
		linesOut = append(linesOut, formatMemoryLine(e, e.Text))
	}
	return &Result{OK: true, Results: strings.Join(linesOut, "\n")}, nil
}

// formatMemoryLine builds one "- [cat] `id8` — text" entry, matching the
// Python module's display format.
func formatMemoryLine(e MemoryEntry, text string) string {
	id := e.ID
	if len(id) > 8 {
		id = id[:8]
	}
	return fmt.Sprintf("- [%s] `%s` — %s", e.Category, id, text)
}

func errorResult(msg string) *Result {
	return &Result{OK: false, Error: msg}
}
