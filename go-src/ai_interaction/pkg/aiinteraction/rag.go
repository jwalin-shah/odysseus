package aiinteraction

import (
	"fmt"
	"os"
	"strings"
)

// ParseRAGAction mirrors the do_manage_rag parser. The Python source
// accepts three actions — list, add_directory, remove_directory — and
// rejects unknown verbs with the same message shape as manage_memory.
//
// Errors carry the "error: " prefix.
func ParseRAGAction(content string) (*RAGAction, error) {
	trimmed := strings.TrimSpace(content)
	if trimmed == "" {
		return nil, fmt.Errorf("error: No action specified")
	}
	lines := strings.Split(trimmed, "\n")
	action := strings.ToLower(strings.TrimSpace(lines[0]))
	out := &RAGAction{Action: action}
	switch action {
	case "list":
		return out, nil
	case "add_directory", "remove_directory":
		if len(lines) < 2 || strings.TrimSpace(lines[1]) == "" {
			return out, fmt.Errorf("error: %s needs line 2: directory path", action)
		}
		out.Directory = strings.TrimSpace(lines[1])
		return out, nil
	default:
		return out, fmt.Errorf("error: Unknown action '%s'. Use: list, add_directory, remove_directory", action)
	}
}

// ExpandDirectory mirrors the `os.path.expanduser` call in
// do_manage_rag's add_directory branch. The Python source only expands
// "~"; the Go port uses the user's home directory lookup the same way
// (HOME on Unix, USERPROFILE on Windows). For unit tests that don't
// want a real lookup, set HOME to a known value via t.Setenv.
func ExpandDirectory(p string) string {
	if p == "" {
		return p
	}
	if p[0] != '~' {
		return p
	}
	home := ""
	for _, env := range []string{"HOME", "USERPROFILE"} {
		if v := os.Getenv(env); v != "" {
			home = v
			break
		}
	}
	if home == "" {
		return p
	}
	if p == "~" {
		return home
	}
	if strings.HasPrefix(p, "~/") {
		return home + p[1:]
	}
	return p
}

// FormatRAGList mirrors the rendering do_manage_rag's list branch
// produces. The Python source shows:
//
//   - indexed directories first (with a header if any);
//   - then indexed files (truncated at 50 entries);
//   - if both are empty, the empty-state message.
//
// The Go port keeps the same text and ordering so callers can drop the
// output into {"results": "..."} without translation.
//
// indexedFiles is the list of {name, ...} dicts (or strings) the
// personal_docs manager exposes via its `index` attribute. Pass nil
// when the manager has no files. The function inspects each entry's
// type and renders strings bare, dicts by their "name" field.
func FormatRAGList(indexedFiles []any, indexedDirs []string) string {
	var b strings.Builder
	if len(indexedDirs) > 0 {
		fmt.Fprintf(&b, "**Indexed directories (%d):**\n", len(indexedDirs))
		for _, d := range indexedDirs {
			fmt.Fprintf(&b, "  - `%s`\n", d)
		}
	}
	if len(indexedFiles) > 0 {
		if b.Len() > 0 {
			b.WriteString("\n")
		}
		fmt.Fprintf(&b, "**Indexed files (%d):**\n", len(indexedFiles))
		shown := indexedFiles
		truncated := false
		if len(shown) > 50 {
			shown = shown[:50]
			truncated = true
		}
		for _, f := range shown {
			switch v := f.(type) {
			case string:
				fmt.Fprintf(&b, "  - %s\n", v)
			case map[string]any:
				if name, ok := v["name"].(string); ok {
					fmt.Fprintf(&b, "  - %s\n", name)
				} else {
					fmt.Fprintf(&b, "  - %v\n", v)
				}
			default:
				fmt.Fprintf(&b, "  - %v\n", v)
			}
		}
		if truncated {
			fmt.Fprintf(&b, "  ... and %d more\n", len(indexedFiles)-50)
		}
	}
	out := strings.TrimRight(b.String(), "\n")
	if out == "" {
		return "No files or directories indexed in RAG."
	}
	return out
}
