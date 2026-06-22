package aiint

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// stubRAG satisfies RagManager for tests. IndexPersonalDirectories
// appends the directory to a tracked list and reports one file indexed.
type stubRAG struct {
	indexed []string
}

func (s *stubRAG) IndexPersonalDocuments(directory string) (RAGIndexResult, error) {
	s.indexed = append(s.indexed, directory)
	return RAGIndexResult{Indexed: 1}, nil
}

// stubPDocs satisfies PersonalDocsManager for tests.
type stubPDocs struct {
	dirs  []string
	files []RAGDoc
	rmLog []string
}

func (s *stubPDocs) IndexedDirectories() []string { return s.dirs }
func (s *stubPDocs) Index() []RAGDoc              { return s.files }
func (s *stubPDocs) RemoveDirectory(directory string) error {
	s.rmLog = append(s.rmLog, directory)
	for i, d := range s.dirs {
		if d == directory {
			s.dirs = append(s.dirs[:i], s.dirs[i+1:]...)
			break
		}
	}
	return nil
}

func TestManageRAG_List_Happy(t *testing.T) {
	tmp := t.TempDir()
	_ = tmp
	mgr := &Manager{
		PersonalDocs: &stubPDocs{
			dirs:  []string{"/tmp/a", "/tmp/b"},
			files: []RAGDoc{{Path: "/tmp/a/x.txt", Name: "x.txt"}},
		},
		RAG: &stubRAG{},
	}
	r, err := ManageRAG("list", mgr)
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if !strings.Contains(r.Results, "/tmp/a") || !strings.Contains(r.Results, "/tmp/b") {
		t.Fatalf("expected both dirs in list, got %q", r.Results)
	}
	if !strings.Contains(r.Results, "Indexed files") {
		t.Fatalf("expected files header, got %q", r.Results)
	}
}

func TestManageRAG_List_MissingPDocs(t *testing.T) {
	mgr := &Manager{RAG: &stubRAG{}}
	r, _ := ManageRAG("list", mgr)
	if !r.OK {
		t.Fatalf("expected ok with informational message, got %+v", r)
	}
	if !strings.Contains(r.Results, "Personal docs manager not available") {
		t.Fatalf("expected availability message, got %q", r.Results)
	}
}

func TestManageRAG_List_EmptyIndex(t *testing.T) {
	mgr := &Manager{
		PersonalDocs: &stubPDocs{},
		RAG:          &stubRAG{},
	}
	r, _ := ManageRAG("list", mgr)
	if !r.OK || !strings.Contains(r.Results, "No files or directories") {
		t.Fatalf("expected empty-index message, got %+v", r)
	}
}

func TestManageRAG_AddDirectory_Happy(t *testing.T) {
	dir := t.TempDir()
	rag := &stubRAG{}
	mgr := &Manager{RAG: rag, PersonalDocs: &stubPDocs{}}

	r, err := ManageRAG(fmt.Sprintf("add_directory\n%s", dir), mgr)
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if r.Action != "add_directory" {
		t.Fatalf("expected action=add_directory, got %q", r.Action)
	}
	if !strings.Contains(r.Results, "added to RAG index") {
		t.Fatalf("expected add confirmation, got %q", r.Results)
	}
	if len(rag.indexed) != 1 || rag.indexed[0] != dir {
		t.Fatalf("expected RAG.IndexPersonalDocuments called with %s, got %v", dir, rag.indexed)
	}
}

func TestManageRAG_AddDirectory_Nonexistent(t *testing.T) {
	mgr := &Manager{RAG: &stubRAG{}, PersonalDocs: &stubPDocs{}}
	r, _ := ManageRAG("add_directory\n/nonexistent/path/here/12345", mgr)
	if r.OK {
		t.Fatalf("expected ok=false for missing dir, got %+v", r)
	}
	if !strings.Contains(r.Error, "Directory not found") {
		t.Fatalf("expected 'Directory not found', got %q", r.Error)
	}
}

func TestManageRAG_AddDirectory_NotADirectory(t *testing.T) {
	// A regular file masquerading as a directory.
	tmpFile := filepath.Join(t.TempDir(), "regular-file.txt")
	mgr := &Manager{RAG: &stubRAG{}, PersonalDocs: &stubPDocs{}}
	r, _ := ManageRAG("add_directory\n"+tmpFile, mgr)
	if r.OK {
		t.Fatalf("expected ok=false for file (not dir), got %+v", r)
	}
	if !strings.Contains(r.Error, "Directory not found") {
		t.Fatalf("expected 'Directory not found', got %q", r.Error)
	}
}

func TestManageRAG_AddDirectory_HomeExpansion(t *testing.T) {
	tmp := t.TempDir()
	// Create ~/docs so the existence check passes.
	if err := os.Mkdir(filepath.Join(tmp, "docs"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	mgr := &Manager{
		RAG:          &stubRAG{},
		PersonalDocs: &stubPDocs{},
		HomeDir:      func() (string, error) { return tmp, nil },
	}
	r, err := ManageRAG("add_directory\n~/docs", mgr)
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if !strings.Contains(r.Results, filepath.Join(tmp, "docs")) {
		t.Fatalf("expected ~ to expand under t.TempDir, got %q", r.Results)
	}
}

func TestManageRAG_AddDirectory_MissingRAG(t *testing.T) {
	tmp := t.TempDir()
	mgr := &Manager{PersonalDocs: &stubPDocs{}} // no RAG
	r, _ := ManageRAG("add_directory\n"+tmp, mgr)
	if r.OK {
		t.Fatalf("expected ok=false without rag, got %+v", r)
	}
	if !strings.Contains(r.Error, "RAG manager not available") {
		t.Fatalf("expected 'RAG manager not available', got %q", r.Error)
	}
}

func TestManageRAG_RemoveDirectory_Happy(t *testing.T) {
	pdocs := &stubPDocs{dirs: []string{"/tmp/a", "/tmp/b"}}
	mgr := &Manager{PersonalDocs: pdocs, RAG: &stubRAG{}}
	r, err := ManageRAG("remove_directory\n/tmp/a", mgr)
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if r.Action != "remove_directory" {
		t.Fatalf("expected action=remove_directory, got %q", r.Action)
	}
	if !strings.Contains(r.Results, "removed from RAG index") {
		t.Fatalf("expected remove confirmation, got %q", r.Results)
	}
	if len(pdocs.rmLog) != 1 || pdocs.rmLog[0] != "/tmp/a" {
		t.Fatalf("expected RemoveDirectory called with /tmp/a, got %v", pdocs.rmLog)
	}
}

func TestManageRAG_RemoveDirectory_MissingPDocs(t *testing.T) {
	mgr := &Manager{RAG: &stubRAG{}} // no pdocs
	r, _ := ManageRAG("remove_directory\n/tmp/a", mgr)
	if r.OK {
		t.Fatalf("expected ok=false without pdocs, got %+v", r)
	}
	if !strings.Contains(r.Error, "Personal docs manager not available") {
		t.Fatalf("expected 'Personal docs manager not available', got %q", r.Error)
	}
}

func TestManageRAG_UnknownAction(t *testing.T) {
	mgr := &Manager{RAG: &stubRAG{}, PersonalDocs: &stubPDocs{}}
	r, _ := ManageRAG("frobnicate", mgr)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "Unknown action") {
		t.Fatalf("expected 'Unknown action', got %q", r.Error)
	}
}

func TestManageRAG_NoManager(t *testing.T) {
	r, _ := ManageRAG("list", nil)
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
}

func TestExpandHome(t *testing.T) {
	cases := []struct {
		in   string
		want string
	}{
		{"~/x", "/home/u/x"},
		{"~", "/home/u"},
		{"/abs/path", "/abs/path"},
		{"rel/path", "rel/path"},
		{"", ""},
	}
	for _, c := range cases {
		got := ExpandHome("/home/u", c.in)
		if got != c.want {
			t.Fatalf("ExpandHome(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}
