package aiint

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// ManageRAG dispatches the manage_rag tool. Mirrors Python's
// `do_manage_rag` actions: list, add_directory, remove_directory.
//
// The Python module needs `~` expansion + a real os.path.isdir() check
// before indexing. Here we honor both by reading the home dir from the
// Manager (defaults to os.UserHomeDir) and checking the directory via
// os.Stat on the resolved path.
func ManageRAG(content string, mgr *Manager) (*Result, error) {
	if mgr == nil {
		return errorResult("Manager not configured"), nil
	}
	rag := mgr.RAG
	pdocs := mgr.PersonalDocs

	lines := strings.Split(strings.TrimSpace(content), "\n")
	if len(lines) == 0 || strings.TrimSpace(lines[0]) == "" {
		return errorResult("No action specified"), nil
	}
	action := strings.ToLower(strings.TrimSpace(lines[0]))

	switch action {
	case "list":
		return ragList(pdocs)
	case "add_directory":
		return ragAddDirectory(content, rag, mgr)
	case "remove_directory":
		return ragRemoveDirectory(content, pdocs)
	default:
		return errorResult(fmt.Sprintf("Unknown action '%s'. Use: list, add_directory, remove_directory", action)), nil
	}
}

func ragList(pdocs PersonalDocsManager) (*Result, error) {
	if pdocs == nil {
		return &Result{OK: true, Results: "Personal docs manager not available. RAG may not be configured."}, nil
	}
	dirs := pdocs.IndexedDirectories()
	files := pdocs.Index()

	var out []string
	if len(dirs) > 0 {
		out = append(out, fmt.Sprintf("**Indexed directories (%d):**", len(dirs)))
		for _, d := range dirs {
			out = append(out, "  - `"+d+"`")
		}
	}
	if len(files) > 0 {
		out = append(out, fmt.Sprintf("\n**Indexed files (%d):**", len(files)))
		limit := len(files)
		if limit > 50 {
			limit = 50
		}
		for _, f := range files[:limit] {
			name := f.Name
			if name == "" {
				name = f.Path
			}
			out = append(out, "  - "+name)
		}
		if len(files) > 50 {
			out = append(out, fmt.Sprintf("  ... and %d more", len(files)-50))
		}
	}
	if len(out) == 0 {
		return &Result{OK: true, Results: "No files or directories indexed in RAG."}, nil
	}
	return &Result{OK: true, Results: strings.Join(out, "\n")}, nil
}

func ragAddDirectory(content string, rag RagManager, mgr *Manager) (*Result, error) {
	lines := strings.Split(strings.TrimSpace(content), "\n")
	if len(lines) < 2 {
		return errorResult("add_directory needs line 2: directory path"), nil
	}
	raw := strings.TrimSpace(lines[1])
	if raw == "" {
		return errorResult("add_directory needs line 2: directory path"), nil
	}

	home, _ := mgr.resolveHome()
	resolved := ExpandHome(home, raw)
	if !filepath.IsAbs(resolved) {
		// Preserve Python behavior: relative paths are kept as-is (caller's cwd).
		// But the Python module rejects if the directory doesn't exist via
		// os.path.isdir(). We do the same.
		var err error
		resolved, err = filepath.Abs(resolved)
		if err != nil {
			return errorResult(fmt.Sprintf("Failed to resolve path: %v", err)), nil
		}
	}

	info, err := os.Stat(resolved)
	if err != nil || !info.IsDir() {
		return errorResult(fmt.Sprintf("Directory not found: %s", resolved)), nil
	}

	if rag == nil {
		return errorResult("RAG manager not available"), nil
	}

	result, err := rag.IndexPersonalDocuments(resolved)
	if err != nil {
		return errorResult(fmt.Sprintf("Failed to index directory: %v", err)), nil
	}

	return &Result{
		OK:      true,
		Action:  "add_directory",
		Details: map[string]any{"directory": resolved},
		Results: fmt.Sprintf("Directory '%s' added to RAG index (%d files indexed)", resolved, result.Indexed),
	}, nil
}

func ragRemoveDirectory(content string, pdocs PersonalDocsManager) (*Result, error) {
	lines := strings.Split(strings.TrimSpace(content), "\n")
	if len(lines) < 2 {
		return errorResult("remove_directory needs line 2: directory path"), nil
	}
	dir := strings.TrimSpace(lines[1])
	if dir == "" {
		return errorResult("remove_directory needs line 2: directory path"), nil
	}
	if pdocs == nil {
		return errorResult("Personal docs manager not available"), nil
	}
	if err := pdocs.RemoveDirectory(dir); err != nil {
		return errorResult(fmt.Sprintf("Failed to remove directory: %v", err)), nil
	}
	return &Result{
		OK:      true,
		Action:  "remove_directory",
		Details: map[string]any{"directory": dir},
		Results: fmt.Sprintf("Directory '%s' removed from RAG index", dir),
	}, nil
}
