// Command document_actions is a small CLI that exercises the
// document_actions package against an in-memory store seeded with sample
// documents covering each junk rule plus a duplicate group. It prints the
// resulting TidyReport and exits 0. A no-change run (SentinelNoChange) also
// exits 0 — the sentinel is a domain signal, not an error.
package main

import (
	"fmt"
	"os"
	"time"

	"odysseus/document_actions"
)

// memStore is a minimal in-memory implementation of document_actions.Store
// used by the CLI binary. Delete is recorded as a set of ids; the CLI
// prints the deleted ids at the end so operators can see exactly what
// would be removed.
type memStore struct {
	docs    []document_actions.Document
	deleted map[int64]struct{}
}

func newMemStore(docs ...document_actions.Document) *memStore {
	return &memStore{docs: docs, deleted: map[int64]struct{}{}}
}

func (m *memStore) ListByOwner(owner string) ([]document_actions.Document, error) {
	if owner == "" {
		out := make([]document_actions.Document, len(m.docs))
		copy(out, m.docs)
		return out, nil
	}
	var out []document_actions.Document
	for _, d := range m.docs {
		if d.Owner == owner {
			out = append(out, d)
		}
	}
	return out, nil
}

func (m *memStore) Delete(ids []int64) error {
	for _, id := range ids {
		m.deleted[id] = struct{}{}
	}
	return nil
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "document_actions:", err)
		os.Exit(1)
	}
}

func run() error {
	store := sampleStore()

	report, err := document_actions.Tidy(store, "alice")
	if err != nil && err != document_actions.SentinelNoChange {
		return err
	}
	if report == nil {
		fmt.Println("no report returned")
		return nil
	}

	fmt.Printf("scanned: %d\n", report.Scanned)
	fmt.Printf("deleted: %d\n", report.Deleted)
	fmt.Printf("kept:    %d\n", report.Kept)
	if len(report.Examples) > 0 {
		fmt.Println("examples:")
		for _, ex := range report.Examples {
			fmt.Printf("  - %s\n", ex)
		}
	} else {
		fmt.Println("examples: (none)")
	}
	if err == document_actions.SentinelNoChange {
		fmt.Println("status: no-op (nothing to delete)")
	}
	return nil
}

// sampleStore seeds the in-memory store with documents covering each junk
// rule plus a duplicate group. The TidyReport should delete docs 1-5 and
// 11 (the duplicate of 10), and keep doc 10.
func sampleStore() *memStore {
	created := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
	updated := time.Date(2024, 6, 1, 0, 0, 0, 0, time.UTC)
	upd := updated
	docs := []document_actions.Document{
		// Rule 1: empty / placeholder
		{ID: 1, Title: "anything", Content: "", Owner: "alice", CreatedAt: created},
		{ID: 2, Title: "x", Content: "# Untitled", Owner: "alice", CreatedAt: created},

		// Rule 2: junk title (mixed case to exercise normalization)
		{ID: 3, Title: "TEST", Content: "this content would be fine on its own but the title is junk", Owner: "alice", CreatedAt: created},
		{ID: 4, Title: "Asdf", Content: "another perfectly valid document body of real length to keep", Owner: "alice", CreatedAt: created},

		// Rule 3: throwaway content (stripped content == "draft")
		{ID: 5, Title: "My Note", Content: "## draft", Owner: "alice", CreatedAt: created},

		// Rule 4: email quote-chain only
		{ID: 6, Title: "Re: hello", Content: "On Mon, 1 Jan 2024, alice@example.com wrote:\n> hello there\n> how are you", Owner: "alice", CreatedAt: created},

		// Duplicate group: same (title, fingerprint), one short and one long.
		// Long one is kept (longer real content), short one deleted.
		{ID: 10, Title: "Note", Content: "the real text upload_id=\"abc\" id=ann-xyz1 trailing content here for length",
			Owner: "alice", CreatedAt: created, UpdatedAt: &upd},
		{ID: 11, Title: "Note", Content: "the real text upload_id=\"def\" id=ann-xyz2 trailing",
			Owner: "alice", CreatedAt: created},

		// A clean survivor that should be kept untouched.
		{ID: 20, Title: "Meeting notes", Content: "Discussed the quarterly roadmap and the open action items for next week",
			Owner: "alice", CreatedAt: created},

		// Bob's docs should be ignored when owner=alice.
		{ID: 100, Title: "x", Content: "", Owner: "bob", CreatedAt: created},
	}
	return newMemStore(docs...)
}
