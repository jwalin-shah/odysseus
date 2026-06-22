package document_actions

import (
	"errors"
	"reflect"
	"testing"
	"time"
)

// fakeDoc is a minimal DocumentView for tests.
type fakeDoc struct {
	id, owner, title, content string
	created                   *time.Time
	updated                   *time.Time
}

func (f *fakeDoc) GetID() string            { return f.id }
func (f *fakeDoc) GetOwner() string         { return f.owner }
func (f *fakeDoc) GetTitle() string         { return f.title }
func (f *fakeDoc) GetContent() string       { return f.content }
func (f *fakeDoc) GetCreatedAt() *time.Time { return f.created }
func (f *fakeDoc) GetUpdatedAt() *time.Time { return f.updated }

func ptr(t time.Time) *time.Time { return &t }

func TestNormTitle(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{"empty", "", ""},
		{"trim and lower", "  Hello   World  ", "hello world"},
		{"already normalised", "notes", "notes"},
		{"newlines collapse", "First\t\nLine", "first line"},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := NormTitle(tc.in)
			if got != tc.want {
				t.Errorf("NormTitle(%q) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}
}

func TestContentFingerprint(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{
			name: "upload_id is stripped",
			in:   `<div data-pdf upload_id="abc-123">x</div>`,
			want: `<div data-pdf upload_id>x</div>`,
		},
		{
			name: "annotation id is stripped",
			in:   `<span id=ann-7qZ9>highlight</span>`,
			want: `<span id=ann>highlight</span>`,
		},
		{
			name: "whitespace collapsed and lowered",
			in:   "  Hello\t\nWorld  ",
			want: "hello world",
		},
		{
			name: "empty input",
			in:   "",
			want: "",
		},
		{
			name: "non-volatile text preserved",
			in:   "Today I shipped the new endpoint.",
			want: "today i shipped the new endpoint.",
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := ContentFingerprint(tc.in)
			if got != tc.want {
				t.Errorf("ContentFingerprint(%q) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}
}

func TestRealLen(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want int
	}{
		{"empty", "", 0},
		{"plain text", "hello", 5},
		{"heading stripped", "# Title", len("Title")},
		{"all heading levels stripped", "###### deep", len("deep")},
		{"markdown emphasis stripped", "**bold** text", len("bold text")},
		{"whitespace collapsed", "a\n  b\t\tc", 5},
		{"email quote survives stripping", "> quoted line", len("quoted line")},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := RealLen(tc.in)
			if got != tc.want {
				t.Errorf("RealLen(%q) = %d, want %d", tc.in, got, tc.want)
			}
		})
	}
}

// Regression: the Python helpers previously used `(x or "")` which only
// guarded falsy. A non-string (or any truthy non-string) crashed inside
// the regex. The Go port accepts string only and documents the contract;
// non-string callers must coerce themselves. We still cover the
// empty/whitespace-only path to mirror the original.
func TestHelpersHandleEdgeInputs(t *testing.T) {
	if NormTitle("") != "" {
		t.Errorf("NormTitle of empty string must be empty")
	}
	if ContentFingerprint("") != "" {
		t.Errorf("ContentFingerprint of empty string must be empty")
	}
	if RealLen("") != 0 {
		t.Errorf("RealLen of empty string must be 0")
	}
	if RealLen("   \n\t  ") != 0 {
		t.Errorf("RealLen of whitespace-only must be 0")
	}
}

func TestRunDocumentTidy_DeletesJunk(t *testing.T) {
	docs := []DocumentView{
		&fakeDoc{id: "1", title: "test", content: "anything goes"},
		&fakeDoc{id: "2", title: "real note", content: "A real note."},
		&fakeDoc{id: "3", title: "untitled", content: ""},
		&fakeDoc{id: "4", title: "Untitled Doc", content: "# Untitled"},
		&fakeDoc{id: "5", title: "asdf", content: "asdf"},
	}
	report, err := RunDocumentTidy(docs)
	if err != nil {
		t.Fatalf("RunDocumentTidy returned error: %v", err)
	}
	if len(report.Deleted) != 4 {
		t.Errorf("expected 4 deletions, got %d", len(report.Deleted))
	}
	if len(report.Kept) != 1 {
		t.Errorf("expected 1 kept, got %d", len(report.Kept))
	}
	if got := report.Kept[0].GetID(); got != "2" {
		t.Errorf("expected to keep doc 2, kept %q", got)
	}
}

func TestRunDocumentTidy_RemovesDuplicates(t *testing.T) {
	body := "This is a real document body long enough to survive junk rules."
	docs := []DocumentView{
		&fakeDoc{id: "a", title: "My Report", content: body,
			created: ptr(time.Date(2026, 6, 1, 9, 0, 0, 0, time.UTC)),
			updated: ptr(time.Date(2026, 6, 1, 9, 0, 0, 0, time.UTC))},
		&fakeDoc{id: "b", title: "My Report", content: body,
			created: ptr(time.Date(2026, 6, 2, 9, 0, 0, 0, time.UTC)),
			updated: ptr(time.Date(2026, 6, 2, 9, 0, 0, 0, time.UTC))},
		&fakeDoc{id: "c", title: "My Report", content: body,
			created: ptr(time.Date(2026, 6, 3, 9, 0, 0, 0, time.UTC)),
			updated: ptr(time.Date(2026, 6, 3, 9, 0, 0, 0, time.UTC))},
		&fakeDoc{id: "d", title: "Unrelated", content: "Different content here."},
	}
	report, err := RunDocumentTidy(docs)
	if err != nil {
		t.Fatalf("RunDocumentTidy returned error: %v", err)
	}
	if len(report.Deleted) != 2 {
		t.Errorf("expected 2 duplicate deletions, got %d", len(report.Deleted))
	}
	if len(report.Kept) != 2 {
		t.Errorf("expected 2 kept (1 report + 1 unrelated), got %d", len(report.Kept))
	}
	// The most recent (id "c") should be the keeper.
	var keptIDs []string
	for _, d := range report.Kept {
		keptIDs = append(keptIDs, d.GetID())
	}
	if !contains(keptIDs, "c") || contains(keptIDs, "a") || contains(keptIDs, "b") {
		t.Errorf("expected the most recent duplicate to be kept; got %v", keptIDs)
	}
}

// Regression: Python's sort key used `updated_at or created_at` directly.
// On a tie with a NULL timestamp, Python raised TypeError comparing None to
// a datetime and aborted the run. The Go port sorts safely by ranking
// "has a timestamp" before the timestamp itself.
func TestRunDocumentTidy_NullTimestampsDoNotPanic(t *testing.T) {
	body := "This is a real document body long enough to survive junk rules."
	docs := []DocumentView{
		&fakeDoc{id: "null1", title: "My Report", content: body, created: nil, updated: nil},
		&fakeDoc{id: "null2", title: "My Report", content: body,
			created: ptr(time.Date(2026, 6, 1, 9, 0, 0, 0, time.UTC)),
			updated: ptr(time.Date(2026, 6, 1, 9, 0, 0, 0, time.UTC))},
	}
	report, err := RunDocumentTidy(docs)
	if err != nil {
		t.Fatalf("RunDocumentTidy panicked/wrapped: %v", err)
	}
	if len(report.Kept) != 1 {
		t.Errorf("expected 1 kept, got %d", len(report.Kept))
	}
	if len(report.Deleted) != 1 {
		t.Errorf("expected 1 deleted (one duplicate), got %d", len(report.Deleted))
	}
}

func TestRunDocumentTidy_EmptyListReturnsTaskNoop(t *testing.T) {
	_, err := RunDocumentTidy(nil)
	if !errors.Is(err, ErrTaskNoop) {
		t.Errorf("expected ErrTaskNoop, got %v", err)
	}
}

func TestRunDocumentTidy_NoJunkReturnsTaskNoop(t *testing.T) {
	docs := []DocumentView{
		&fakeDoc{id: "1", title: "Real note A", content: "Some content."},
		&fakeDoc{id: "2", title: "Real note B", content: "Other content."},
	}
	_, err := RunDocumentTidy(docs)
	if !errors.Is(err, ErrTaskNoop) {
		t.Errorf("expected ErrTaskNoop, got %v", err)
	}
}

// Upload-id variation between two imports of the same PDF must collapse to
// the same fingerprint, so they dedup rather than survive independently.
func TestRunDocumentTidy_UploadIDNoiseCollapsesForDedup(t *testing.T) {
	docs := []DocumentView{
		&fakeDoc{id: "p1", title: "Quarterly Report", content: `<div upload_id="abc-111">body</div>`,
			created: ptr(time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC))},
		&fakeDoc{id: "p2", title: "Quarterly Report", content: `<div upload_id="xyz-999">body</div>`,
			created: ptr(time.Date(2026, 2, 1, 0, 0, 0, 0, time.UTC))},
	}
	report, err := RunDocumentTidy(docs)
	if err != nil {
		t.Fatalf("RunDocumentTidy returned error: %v", err)
	}
	if len(report.Deleted) != 1 {
		t.Errorf("expected 1 dedup deletion, got %d", len(report.Deleted))
	}
}

// Annotation-id noise inside the same PDF body must also collapse.
func TestRunDocumentTidy_AnnotationIDNoiseCollapsesForDedup(t *testing.T) {
	docs := []DocumentView{
		&fakeDoc{id: "a1", title: "Annotated doc", content: `<p id=ann-7qZ9>highlight</p>`,
			created: ptr(time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC))},
		&fakeDoc{id: "a2", title: "Annotated doc", content: `<p id=ann-Ab12Cd>highlight</p>`,
			created: ptr(time.Date(2026, 2, 1, 0, 0, 0, 0, time.UTC))},
	}
	report, err := RunDocumentTidy(docs)
	if err != nil {
		t.Fatalf("RunDocumentTidy returned error: %v", err)
	}
	if len(report.Deleted) != 1 {
		t.Errorf("expected 1 dedup deletion, got %d", len(report.Deleted))
	}
}

// Email reply-chain: only quoted text and an attribution line. Should be
// removed under the email-quote rule.
func TestRunDocumentTidy_EmailQuoteChainOnly(t *testing.T) {
	body := "> quoted text from a previous email\n" +
		"> another line of quoted text\n" +
		"> third line of quoted text\n" +
		"On Mon, Jun 1, 2026, alice@example.com wrote:\n" +
		"> fourth quoted line\n"
	docs := []DocumentView{
		&fakeDoc{id: "e1", title: "Re: meeting", content: body},
	}
	report, err := RunDocumentTidy(docs)
	if err != nil {
		t.Fatalf("RunDocumentTidy returned error: %v", err)
	}
	if len(report.Deleted) != 1 {
		t.Errorf("expected email chain to be deleted, got %d deletions", len(report.Deleted))
	}
	if len(report.Kept) != 0 {
		t.Errorf("expected 0 kept, got %d", len(report.Kept))
	}
}

// A short real note is legitimate content — must NOT be deleted.
func TestRunDocumentTidy_ShortNoteSurvives(t *testing.T) {
	docs := []DocumentView{
		&fakeDoc{id: "s1", title: "grocery list", content: "milk, eggs"},
	}
	_, err := RunDocumentTidy(docs)
	if !errors.Is(err, ErrTaskNoop) {
		t.Errorf("expected ErrTaskNoop for a single short real note, got %v", err)
	}
}

func TestJunkTitlesContainsExpected(t *testing.T) {
	want := []string{"untitled", "test", "asdf", "junk", "trash"}
	for _, w := range want {
		if _, ok := JunkTitles[w]; !ok {
			t.Errorf("JunkTitles missing expected entry %q", w)
		}
	}
}

func TestDocumentAdapter(t *testing.T) {
	now := time.Date(2026, 6, 1, 9, 0, 0, 0, time.UTC)
	d := &Document{
		ID: "abc", Owner: "alice", Title: "hello",
		CurrentContent: "body", CreatedAt: ptr(now), UpdatedAt: ptr(now),
	}
	if d.GetID() != "abc" || d.GetOwner() != "alice" || d.GetTitle() != "hello" {
		t.Errorf("Document adapter getters returned wrong values: %+v", d)
	}
	if d.GetContent() != "body" {
		t.Errorf("Document.GetContent = %q, want %q", d.GetContent(), "body")
	}
	if d.GetCreatedAt() == nil || !d.GetCreatedAt().Equal(now) {
		t.Errorf("Document.GetCreatedAt = %v, want %v", d.GetCreatedAt(), now)
	}
	if d.GetUpdatedAt() == nil || !d.GetUpdatedAt().Equal(now) {
		t.Errorf("Document.GetUpdatedAt = %v, want %v", d.GetUpdatedAt(), now)
	}
}

func TestFormatSummary(t *testing.T) {
	got := formatSummary(7, 20, []string{"a", "b"}, 13)
	want := "Removed 7 of 20: a; b (+5 more) · 13 kept"
	if got != want {
		t.Errorf("formatSummary = %q, want %q", got, want)
	}
	// With all examples listed, no "+N more".
	got2 := formatSummary(2, 2, []string{"a", "b"}, 0)
	if got2 != "Removed 2 of 2: a; b · 0 kept" {
		t.Errorf("formatSummary no-extra = %q", got2)
	}
}

func TestDocumentImplementsView(t *testing.T) {
	var _ DocumentView = (*Document)(nil)
	var _ DocumentView = (*fakeDoc)(nil)
	// reflect check ensures methods are exported-shaped.
	dvType := reflect.TypeOf((*DocumentView)(nil)).Elem()
	for _, ty := range []reflect.Type{reflect.TypeOf((*Document)(nil)), reflect.TypeOf((*fakeDoc)(nil))} {
		if !ty.Implements(dvType) {
			t.Errorf("%s does not implement DocumentView", ty)
		}
	}
}

func contains(haystack []string, needle string) bool {
	for _, h := range haystack {
		if h == needle {
			return true
		}
	}
	return false
}
