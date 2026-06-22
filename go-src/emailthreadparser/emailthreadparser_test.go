package emailthreadparser

import (
	"strings"
	"testing"
)

// TestThreadParserVersion pins the version constant. The cache layer
// treats any change as a stale-cache signal.
func TestThreadParserVersion(t *testing.T) {
	if ThreadParserVersion != 6 {
		t.Fatalf("ThreadParserVersion = %d, want 6", ThreadParserVersion)
	}
}

// TestParsePlaintextBasicGmailQuote covers the canonical Gmail "On X
// wrote:\n> quoted" attribution pattern.
func TestParsePlaintextBasicGmailQuote(t *testing.T) {
	body := "hi there\n\nOn Tue, Alice wrote:\n> older message\n> line two\n"
	turns := parsePlaintext(body)
	if len(turns) < 2 {
		t.Fatalf("expected >= 2 turns, got %d: %#v", len(turns), turns)
	}
	if turns[0].Level != 0 {
		t.Errorf("first turn level = %d, want 0", turns[0].Level)
	}
	if !strings.Contains(turns[0].BodyHTML, "hi there") {
		t.Errorf("first turn body missing 'hi there': %q", turns[0].BodyHTML)
	}
	if turns[1].Level <= 0 {
		t.Errorf("second turn level = %d, want > 0", turns[1].Level)
	}
	if turns[1].Meta == "" {
		t.Errorf("second turn meta should not be empty: %#v", turns[1])
	}
}

// TestParsePlaintextOriginalMessageDelimiter covers the
// "----- Original Message -----" delimiter with Outlook header block.
func TestParsePlaintextOriginalMessageDelimiter(t *testing.T) {
	body := "hello\n\n-----Original Message-----\nFrom: Bob <bob@x>\nSent: Mon, Jan 1 2024\nSubject: hi\n\nolder\n"
	turns := parsePlaintext(body)
	if len(turns) < 2 {
		t.Fatalf("expected >= 2 turns, got %d", len(turns))
	}
	if turns[0].Level != 0 {
		t.Errorf("first turn level = %d, want 0", turns[0].Level)
	}
	foundMeta := false
	for _, tn := range turns {
		if strings.Contains(tn.Meta, "Bob") {
			foundMeta = true
		}
	}
	if !foundMeta {
		t.Errorf("expected meta to mention Bob, got %#v", turns)
	}
}

// TestParsePlaintextCJKAttributionLine covers Japanese
// "YYYY年MM月DD日 HH:MM <email>:" attribution lines.
func TestParsePlaintextCJKAttributionLine(t *testing.T) {
	body := "新しい返信\n\n2026年5月11日(月) 21:28 <alice@example.com>:\n> 古いメッセージ\n"
	turns := parsePlaintext(body)
	if len(turns) < 2 {
		t.Fatalf("expected >= 2 turns, got %d", len(turns))
	}
	found := false
	for _, tn := range turns {
		if strings.Contains(tn.Meta, "alice@example.com") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected meta to contain alice@example.com, got %#v", turns)
	}
}

// TestParsePlaintextNoQuotesReturnsNil verifies that bodies without any
// quoted material return nil so callers render flat.
func TestParsePlaintextNoQuotesReturnsNil(t *testing.T) {
	if got := parsePlaintext("just a regular message, no quoting here"); got != nil {
		t.Errorf("expected nil for unquoted body, got %#v", got)
	}
}

// TestParsePlaintextEmptyInput covers the empty-string fast path.
func TestParsePlaintextEmptyInput(t *testing.T) {
	if got := parsePlaintext(""); got != nil {
		t.Errorf("expected nil for empty input, got %#v", got)
	}
}

// TestParsePlaintextStripsMashedOutlookHeader ensures Outlook's mashed
// conversation-header at the top of a reply is stripped before parsing.
func TestParsePlaintextStripsMashedOutlookHeader(t *testing.T) {
	body := "alice@example.comThursday, May 7, 2026 3:06 PM\n\nmy reply\n\nOn Tue, Alice wrote:\n> older\n"
	turns := parsePlaintext(body)
	if len(turns) < 2 {
		t.Fatalf("expected >= 2 turns, got %d", len(turns))
	}
	for _, tn := range turns {
		if strings.Contains(tn.BodyHTML, "alice@example.comThursday") {
			t.Errorf("mashed header should have been stripped, got: %q", tn.BodyHTML)
		}
	}
}

// TestParsePlaintextStripsMailtoDecoration ensures Outlook's
// "<mailto:foo>" decorations are dropped from body HTML.
func TestParsePlaintextStripsMailtoDecoration(t *testing.T) {
	body := "see <mailto:alice@x.com> here\n\nOn Tue, Alice wrote:\n> older\n"
	turns := parsePlaintext(body)
	for _, tn := range turns {
		if strings.Contains(tn.BodyHTML, "mailto:") {
			t.Errorf("mailto decoration should have been stripped, got: %q", tn.BodyHTML)
		}
	}
}

// TestParsePlaintextExtractsSenderMeta verifies the meta chip includes
// the sender's name + date for "On <date>, <name> wrote:" lines.
func TestParsePlaintextExtractsSenderMeta(t *testing.T) {
	body := "hi\n\nOn Tue, May 7, 2026, Alice Smith wrote:\n> older\n"
	turns := parsePlaintext(body)
	if len(turns) < 2 {
		t.Fatalf("expected >= 2 turns, got %d", len(turns))
	}
	found := false
	for _, tn := range turns {
		if strings.Contains(tn.Meta, "Alice Smith") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected meta to mention Alice Smith, got %#v", turns)
	}
}

// TestExtractQuoteMetaFromOutlookHeader directly exercises the Outlook
// From/Sent extraction path used by the meta chip builder.
func TestExtractQuoteMetaFromOutlookHeader(t *testing.T) {
	in := "<div>From: Bob Builder</div><div>Sent: Mon, Jan 1 2024</div><div>Subject: x</div>"
	meta := ExtractQuoteMeta(in)
	if !strings.Contains(meta, "Bob Builder") || !strings.Contains(meta, "Mon") {
		t.Errorf("meta missing sender/date: %q", meta)
	}
	if !strings.Contains(meta, "·") {
		t.Errorf("expected '·' separator, got %q", meta)
	}
}

// TestExtractQuoteMetaGmailFormat covers the On <date>, <name> wrote:
// fallback used when Outlook headers are absent.
func TestExtractQuoteMetaGmailFormat(t *testing.T) {
	in := "On Tue, May 7, Alice Smith wrote:"
	meta := ExtractQuoteMeta(in)
	if !strings.Contains(meta, "Alice Smith") {
		t.Errorf("meta missing Alice: %q", meta)
	}
	if !strings.Contains(meta, "May") {
		t.Errorf("meta missing date: %q", meta)
	}
}

// TestExtractQuoteMetaCJKFormat covers the Japanese attribution
// extraction. The meta chip should contain the date and either the
// display name or the email address.
func TestExtractQuoteMetaCJKFormat(t *testing.T) {
	in := "2026年5月11日(月) 21:28 Alice <alice@example.com> のメッセージ:"
	meta := ExtractQuoteMeta(in)
	if !strings.Contains(meta, "Alice") && !strings.Contains(meta, "alice@example.com") {
		t.Errorf("meta missing display name or email: %q", meta)
	}
	if !strings.Contains(meta, "2026年5月11日") {
		t.Errorf("meta missing date: %q", meta)
	}
}

// TestExtractQuoteMetaEmptyInput covers the empty-string fast path of
// the meta extractor.
func TestExtractQuoteMetaEmptyInput(t *testing.T) {
	if got := ExtractQuoteMeta(""); got != "" {
		t.Errorf("expected empty meta for empty input, got %q", got)
	}
}

// TestNormalizeBodyCollapsesBlankLines verifies that vertical-space soup
// (3+ consecutive newlines) is collapsed to a single blank line.
func TestNormalizeBodyCollapsesBlankLines(t *testing.T) {
	in := "a\n\n\n\n\n\nb"
	out := normalizeBody(in)
	if strings.Contains(out, "\n\n\n") {
		t.Errorf("expected newlines collapsed, got %q", out)
	}
	if !strings.Contains(out, "a\n\nb") {
		t.Errorf("expected a\\nb with single blank line between, got %q", out)
	}
}

// TestNormalizeBodyStripsURLDecorations verifies Outlook's `<https://...>`
// brackets are dropped.
func TestNormalizeBodyStripsURLDecorations(t *testing.T) {
	in := "visit <https://example.com> now"
	out := normalizeBody(in)
	if strings.Contains(out, "https://") {
		t.Errorf("expected URL decoration stripped, got %q", out)
	}
	if !strings.Contains(out, "visit") || !strings.Contains(out, "now") {
		t.Errorf("expected surrounding text preserved, got %q", out)
	}
}

// TestParseThreadIgnoresNonStringBodies mirrors the Python test
// test_parse_thread_ignores_non_string_bodies — non-string args must
// return nil.
func TestParseThreadIgnoresNonStringBodies(t *testing.T) {
	if got := ParseThread(123, map[string]bool{"bad": true}); got != nil {
		t.Errorf("expected nil for non-string bodies, got %#v", got)
	}
	if got := ParseThread([]string{"<blockquote>bad</blockquote>"}, nil); got != nil {
		t.Errorf("expected nil for non-string bodies, got %#v", got)
	}
}

// TestParseThreadStrings handles the typed-string convenience wrapper.
func TestParseThreadStrings(t *testing.T) {
	body := "hi\n\nOn Tue, Alice wrote:\n> older"
	turns := ParseThreadStrings("", body)
	if len(turns) == 0 {
		t.Fatalf("expected turns, got none")
	}
	if turns[0].Level != 0 {
		t.Errorf("first turn level = %d, want 0", turns[0].Level)
	}
}

// TestEscapeToHTMLLinkifiesURLs ensures URLs become anchor tags.
func TestEscapeToHTMLLinkifiesURLs(t *testing.T) {
	out := escapeToHTML("see https://example.com/path now")
	if !strings.Contains(out, `<a href="https://example.com/path"`) {
		t.Errorf("expected URL linkified, got %q", out)
	}
	if !strings.Contains(out, "target=\"_blank\"") {
		t.Errorf("expected target=_blank, got %q", out)
	}
}

// TestEscapeToHTMLEscapesHTMLChars ensures `<` and `>` are escaped to
// entities.
func TestEscapeToHTMLEscapesHTMLChars(t *testing.T) {
	out := escapeToHTML("if a < b then >")
	if strings.ContainsAny(out, "<>") {
		t.Errorf("expected < and > escaped, got %q", out)
	}
	if !strings.Contains(out, "&lt;") || !strings.Contains(out, "&gt;") {
		t.Errorf("expected &lt; and &gt; entities, got %q", out)
	}
}

// TestEscapeToHTMLEmptyInput covers the empty-string fast path.
func TestEscapeToHTMLEmptyInput(t *testing.T) {
	if got := escapeToHTML(""); got != "" {
		t.Errorf("expected empty output for empty input, got %q", got)
	}
}

// TestOutlookHeaderBlockEndFound covers the start of an Outlook header
// block returning the index past the header.
func TestOutlookHeaderBlockEndFound(t *testing.T) {
	stripped := []string{
		"From: Alice",
		"Sent: Mon, Jan 1 2024",
		"Subject: x",
		"To: bob@x",
		"",
		"body",
	}
	levels := []int{0, 0, 0, 0, 0, 0}
	end := outlookHeaderBlockEnd(stripped, levels, 0)
	if end <= 1 {
		t.Errorf("expected header block to be consumed, got end=%d", end)
	}
}

// TestOutlookHeaderBlockEndNotFound covers a line that is not a header
// key — must return start unchanged.
func TestOutlookHeaderBlockEndNotFound(t *testing.T) {
	stripped := []string{"just plain text"}
	levels := []int{0}
	if got := outlookHeaderBlockEnd(stripped, levels, 0); got != 0 {
		t.Errorf("expected 0 (no header block), got %d", got)
	}
}

// TestParsePlaintextNestedQuotes covers `> >` nested attribution
// counting as multiple conversation levels.
func TestParsePlaintextNestedQuotes(t *testing.T) {
	body := "top\n\nOn Tue, Alice wrote:\n> middle\n>\n>> deeper\n>\n> end\n"
	turns := parsePlaintext(body)
	if len(turns) < 2 {
		t.Fatalf("expected >= 2 turns, got %d", len(turns))
	}
	maxLevel := 0
	for _, tn := range turns {
		if tn.Level > maxLevel {
			maxLevel = tn.Level
		}
	}
	if maxLevel < 2 {
		t.Errorf("expected nested levels >= 2, got max %d", maxLevel)
	}
}

// TestParsePlaintextOutlookHeaderBlock exercises the
// outlookHeaderBlockEnd path with a full Outlook From/Sent/Subject/To
// header.
func TestParsePlaintextOutlookHeaderBlock(t *testing.T) {
	body := "my reply\n\nFrom: Alice <alice@x>\nSent: Mon, Jan 1, 2024\nTo: bob@x\nSubject: hi\n\nquoted body\n"
	turns := parsePlaintext(body)
	if len(turns) < 2 {
		t.Fatalf("expected >= 2 turns, got %d", len(turns))
	}
	found := false
	for _, tn := range turns {
		if strings.Contains(tn.Meta, "alice@x") || strings.Contains(tn.Meta, "Alice") {
			found = true
		}
	}
	if !found {
		t.Errorf("expected meta with Alice/email, got %#v", turns)
	}
}
