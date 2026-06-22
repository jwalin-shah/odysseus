package assistantlog

import (
	"bytes"
	"context"
	"log/slog"
	"strings"
	"sync"
	"testing"
)

// captureLogger returns a slog.Logger that writes JSON records to buf.
// The returned restore func resets the package's session manager and is
// wired up by callers that mutate global state.
func captureLogger(buf *bytes.Buffer) *slog.Logger {
	h := slog.NewJSONHandler(buf, &slog.HandlerOptions{Level: slog.LevelDebug})
	return slog.New(h)
}

// resetSessionManagerForTest puts the package's global SessionManager
// back to its noop default so a test that swaps it does not leak state
// into the next test.
func resetSessionManagerForTest(t *testing.T) {
	t.Helper()
	t.Cleanup(func() { SetSessionManager(nil) })
}

// TestParseLegacyTag is the table-driven coverage for the regex port.
// The Python source uses r"^\s*\*\*\[([^\]]{1,40})\]\*\*\s*"; the Go
// port must agree on every case below.
func TestParseLegacyTag(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		wantCat  string
		wantRest string
		wantOK   bool
	}{
		{
			name:     "plain download tag",
			input:    "**[Download]** Started downloading foo.zip",
			wantCat:  "Download",
			wantRest: "Started downloading foo.zip",
			wantOK:   true,
		},
		{
			name:     "leading whitespace",
			input:    "   **[Search]** query result",
			wantCat:  "Search",
			wantRest: "query result",
			wantOK:   true,
		},
		{
			name:     "trailing whitespace after tag",
			input:    "**[Ingest]**   something happened",
			wantCat:  "Ingest",
			wantRest: "something happened",
			wantOK:   true,
		},
		{
			name:     "category with spaces",
			input:    "**[My Category]** body",
			wantCat:  "My Category",
			wantRest: "body",
			wantOK:   true,
		},
		{
			name:     "category at max length (40)",
			input:    "**[" + strings.Repeat("a", 40) + "]** body",
			wantCat:  strings.Repeat("a", 40),
			wantRest: "body",
			wantOK:   true,
		},
		{
			name:     "no tag",
			input:    "Just a regular message",
			wantCat:  "",
			wantRest: "Just a regular message",
			wantOK:   false,
		},
		{
			name:     "empty string",
			input:    "",
			wantCat:  "",
			wantRest: "",
			wantOK:   false,
		},
		{
			name:     "tag too long (>40) is rejected",
			input:    "**[" + strings.Repeat("a", 41) + "]** body",
			wantCat:  "",
			wantRest: "**[" + strings.Repeat("a", 41) + "]** body",
			wantOK:   false,
		},
		{
			name:     "missing closing bracket",
			input:    "**[Download started",
			wantCat:  "",
			wantRest: "**[Download started",
			wantOK:   false,
		},
		{
			name:     "missing asterisks",
			input:    "[Download] Started downloading",
			wantCat:  "",
			wantRest: "[Download] Started downloading",
			wantOK:   false,
		},
		{
			name:     "single asterisk is not enough",
			input:    "*[Download]** body",
			wantCat:  "",
			wantRest: "*[Download]** body",
			wantOK:   false,
		},
		{
			name:     "tag with embedded close-bracket is rejected",
			input:    "**[abc]def]** body",
			wantCat:  "",
			wantRest: "**[abc]def]** body",
			wantOK:   false,
		},
	}

	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			gotCat, gotRest, gotOK := ParseLegacyTag(tc.input)
			if gotCat != tc.wantCat {
				t.Errorf("category: got %q, want %q", gotCat, tc.wantCat)
			}
			if gotRest != tc.wantRest {
				t.Errorf("rest: got %q, want %q", gotRest, tc.wantRest)
			}
			if gotOK != tc.wantOK {
				t.Errorf("ok: got %v, want %v", gotOK, tc.wantOK)
			}
		})
	}
}

// TestLogToAssistantNoOp confirms the shim never reports Logged=true
// and always returns ReasonLegacyNoOp, regardless of inputs.
func TestLogToAssistantNoOp(t *testing.T) {
	var buf bytes.Buffer
	lg := captureLogger(&buf)
	ctx := context.Background()

	cases := []struct {
		name string
		opts LogOptions
	}{
		{"empty", LogOptions{}},
		{"only owner", LogOptions{Owner: "alice"}},
		{"only content", LogOptions{Content: "hello"}},
		{"explicit category", LogOptions{Owner: "alice", Content: "hello", Category: "Manual"}},
		{"legacy tag category", LogOptions{Owner: "alice", Content: "**[Download]** file.zip"}},
		{"full options", LogOptions{Owner: "alice", Content: "**[Download]** file.zip", Role: "user", Category: "explicit"}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			buf.Reset()
			res := LogToAssistant(ctx, tc.opts, lg)
			if res.Logged {
				t.Errorf("expected Logged=false, got true")
			}
			if res.Reason != ReasonLegacyNoOp {
				t.Errorf("expected Reason=%q, got %q", ReasonLegacyNoOp, res.Reason)
			}
		})
	}
}

// TestLogToAssistantCategoryResolution confirms that the explicit
// Category field wins over the parsed legacy tag, and that the legacy
// tag wins when no explicit category is provided.
func TestLogToAssistantCategoryResolution(t *testing.T) {
	var buf bytes.Buffer
	lg := captureLogger(&buf)
	ctx := context.Background()

	cases := []struct {
		name string
		opts LogOptions
		want string
	}{
		{
			name: "explicit category wins",
			opts: LogOptions{Content: "**[Download]** file.zip", Category: "Manual"},
			want: "Manual",
		},
		{
			name: "legacy tag when no explicit category",
			opts: LogOptions{Content: "**[Download]** file.zip"},
			want: "Download",
		},
		{
			name: "empty when neither",
			opts: LogOptions{Content: "no tag here"},
			want: "",
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			buf.Reset()
			res := LogToAssistant(ctx, tc.opts, lg)
			if res.Category != tc.want {
				t.Errorf("Category: got %q, want %q", res.Category, tc.want)
			}
		})
	}
}

// TestLogToAssistantDebugLogEmitted asserts that the shim emits exactly
// one DEBUG-level log line per call, with the right key/value pairs.
// The Python source's logger.debug(...) carried category + owner; the
// Go port adds role for parity with LogOptions.
func TestLogToAssistantDebugLogEmitted(t *testing.T) {
	var buf bytes.Buffer
	lg := captureLogger(&buf)
	ctx := context.Background()

	res := LogToAssistant(ctx, LogOptions{
		Owner:    "alice",
		Content:  "**[Download]** file.zip",
		Role:     "user",
		Category: "explicit",
	}, lg)

	if res.Reason != ReasonLegacyNoOp {
		t.Fatalf("expected legacy no-op reason, got %q", res.Reason)
	}
	out := buf.String()
	if !strings.Contains(out, `"level":"DEBUG"`) {
		t.Errorf("expected DEBUG level, got %q", out)
	}
	if !strings.Contains(out, `"category":"explicit"`) {
		t.Errorf("expected category=explicit in log, got %q", out)
	}
	if !strings.Contains(out, `"owner":"alice"`) {
		t.Errorf("expected owner=alice in log, got %q", out)
	}
	if !strings.Contains(out, `"role":"user"`) {
		t.Errorf("expected role=user in log, got %q", out)
	}
	if strings.Contains(out, "**[Download]**") {
		t.Errorf("content leaked into log line: %q", out)
	}
	if strings.Contains(out, "file.zip") {
		t.Errorf("content body leaked into log line: %q", out)
	}
}

// TestLogToAssistantDefaultRole confirms the empty Role defaults to
// DefaultRole ("assistant") and that the default is reflected in the
// emitted log line.
func TestLogToAssistantDefaultRole(t *testing.T) {
	var buf bytes.Buffer
	lg := captureLogger(&buf)
	ctx := context.Background()

	res := LogToAssistant(ctx, LogOptions{Owner: "bob", Content: "hi"}, lg)
	if res.Category != "" {
		t.Errorf("expected empty category, got %q", res.Category)
	}
	if !strings.Contains(buf.String(), `"role":"assistant"`) {
		t.Errorf("expected role=assistant default, got %q", buf.String())
	}
}

// TestLogToAssistantNilLogger confirms that passing a nil logger falls
// back to slog.Default() without panicking.
func TestLogToAssistantNilLogger(t *testing.T) {
	res := LogToAssistant(context.Background(), LogOptions{Owner: "alice", Content: "hi"}, nil)
	if res.Logged {
		t.Errorf("expected Logged=false")
	}
	if res.Reason != ReasonLegacyNoOp {
		t.Errorf("expected Reason=%q, got %q", ReasonLegacyNoOp, res.Reason)
	}
}

// recordingSessionManager captures every PostActivity call so tests can
// assert that LogToAssistant never invokes it (the shim is intentionally
// inert).
type recordingSessionManager struct {
	mu    sync.Mutex
	calls int
}

func (r *recordingSessionManager) PostActivity(ctx context.Context, owner, role, content string, category *string) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.calls++
	return nil
}

func (r *recordingSessionManager) Calls() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.calls
}

// TestSetSessionManagerIsNoOp confirms LogToAssistant never actually
// invokes the installed SessionManager. The Python module stored the
// reference but never called into it; the Go port mirrors that contract.
func TestSetSessionManagerIsNoOp(t *testing.T) {
	resetSessionManagerForTest(t)

	rec := &recordingSessionManager{}
	SetSessionManager(rec)

	var buf bytes.Buffer
	lg := captureLogger(&buf)

	for i := 0; i < 5; i++ {
		res := LogToAssistant(context.Background(), LogOptions{Owner: "alice", Content: "**[X]** msg"}, lg)
		if res.Logged {
			t.Errorf("expected Logged=false on iter %d", i)
		}
	}
	if got := rec.Calls(); got != 0 {
		t.Errorf("SessionManager.PostActivity should not be called; got %d calls", got)
	}
}

// TestSetSessionManagerNilResetsDefault confirms SetSessionManager(nil)
// restores the noop default. Tests that swap the manager must be able to
// reset it for subsequent tests.
func TestSetSessionManagerNilResetsDefault(t *testing.T) {
	resetSessionManagerForTest(t)

	called := false
	SetSessionManager(SessionManager(&flippySessionManager{onCall: func() { called = true }}))

	// Sanity: the recorder IS installed.
	if SessionManager_() == nil {
		t.Fatal("SessionManager_() returned nil after Set")
	}

	SetSessionManager(nil)
	if SessionManager_() == nil {
		t.Fatal("SessionManager_() returned nil after Set(nil)")
	}

	// The package's default noop returns nil without mutating state.
	_ = SessionManager_().PostActivity(context.Background(), "x", "y", "z", nil)
	if called {
		t.Errorf("expected noop default to not flip the test callback")
	}
}

// flippySessionManager is a tiny test double used to verify that the
// nil-reset path picks the noop default rather than the previously-set
// implementation.
type flippySessionManager struct {
	onCall func()
}

func (f flippySessionManager) PostActivity(ctx context.Context, owner, role, content string, category *string) error {
	if f.onCall != nil {
		f.onCall()
	}
	return nil
}
