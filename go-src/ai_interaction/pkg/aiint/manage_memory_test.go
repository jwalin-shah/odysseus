package aiint

import (
	"strings"
	"testing"
)

// memMgr is a deterministic in-memory MemoryManager. It backs Load/LoadAll
// out of an explicit slice so tests can prove ownership + ordering. Save
// replaces the slice. AddEntry mints a synthetic id.
type memMgr struct {
	store []MemoryEntry
}

func newMemMgr(initial ...MemoryEntry) *memMgr {
	cp := make([]MemoryEntry, len(initial))
	copy(cp, initial)
	return &memMgr{store: cp}
}

func (m *memMgr) Load(owner string) []MemoryEntry {
	out := make([]MemoryEntry, 0, len(m.store))
	for _, e := range m.store {
		if owner != "" && e.Owner != "" && e.Owner != owner {
			continue
		}
		out = append(out, e)
	}
	return out
}
func (m *memMgr) LoadAll() []MemoryEntry {
	cp := make([]MemoryEntry, len(m.store))
	copy(cp, m.store)
	return cp
}
func (m *memMgr) AddEntry(text, source, category, owner string) (MemoryEntry, error) {
	id := memID(len(m.store) + 1)
	return MemoryEntry{ID: id, Text: text, Category: category, Owner: owner}, nil
}
func (m *memMgr) Save(entries []MemoryEntry) error {
	m.store = make([]MemoryEntry, len(entries))
	copy(m.store, entries)
	return nil
}

// memID mirrors the Python UUID-style 8-char prefix that the rest of the
// module uses for display. Deterministic so tests can match on it.
func memID(n int) string {
	const digits = "0123456789abcdef"
	out := make([]byte, 8)
	for i := 7; i >= 0; i-- {
		out[i] = digits[n&0xf]
		n >>= 4
	}
	return string(out)
}

// countingVec records add/remove calls so tests can verify the vector path
// is taken (or skipped when unhealthy).
type countingVec struct {
	healthy   bool
	addCalls  int
	remCalls  int
	lastAddID string
	lastAddTx string
	lastRemID string
}

func (c *countingVec) Healthy() bool { return c.healthy }
func (c *countingVec) Add(id, text string) error {
	c.addCalls++
	c.lastAddID = id
	c.lastAddTx = text
	return nil
}
func (c *countingVec) Remove(id string) error { c.remCalls++; c.lastRemID = id; return nil }

func TestManageMemory_NoManager(t *testing.T) {
	r, err := ManageMemory("list", nil, nil, "alice")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if r.OK {
		t.Fatalf("expected ok=false without manager, got %+v", r)
	}
	if !strings.Contains(r.Error, "Memory manager not available") {
		t.Fatalf("expected 'Memory manager not available', got %q", r.Error)
	}
}

func TestManageMemory_List_Empty(t *testing.T) {
	mgr := newMemMgr()
	r, err := ManageMemory("list", mgr, nil, "alice")
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if !strings.Contains(r.Results, "No memories found") {
		t.Fatalf("expected empty message, got %q", r.Results)
	}
}

func TestManageMemory_List_All(t *testing.T) {
	mgr := newMemMgr(
		MemoryEntry{ID: memID(1), Text: "first memory", Category: "fact", Owner: "alice"},
		MemoryEntry{ID: memID(2), Text: "second memory", Category: "event", Owner: "alice"},
	)
	r, err := ManageMemory("list", mgr, nil, "alice")
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if !strings.Contains(r.Results, "first memory") || !strings.Contains(r.Results, "second memory") {
		t.Fatalf("expected both entries listed, got %q", r.Results)
	}
	if !strings.Contains(r.Results, "Found 2 memory entries") {
		t.Fatalf("expected count header, got %q", r.Results)
	}
}

func TestManageMemory_List_CategoryFilter(t *testing.T) {
	mgr := newMemMgr(
		MemoryEntry{ID: memID(1), Text: "fact entry", Category: "fact", Owner: "alice"},
		MemoryEntry{ID: memID(2), Text: "event entry", Category: "event", Owner: "alice"},
	)
	r, _ := ManageMemory("list\nfact", mgr, nil, "alice")
	if !strings.Contains(r.Results, "fact entry") {
		t.Fatalf("expected fact entry, got %q", r.Results)
	}
	if strings.Contains(r.Results, "event entry") {
		t.Fatalf("event entry should be filtered out, got %q", r.Results)
	}
}

func TestManageMemory_Add_BasicAndVectorPath(t *testing.T) {
	mgr := newMemMgr()
	vec := &countingVec{healthy: true}
	r, err := ManageMemory("add\nI like Go", mgr, vec, "alice")
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if !strings.Contains(r.Results, "Memory added: [fact] I like Go") {
		t.Fatalf("unexpected add result %q", r.Results)
	}
	if r.Action != "add" {
		t.Fatalf("expected action=add, got %q", r.Action)
	}
	if vec.addCalls != 1 {
		t.Fatalf("expected vector.Add called once, got %d", vec.addCalls)
	}
	if !strings.HasPrefix(vec.lastAddID, "") || vec.lastAddID == "" {
		t.Fatalf("expected non-empty vector id, got %q", vec.lastAddID)
	}
	if len(mgr.store) != 1 {
		t.Fatalf("expected 1 entry persisted, got %d", len(mgr.store))
	}
}

func TestManageMemory_Add_UnhealthyVector_NoOp(t *testing.T) {
	mgr := newMemMgr()
	vec := &countingVec{healthy: false}
	r, err := ManageMemory("add\ntext", mgr, vec, "alice")
	if err != nil || !r.OK {
		t.Fatalf("expected ok, got err=%v result=%+v", err, r)
	}
	if vec.addCalls != 0 {
		t.Fatalf("expected vector.Add to be skipped when unhealthy, got %d", vec.addCalls)
	}
}

func TestManageMemory_Add_EmptyText(t *testing.T) {
	mgr := newMemMgr()
	r, _ := ManageMemory("add\n   ", mgr, nil, "alice")
	if r.OK {
		t.Fatalf("expected ok=false for empty text, got %+v", r)
	}
	if !strings.Contains(r.Error, "Memory text cannot be empty") {
		t.Fatalf("expected empty-text error, got %q", r.Error)
	}
}

func TestManageMemory_Edit_OwnershipAndVectorPath(t *testing.T) {
	mgr := newMemMgr(
		MemoryEntry{ID: memID(1), Text: "old text", Category: "fact", Owner: "alice"},
	)
	vec := &countingVec{healthy: true}

	// Wrong owner -> "not found".
	r, _ := ManageMemory("edit\n"+memID(1)+"\nnew text", mgr, vec, "bob")
	if r.OK {
		t.Fatalf("expected ownership rejection, got %+v", r)
	}
	if !strings.Contains(r.Error, "not found") {
		t.Fatalf("expected 'not found' for ownership mismatch, got %q", r.Error)
	}

	// Correct owner -> updated + vector.Add called.
	r, _ = ManageMemory("edit\n"+memID(1)+"\nnew text", mgr, vec, "alice")
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	if vec.addCalls != 1 || vec.lastAddTx != "new text" {
		t.Fatalf("expected vector.Add called once with new text, got addCalls=%d last=%q", vec.addCalls, vec.lastAddTx)
	}
	if mgr.store[0].Text != "new text" {
		t.Fatalf("expected persisted text updated, got %q", mgr.store[0].Text)
	}
}

func TestManageMemory_Edit_MissingID(t *testing.T) {
	mgr := newMemMgr(
		MemoryEntry{ID: memID(1), Text: "first", Category: "fact", Owner: "alice"},
	)
	r, _ := ManageMemory("edit\ndeadbeef\nnew text", mgr, nil, "alice")
	if r.OK {
		t.Fatalf("expected ok=false for missing id, got %+v", r)
	}
	if !strings.Contains(r.Error, "not found") {
		t.Fatalf("expected 'not found', got %q", r.Error)
	}
}

func TestManageMemory_Delete_OwnershipAndVectorPath(t *testing.T) {
	mgr := newMemMgr(
		MemoryEntry{ID: memID(1), Text: "doomed", Category: "fact", Owner: "alice"},
	)
	vec := &countingVec{healthy: true}

	// Wrong owner -> "not found" + no delete.
	r, _ := ManageMemory("delete\n"+memID(1), mgr, vec, "bob")
	if r.OK {
		t.Fatalf("expected ownership rejection, got %+v", r)
	}
	if len(mgr.store) != 1 {
		t.Fatalf("ownership mismatch must not delete, store=%d", len(mgr.store))
	}
	if vec.remCalls != 0 {
		t.Fatalf("ownership mismatch must not call vector.Remove, got %d", vec.remCalls)
	}

	// Correct owner -> deleted + vector.Remove called.
	r, _ = ManageMemory("delete\n"+memID(1), mgr, vec, "alice")
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	if vec.remCalls != 1 || vec.lastRemID == "" {
		t.Fatalf("expected vector.Remove called once with full id, got remCalls=%d last=%q", vec.remCalls, vec.lastRemID)
	}
	if len(mgr.store) != 0 {
		t.Fatalf("expected store empty, got %d entries", len(mgr.store))
	}
}

func TestManageMemory_Delete_MissingID(t *testing.T) {
	mgr := newMemMgr(
		MemoryEntry{ID: memID(1), Text: "keep", Category: "fact", Owner: "alice"},
	)
	r, _ := ManageMemory("delete\nzzzz", mgr, nil, "alice")
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "not found") {
		t.Fatalf("expected 'not found', got %q", r.Error)
	}
}

func TestManageMemory_Search_NoHits(t *testing.T) {
	mgr := newMemMgr(
		MemoryEntry{ID: memID(1), Text: "alpha", Category: "fact", Owner: "alice"},
	)
	r, _ := ManageMemory("search\nomega", mgr, nil, "alice")
	if !r.OK {
		t.Fatalf("expected ok, got %+v", r)
	}
	if !strings.Contains(r.Results, "No memories found matching") {
		t.Fatalf("expected no-hit message, got %q", r.Results)
	}
}

func TestManageMemory_Search_Hits(t *testing.T) {
	mgr := newMemMgr(
		MemoryEntry{ID: memID(1), Text: "alpha bravo", Category: "fact", Owner: "alice"},
		MemoryEntry{ID: memID(2), Text: "alpha charlie", Category: "fact", Owner: "alice"},
		MemoryEntry{ID: memID(3), Text: "delta", Category: "fact", Owner: "alice"},
	)
	r, _ := ManageMemory("search\nalpha", mgr, nil, "alice")
	if !strings.Contains(r.Results, "alpha bravo") || !strings.Contains(r.Results, "alpha charlie") {
		t.Fatalf("expected both alpha entries, got %q", r.Results)
	}
	if strings.Contains(r.Results, "delta") {
		t.Fatalf("delta should not match, got %q", r.Results)
	}
}

func TestManageMemory_UnknownAction(t *testing.T) {
	mgr := newMemMgr()
	r, _ := ManageMemory("frobnicate", mgr, nil, "alice")
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "Unknown action") {
		t.Fatalf("expected 'Unknown action', got %q", r.Error)
	}
}

func TestManageMemory_EmptyContent(t *testing.T) {
	mgr := newMemMgr()
	r, _ := ManageMemory("", mgr, nil, "alice")
	if r.OK {
		t.Fatalf("expected ok=false, got %+v", r)
	}
	if !strings.Contains(r.Error, "Need at least 1 line") {
		t.Fatalf("expected 'Need at least 1 line', got %q", r.Error)
	}
}
