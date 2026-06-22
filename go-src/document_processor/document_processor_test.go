package document_processor

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// IsTextFile
// ---------------------------------------------------------------------------

func TestIsTextFile(t *testing.T) {
	cases := []struct {
		path string
		want bool
	}{
		{"/tmp/hello.txt", true},
		{"/tmp/script.py", true},
		{"/tmp/page.html", true},
		{"/tmp/notes.MD", true}, // case-insensitive
		{"/tmp/data.json", true},
		{"/tmp/data.CSV", true},
		{"/tmp/dump.log", true},
		{"/tmp/app.js", true},
		{"/tmp/config.nix", true},
		{"/tmp/image.png", false},
		{"/tmp/archive.zip", false},
		{"", false},
		{"/tmp/markdown.txtx", false}, // .txtx is not in the list
	}
	for _, tc := range cases {
		t.Run(tc.path, func(t *testing.T) {
			if got := IsTextFile(tc.path); got != tc.want {
				t.Errorf("IsTextFile(%q) = %v, want %v", tc.path, got, tc.want)
			}
		})
	}
}

func TestLanguageForExt(t *testing.T) {
	cases := []struct {
		ext  string
		want string
	}{
		{".py", "python"},
		{".go", "go"},
		{".tsx", "typescript"},
		{".jsx", "javascript"},
		{".unknown", "text"},
		{"", "text"},
		{".MD", "markdown"}, // case-insensitive
	}
	for _, tc := range cases {
		t.Run(tc.ext, func(t *testing.T) {
			if got := LanguageForExt(tc.ext); got != tc.want {
				t.Errorf("LanguageForExt(%q) = %q, want %q", tc.ext, got, tc.want)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// formatInt — the Python f"{n:,}" equivalent.
// ---------------------------------------------------------------------------

func TestFormatInt(t *testing.T) {
	cases := []struct {
		in   int64
		want string
	}{
		{0, "0"},
		{1, "1"},
		{999, "999"},
		{1000, "1,000"},
		{12345, "12,345"},
		{1234567, "1,234,567"},
		{-1500, "-1,500"},
	}
	for _, tc := range cases {
		t.Run(tc.want, func(t *testing.T) {
			if got := formatInt(tc.in); got != tc.want {
				t.Errorf("formatInt(%d) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// TruncateInline
// ---------------------------------------------------------------------------

func TestTruncateInline(t *testing.T) {
	t.Run("empty input", func(t *testing.T) {
		body, marker := TruncateInline("", 100)
		if body != "" || marker != "" {
			t.Errorf("expected empty body/marker, got body=%q marker=%q", body, marker)
		}
	})
	t.Run("fits under limit", func(t *testing.T) {
		body, marker := TruncateInline("hello world", 100)
		if body != "hello world" || marker != "" {
			t.Errorf("unexpected: body=%q marker=%q", body, marker)
		}
	})
	t.Run("truncates at limit with marker", func(t *testing.T) {
		body, marker := TruncateInline(strings.Repeat("a", 25000), 100)
		if len(body) != 100 {
			t.Errorf("body len = %d, want 100", len(body))
		}
		if !strings.Contains(marker, "truncated for inline context") {
			t.Errorf("marker missing truncation phrase: %q", marker)
		}
	})
	t.Run("strips surrounding whitespace", func(t *testing.T) {
		body, _ := TruncateInline("   padded   ", 100)
		if body != "padded" {
			t.Errorf("body = %q, want %q", body, "padded")
		}
	})
	t.Run("default limit when zero or negative", func(t *testing.T) {
		body, marker := TruncateInline("a", 0)
		if body != "a" {
			t.Errorf("zero limit should not truncate, got %q", body)
		}
		if marker != "" {
			t.Errorf("zero limit marker = %q, want empty", marker)
		}
	})
}

// ---------------------------------------------------------------------------
// FitInlineAttachmentText
// ---------------------------------------------------------------------------

func TestFitInlineAttachmentText(t *testing.T) {
	t.Run("fits under budget", func(t *testing.T) {
		body, remaining := FitInlineAttachmentText("hello", "doc.txt", 1000)
		if body != "hello" {
			t.Errorf("body = %q, want %q", body, "hello")
		}
		if remaining != 995 {
			t.Errorf("remaining = %d, want 995", remaining)
		}
	})
	t.Run("exact fit", func(t *testing.T) {
		body, remaining := FitInlineAttachmentText("hello", "doc.txt", 5)
		if body != "hello" || remaining != 0 {
			t.Errorf("body=%q remaining=%d, want hello/0", body, remaining)
		}
	})
	t.Run("truncates with marker when above slice threshold", func(t *testing.T) {
		long := strings.Repeat("a", 5000)
		body, remaining := FitInlineAttachmentText(long, "big.txt", 1000)
		if !strings.HasPrefix(body, strings.Repeat("a", 1000)) {
			t.Errorf("body should start with the truncated slice; got %q", body[:50])
		}
		if !strings.Contains(body, "[Attachment content truncated: big.txt") {
			t.Errorf("missing truncation marker, got body tail: %q", body[len(body)-100:])
		}
		if !strings.Contains(body, "Only 1,000 characters") {
			t.Errorf("marker should mention the 1,000 character cap, got: %s", body)
		}
		if remaining != 0 {
			t.Errorf("remaining = %d, want 0", remaining)
		}
	})
	t.Run("falls back to omission notice when budget is too small", func(t *testing.T) {
		body, remaining := FitInlineAttachmentText(strings.Repeat("a", 2000), "doc.txt", 100)
		if !strings.Contains(body, "[Attachment omitted from inline context: doc.txt") {
			t.Errorf("expected omission notice, got: %q", body)
		}
		if !strings.Contains(body, fmt.Sprintf("The %d-character shared inline attachment budget", MaxInlineAttachmentChars)) {
			t.Errorf("omission notice should mention the %d-character budget", MaxInlineAttachmentChars)
		}
		if remaining != 0 {
			t.Errorf("remaining = %d, want 0", remaining)
		}
	})
	t.Run("uses basename only", func(t *testing.T) {
		body, _ := FitInlineAttachmentText(strings.Repeat("a", 2000), "/tmp/dir/cool.txt", 100)
		if !strings.Contains(body, "Attachment omitted from inline context: cool.txt") {
			t.Errorf("expected basename only in notice: %q", body)
		}
	})
}

// ---------------------------------------------------------------------------
// StripPDFContentMarker
// ---------------------------------------------------------------------------

func TestStripPDFContentMarker(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want string
	}{
		{
			name: "happy path",
			in:   PDFContentMarker + "\n\n[Page 1 text]:\nhello",
			want: "[Page 1 text]:\nhello",
		},
		{
			name: "no marker",
			in:   "no marker here",
			want: "no marker here",
		},
		{
			name: "empty input",
			in:   "",
			want: "",
		},
		{
			name: "nil-ish (whitespace only)",
			in:   "    ",
			want: "",
		},
		{
			// CRITICAL: a naive lstrip would have eaten the "To" prefix.
			// removeprefix must not.
			name: "no character-set loss on body that starts with marker chars",
			in:   PDFContentMarker + "To the board",
			want: "To the board",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := StripPDFContentMarker(tc.in); got != tc.want {
				t.Errorf("StripPDFContentMarker(%q) = %q, want %q", tc.in, got, tc.want)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// ProcessTextFile
// ---------------------------------------------------------------------------

func writeFile(t *testing.T, dir, name, body string) string {
	t.Helper()
	p := filepath.Join(dir, name)
	if err := os.WriteFile(p, []byte(body), 0o600); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	return p
}

func TestProcessTextFilePythonBody(t *testing.T) {
	dir := t.TempDir()
	body := strings.Repeat("line\n", 50)
	path := writeFile(t, dir, "hello.txt", body)

	got := ProcessTextFile(path, TextFileOptions{})
	if !strings.Contains(got, "=== File: hello.txt ===") {
		t.Errorf("missing header, got: %q", got)
	}
	if !strings.Contains(got, "[Type: text") {
		t.Errorf("missing language tag, got: %q", got)
	}
	if !strings.Contains(got, "Lines: 51") {
		t.Errorf("missing line count, got: %q", got)
	}
	if strings.Contains(got, "[Truncated]") {
		t.Errorf("file should not have been truncated")
	}
}

func TestProcessTextFilePythonCode(t *testing.T) {
	dir := t.TempDir()
	body := "def hello():\n    print('hi')\n"
	path := writeFile(t, dir, "script.py", body)

	got := ProcessTextFile(path, TextFileOptions{})
	if !strings.HasPrefix(got, "\n=== File: script.py ===") {
		t.Errorf("missing header, got: %q", got)
	}
	if !strings.Contains(got, "[Type: python") {
		t.Errorf("missing language tag, got: %q", got)
	}
	if !strings.Contains(got, "```python\n") {
		t.Errorf("expected fenced python code block, got: %q", got)
	}
	if !strings.Contains(got, "print('hi')") {
		t.Errorf("expected body content, got: %q", got)
	}
}

func TestProcessTextFileTruncatesLarge(t *testing.T) {
	dir := t.TempDir()
	// 60k chars of content with no newlines means the snap-to-newline
	// logic must fall back to a 100-char back-search, then hard-truncate
	// at MaxLen (30 000 by default).
	body := strings.Repeat("a", 60000)
	path := writeFile(t, dir, "huge.txt", body)

	got := ProcessTextFile(path, TextFileOptions{})
	if !strings.Contains(got, "[Truncated]") {
		t.Errorf("expected truncation marker, got: %q", got)
	}
	if len(got) > 35000 { // header (~100) + body (30000) + markers
		t.Errorf("result unexpectedly large: %d", len(got))
	}
}

func TestProcessTextFileLogShorterCap(t *testing.T) {
	dir := t.TempDir()
	body := strings.Repeat("a", 20000)
	path := writeFile(t, dir, "app.log", body)

	got := ProcessTextFile(path, TextFileOptions{})
	if !strings.Contains(got, "[Truncated]") {
		t.Errorf("expected truncation marker for .log file above 10 000 char cap, got: %q", got)
	}
}

func TestProcessTextFileReadFailureBanner(t *testing.T) {
	dir := t.TempDir()
	// Make the directory unwritable so the read fails. We rely on a
	// missing file (no fixture write) to keep this test simple and
	// cross-platform.
	path := filepath.Join(dir, "absent.txt")
	got := ProcessTextFile(path, TextFileOptions{})
	if got != "\n\n[Failed to read attached file]" {
		t.Errorf("got %q, want failure banner", got)
	}
}

func TestProcessTextFileSnapToNewlineForward(t *testing.T) {
	// Build content that overflows MaxLen and has a newline a few chars
	// past the cutoff so the forward snap fires.
	dir := t.TempDir()
	prefix := strings.Repeat("a", 100)
	overflow := strings.Repeat("b", 29900)
	mid := strings.Repeat("c", 50) // filler near the cap
	body := prefix + overflow + mid + strings.Repeat("d", 50)
	path := writeFile(t, dir, "snap.txt", body)

	got := ProcessTextFile(path, TextFileOptions{})
	if !strings.Contains(got, "[Truncated]") {
		t.Errorf("expected truncation marker, got: %q", got)
	}
	// The cap is 30 000 chars; the forward snap range is 100 chars. The
	// body length we get back should be within that window.
	if !strings.HasPrefix(got, "\n=== File: snap.txt ===") {
		t.Errorf("missing header, got: %q", got)
	}
}

func TestProcessTextFileReaderOverride(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "ignored.txt", "disk content")
	got := ProcessTextFile(path, TextFileOptions{
		Reader: func(_ string) (string, error) {
			return "in-memory body", nil
		},
		SizeLookup: func(_ string) (int64, error) { return 42, nil },
	})
	if !strings.Contains(got, "in-memory body") {
		t.Errorf("expected injected content, got: %q", got)
	}
	if !strings.Contains(got, "Size: 42 bytes") {
		t.Errorf("expected injected size 42, got: %q", got)
	}
}

// ---------------------------------------------------------------------------
// Image format / base64 helpers
// ---------------------------------------------------------------------------

func TestImageFormat(t *testing.T) {
	cases := map[string]string{
		"/tmp/a.jpg":  "jpeg",
		"/tmp/a.jpeg": "jpeg",
		"/tmp/a.png":  "png",
		"/tmp/a.gif":  "gif",
		"/tmp/a.webp": "webp",
		"/tmp/a.bmp":  "jpeg", // default
		"/tmp/noext":  "jpeg",
	}
	for in, want := range cases {
		t.Run(in, func(t *testing.T) {
			if got := imageFormat(in); got != want {
				t.Errorf("imageFormat(%q) = %q, want %q", in, got, want)
			}
		})
	}
}

func TestReadAndBase64(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "tiny.bin", "abc")
	got, err := readAndBase64(path)
	if err != nil {
		t.Fatalf("readAndBase64: %v", err)
	}
	want := "YWJj" // base64("abc")
	if got != want {
		t.Errorf("readAndBase64 = %q, want %q", got, want)
	}
}

func TestReadAndBase64MissingFile(t *testing.T) {
	if _, err := readAndBase64("/no/such/file"); err == nil {
		t.Error("expected error on missing file")
	}
}

// ---------------------------------------------------------------------------
// VL pipeline
// ---------------------------------------------------------------------------

// fakeVLCaller records the calls and returns a scripted response.
type fakeVLCaller struct {
	calls   []vlCall
	respond func(idx int) (string, error)
}

type vlCall struct {
	URL, Model string
	Headers    map[string]string
	Timeout    int
	HasImage   bool
}

func (f *fakeVLCaller) Call(url, model string, messages VLMessages, headers map[string]string, timeoutSeconds int) (string, error) {
	hasImage := false
	for _, m := range messages {
		if parts, ok := m["content"].([]ContentPart); ok {
			for _, p := range parts {
				if _, ok := p["image_url"]; ok {
					hasImage = true
				}
			}
		}
	}
	f.calls = append(f.calls, vlCall{URL: url, Model: model, Headers: headers, Timeout: timeoutSeconds, HasImage: hasImage})
	if f.respond != nil {
		return f.respond(len(f.calls) - 1)
	}
	return "description", nil
}

func TestAnalyzeImageWithVLHappyPath(t *testing.T) {
	dir := t.TempDir()
	img := writeFile(t, dir, "pic.png", "\x89PNG\r\n\x1a\nfake")

	caller := &fakeVLCaller{}
	cfg := VLConfig{
		Call: caller.Call,
		ResolveModel: func(configured, owner string) (VLEndpoint, error) {
			return VLEndpoint{URL: "https://x", Model: "gpt-4o", Headers: map[string]string{"Authorization": "Bearer test"}}, nil
		},
	}

	res := AnalyzeImageWithVLResult(img, "alice", cfg)
	if res.Text != "description" {
		t.Errorf("Text = %q, want %q", res.Text, "description")
	}
	if res.Model != "gpt-4o" {
		t.Errorf("Model = %q, want %q", res.Model, "gpt-4o")
	}
	if len(caller.calls) != 1 {
		t.Fatalf("expected 1 call, got %d", len(caller.calls))
	}
	if !caller.calls[0].HasImage {
		t.Error("VL message missing image_url part")
	}
	if caller.calls[0].Timeout != 120 {
		t.Errorf("Timeout = %d, want 120", caller.calls[0].Timeout)
	}
}

func TestAnalyzeImageWithVLFallbackChain(t *testing.T) {
	dir := t.TempDir()
	img := writeFile(t, dir, "pic.jpg", "fake")

	caller := &fakeVLCaller{
		respond: func(idx int) (string, error) {
			if idx == 0 {
				return "", errors.New("primary 503")
			}
			return "fallback description", nil
		},
	}
	cfg := VLConfig{
		Call: caller.Call,
		ResolveModel: func(configured, owner string) (VLEndpoint, error) {
			return VLEndpoint{URL: "https://x", Model: "primary"}, nil
		},
		Fallbacks: func(_ string) []VLEndpoint {
			return []VLEndpoint{
				{URL: "https://x2", Model: "gpt-4o-mini"},
				{URL: "https://x3", Model: "gemini-2.0-flash"},
			}
		},
	}

	res := AnalyzeImageWithVLResult(img, "alice", cfg)
	if res.Text != "fallback description" {
		t.Errorf("Text = %q, want %q", res.Text, "fallback description")
	}
	if res.Model != "gpt-4o-mini" {
		t.Errorf("Model = %q, want %q", res.Model, "gpt-4o-mini")
	}
	if len(caller.calls) != 2 {
		t.Fatalf("expected 2 calls (primary + 1 fallback), got %d", len(caller.calls))
	}
}

func TestAnalyzeImageWithVLAllCandidatesExhausted(t *testing.T) {
	dir := t.TempDir()
	img := writeFile(t, dir, "pic.gif", "fake")

	caller := &fakeVLCaller{
		respond: func(_ int) (string, error) {
			return "", errors.New("still down")
		},
	}
	cfg := VLConfig{
		Call: caller.Call,
		ResolveModel: func(_, _ string) (VLEndpoint, error) {
			return VLEndpoint{URL: "https://x", Model: "primary"}, nil
		},
		Fallbacks: func(_ string) []VLEndpoint {
			return []VLEndpoint{{URL: "https://x2", Model: "gpt-4o-mini"}}
		},
	}

	res := AnalyzeImageWithVLResult(img, "alice", cfg)
	if res.Text != "[VL model unavailable - image not analyzed]" {
		t.Errorf("Text = %q, want unavailable banner", res.Text)
	}
	if res.Model != "" {
		t.Errorf("Model = %q, want empty", res.Model)
	}
}

func TestAnalyzeImageWithVLNoResolver(t *testing.T) {
	dir := t.TempDir()
	img := writeFile(t, dir, "pic.webp", "fake")

	cfg := VLConfig{Call: (&fakeVLCaller{}).Call}
	res := AnalyzeImageWithVLResult(img, "", cfg)
	if !strings.Contains(res.Text, "No vision model configured") {
		t.Errorf("Text = %q, want no-configured banner", res.Text)
	}
}

func TestAnalyzeImageWithVLNoCaller(t *testing.T) {
	res := AnalyzeImageWithVLResult("/no/file", "", VLConfig{})
	if res.Text != "[VL model unavailable - image not analyzed]" {
		t.Errorf("Text = %q, want unavailable banner", res.Text)
	}
}

func TestAnalyzeImageWithVLMissingImage(t *testing.T) {
	cfg := VLConfig{
		Call: (&fakeVLCaller{}).Call,
		ResolveModel: func(_, _ string) (VLEndpoint, error) {
			return VLEndpoint{URL: "https://x", Model: "gpt-4o"}, nil
		},
	}
	res := AnalyzeImageWithVLResult("/no/such.png", "", cfg)
	if res.Text != "[VL model unavailable - image not analyzed]" {
		t.Errorf("Text = %q, want unavailable banner", res.Text)
	}
	if res.Model != "" {
		t.Errorf("Model = %q, want empty", res.Model)
	}
}

func TestAnalyzeImageWithVLResolverWalksCandidates(t *testing.T) {
	dir := t.TempDir()
	img := writeFile(t, dir, "pic.png", "fake")

	cfg := VLConfig{
		Call: (&fakeVLCaller{}).Call,
		ResolveModel: func(configured, _ string) (VLEndpoint, error) {
			// Simulate the Python behavior: every model the candidate
			// list throws at us fails until we hit "gpt-4o-mini".
			if configured == "gpt-4o-mini" {
				return VLEndpoint{URL: "https://x", Model: configured}, nil
			}
			return VLEndpoint{}, errors.New("not available")
		},
	}
	res := AnalyzeImageWithVLResult(img, "", cfg)
	if res.Model != "gpt-4o-mini" {
		t.Errorf("Model = %q, want %q (candidate walk)", res.Model, "gpt-4o-mini")
	}
}

func TestAnalyzeImageWithVLConvenienceWrapper(t *testing.T) {
	dir := t.TempDir()
	img := writeFile(t, dir, "pic.png", "fake")
	cfg := VLConfig{
		Call: (&fakeVLCaller{
			respond: func(_ int) (string, error) { return "wrap", nil },
		}).Call,
		ResolveModel: func(_, _ string) (VLEndpoint, error) {
			return VLEndpoint{URL: "https://x", Model: "gpt-4o"}, nil
		},
	}
	if got := AnalyzeImageWithVL(img, "alice", cfg); got != "wrap" {
		t.Errorf("AnalyzeImageWithVL = %q, want %q", got, "wrap")
	}
}

// ---------------------------------------------------------------------------
// BuildUserContent
// ---------------------------------------------------------------------------

// stubUploadHandler is a test double for the UploadHandler interface.
type stubUploadHandler struct {
	files       map[string]UploadInfo
	images      map[string]bool
	audios      map[string]bool
	documents   map[string]bool
	insideBase  bool
	resolveMiss bool
}

func (s *stubUploadHandler) ResolveUpload(id, _ string) (UploadInfo, bool) {
	if s.resolveMiss {
		return UploadInfo{}, false
	}
	info, ok := s.files[id]
	return info, ok
}

func (s *stubUploadHandler) IsImageFile(_, _ string) bool    { return false }
func (s *stubUploadHandler) IsAudioFile(_, _ string) bool    { return false }
func (s *stubUploadHandler) IsDocumentFile(_, _ string) bool { return false }
func (s *stubUploadHandler) InsideBaseDir(string) bool       { return s.insideBase }

func TestBuildUserContentNoAttachments(t *testing.T) {
	out := BuildUserContent(BuildUserContentInput{
		Text:          "hello",
		UploadHandler: &stubUploadHandler{insideBase: true},
	})
	if got, ok := out.(string); !ok || got != "hello" {
		t.Errorf("expected string %q, got %#v", "hello", out)
	}
}

func TestBuildUserContentUnknownAttachment(t *testing.T) {
	out := BuildUserContent(BuildUserContentInput{
		Text:          "hi",
		AttachmentIDs: []string{"missing"},
		UploadHandler: &stubUploadHandler{insideBase: true, resolveMiss: true},
	})
	if got, ok := out.(string); !ok || got != "hi" {
		t.Errorf("expected %q, got %#v", "hi", out)
	}
}

func TestBuildUserContentRejectsPathOutsideBase(t *testing.T) {
	dir := t.TempDir()
	path := writeFile(t, dir, "evil.txt", "x")
	out := BuildUserContent(BuildUserContentInput{
		Text:          "hi",
		AttachmentIDs: []string{"a"},
		UploadHandler: &stubUploadHandler{
			insideBase: false,
			files:      map[string]UploadInfo{"a": {Path: path}},
		},
	})
	if got, ok := out.(string); !ok || got != "hi" {
		t.Errorf("expected %q (no inlining), got %#v", "hi", out)
	}
}

func TestBuildUserContentRejectsMissingPath(t *testing.T) {
	out := BuildUserContent(BuildUserContentInput{
		Text:          "hi",
		AttachmentIDs: []string{"a"},
		UploadHandler: &stubUploadHandler{
			insideBase: true,
			files:      map[string]UploadInfo{"a": {Path: "/no/such/file"}},
		},
	})
	if got, ok := out.(string); !ok || got != "hi" {
		t.Errorf("expected %q (no inlining), got %#v", "hi", out)
	}
}

type imageHandler struct {
	stubUploadHandler
}

func (i *imageHandler) IsImageFile(string, string) bool { return true }
func (i *imageHandler) IsAudioFile(string, string) bool { return false }
func (i *imageHandler) IsDocumentFile(string, string) bool {
	return false
}

func TestBuildUserContentImageAttachment(t *testing.T) {
	dir := t.TempDir()
	img := writeFile(t, dir, "pic.png", "fake")
	h := &imageHandler{
		stubUploadHandler: stubUploadHandler{
			insideBase: true,
			files:      map[string]UploadInfo{"a": {Path: img, Name: "pic.png", Mime: "image/png"}},
		},
	}
	out := BuildUserContent(BuildUserContentInput{
		Text:          "see attached",
		AttachmentIDs: []string{"a"},
		UploadHandler: h,
	})
	parts, ok := out.([]ContentPart)
	if !ok {
		t.Fatalf("expected []ContentPart, got %T", out)
	}
	if len(parts) != 2 {
		t.Fatalf("expected 2 parts (text+image), got %d", len(parts))
	}
	imagePart, ok := parts[1]["image_url"].(map[string]any)
	if !ok {
		t.Fatalf("image_url not a map: %v", parts[1])
	}
	url, _ := imagePart["url"].(string)
	if !strings.HasPrefix(url, "data:image/png;base64,") {
		t.Errorf("unexpected data URL: %q", url[:50])
	}
}

type documentHandler struct {
	stubUploadHandler
}

func (d *documentHandler) IsImageFile(string, string) bool    { return false }
func (d *documentHandler) IsAudioFile(string, string) bool    { return false }
func (d *documentHandler) IsDocumentFile(string, string) bool { return true }

// scriptedDocHandler returns a configurable inline body so we can test
// budget enforcement.
type scriptedDocHandler struct {
	body string
}

func (s *scriptedDocHandler) HandleDocument(_, _, _, _, _ string, _ *[]AutoOpenedDoc) string {
	return s.body
}

func TestBuildUserContentDocumentBudgetTracking(t *testing.T) {
	dir := t.TempDir()
	doc1 := writeFile(t, dir, "a.txt", "x")
	doc2 := writeFile(t, dir, "b.txt", "y")
	h := &documentHandler{
		stubUploadHandler: stubUploadHandler{
			insideBase: true,
			files: map[string]UploadInfo{
				"a": {Path: doc1, Name: "a.txt", Mime: "text/plain"},
				"b": {Path: doc2, Name: "b.txt", Mime: "text/plain"},
			},
		},
	}

	doc := &scriptedDocHandler{body: strings.Repeat("D", MaxInlineAttachmentChars+5000)}

	out := BuildUserContent(BuildUserContentInput{
		Text:            "summary",
		AttachmentIDs:   []string{"a", "b"},
		UploadHandler:   h,
		DocumentHandler: doc,
	})

	got, ok := out.(string)
	if !ok {
		t.Fatalf("expected string output, got %T", out)
	}
	// First attachment fits, second should be truncated/omitted.
	if !strings.Contains(got, "summary") {
		t.Errorf("expected original text in body, got: %q", got)
	}
	if !strings.Contains(got, "D") {
		t.Errorf("expected first doc body, got: %q", got[:200])
	}
	if strings.Count(got, "D") != MaxInlineAttachmentChars {
		t.Errorf("expected exactly %d D chars (one doc fitting exactly), got %d", MaxInlineAttachmentChars, strings.Count(got, "D"))
	}
}

func TestBuildUserContentNonTextAttachment(t *testing.T) {
	dir := t.TempDir()
	binary := writeFile(t, dir, "thing.bin", "x")
	h := &stubUploadHandler{
		insideBase: true,
		files:      map[string]UploadInfo{"x": {Path: binary, Name: "thing.bin", Mime: "application/octet-stream"}},
	}
	out := BuildUserContent(BuildUserContentInput{
		Text:          "look",
		AttachmentIDs: []string{"x"},
		UploadHandler: h,
	})
	got, ok := out.(string)
	if !ok {
		t.Fatalf("expected string output, got %T", out)
	}
	if !strings.Contains(got, "[Attached non-text file]") {
		t.Errorf("expected non-text banner, got: %q", got)
	}
}

func TestBuildUserContentNoHandler(t *testing.T) {
	out := BuildUserContent(BuildUserContentInput{
		Text:          "hi",
		AttachmentIDs: []string{"x"},
	})
	if got, ok := out.(string); !ok || got != "hi" {
		t.Errorf("expected %q, got %#v", "hi", out)
	}
}

func TestBannerDocumentHandler(t *testing.T) {
	got := BannerDocumentHandler{}.HandleDocument("/tmp/x", "x", "application/pdf", "", "", nil)
	if got != "\n\n[Attached document file]" {
		t.Errorf("BannerDocumentHandler = %q, want default banner", got)
	}
}

// ---------------------------------------------------------------------------
// hasMedia + appendImagePart + appendAudioPart direct coverage
// ---------------------------------------------------------------------------

func TestHasMedia(t *testing.T) {
	if hasMedia([]ContentPart{{"type": "text", "text": "x"}}) {
		t.Error("text-only should not count as media")
	}
	if !hasMedia([]ContentPart{{"type": "image_url", "image_url": map[string]any{}}}) {
		t.Error("image_url should count as media")
	}
	if !hasMedia([]ContentPart{{"type": "audio", "audio": map[string]any{}}}) {
		t.Error("audio should count as media")
	}
}

func TestPrependOrAppendBanner(t *testing.T) {
	// First call: text part exists, banner is appended with "\n\n" separator.
	parts := []ContentPart{{"type": "text", "text": "hello"}}
	parts = prependOrAppendBanner(parts, "\n\nWORLD")
	if got, _ := parts[0]["text"].(string); got != "hello\n\nWORLD" {
		t.Errorf("got %q, want %q", got, "hello\n\nWORLD")
	}
	// Second call: banner with no leading newlines still gets "\n\n" prepended.
	parts = prependOrAppendBanner(parts, "LEAD")
	if got, _ := parts[0]["text"].(string); got != "hello\n\nWORLD\n\nLEAD" {
		t.Errorf("got %q, want %q", got, "hello\n\nWORLD\n\nLEAD")
	}

	// Non-text first part: banner becomes the new first part.
	parts2 := []ContentPart{{"type": "image_url", "image_url": map[string]any{}}}
	parts2 = prependOrAppendBanner(parts2, "BANNER")
	if len(parts2) != 2 {
		t.Fatalf("expected 2 parts, got %d", len(parts2))
	}
	if got, _ := parts2[0]["text"].(string); got != "BANNER" {
		t.Errorf("got %q, want %q", got, "BANNER")
	}
}

func TestAppendAudioPartMissingFile(t *testing.T) {
	parts := []ContentPart{{"type": "text", "text": "x"}}
	_, appended, ok := appendAudioPart(parts, UploadInfo{Path: "/no/such"}, ".mp3", "a")
	if ok || appended != "" {
		t.Errorf("expected failure, got appended=%q ok=%v", appended, ok)
	}
}

func TestAppendImagePartMissingFile(t *testing.T) {
	parts := []ContentPart{{"type": "text", "text": "x"}}
	_, appended, ok := appendImagePart(parts, UploadInfo{Path: "/no/such"}, ".png", "a")
	if ok || appended != "" {
		t.Errorf("expected failure, got appended=%q ok=%v", appended, ok)
	}
}

func TestResolveVLEndpointsNoResolver(t *testing.T) {
	_, err := resolveVLEndpoints(VLConfig{}, "alice")
	if !errors.Is(err, ErrNoVisionModel) {
		t.Errorf("expected ErrNoVisionModel, got %v", err)
	}
}

func TestResolveVLEndpointsWithFallbacks(t *testing.T) {
	cfg := VLConfig{
		ResolveModel: func(_, _ string) (VLEndpoint, error) {
			return VLEndpoint{URL: "u", Model: "m"}, nil
		},
		Fallbacks: func(_ string) []VLEndpoint {
			return []VLEndpoint{{URL: "u2", Model: "m2"}}
		},
	}
	eps, err := resolveVLEndpoints(cfg, "alice")
	if err != nil {
		t.Fatalf("resolveVLEndpoints: %v", err)
	}
	if len(eps) != 2 {
		t.Fatalf("expected 2 endpoints, got %d", len(eps))
	}
	if eps[0].Model != "m" || eps[1].Model != "m2" {
		t.Errorf("endpoint order wrong: %+v", eps)
	}
}

func TestErrNoVisionModelExposed(t *testing.T) {
	if ErrNoVisionModel == nil {
		t.Fatal("ErrNoVisionModel must be non-nil")
	}
}
