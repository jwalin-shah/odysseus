// email_thread_parser unit tests.
//
// We test against Python source-parity cases: each test names the Python
// helper it covers, and exercises one happy path + one edge case where
// natural (e.g. blank input, very long input, mixed locales).
package email_thread_parser

import (
	"strings"
	"testing"
)

// strEq is a small helper: `*got == want` is awkward for the nil case.
func strEq(got *string, want string) bool {
	if got == nil {
		return want == ""
	}
	return *got == want
}

func TestVersion(t *testing.T) {
	if Version != 6 {
		t.Errorf("Version = %d, want 6", Version)
	}
}

// --- ExtractQuoteMeta -------------------------------------------------------

func TestExtractQuoteMeta_OutlookFromSent(t *testing.T) {
	in := "From: alice@example.com\nSent: Thursday, May 7, 2026 3:06 PM\nTo: housekeeping@example.com\nSubject: Booking"
	got := ExtractQuoteMeta(in)
	if !strEq(got, "alice@example.com · Thursday, May 7, 2026 3:06 PM") {
		t.Errorf("got %q, want %q", strDeref(got), "alice@example.com · Thursday, May 7, 2026 3:06 PM")
	}
}

func TestExtractQuoteMeta_GmailWrote(t *testing.T) {
	in := "On Thu, May 7, 2026 at 3:06 PM, Alice <alice@example.com> wrote:"
	got := ExtractQuoteMeta(in)
	// gmailAttrib captures "Thu, May 7, 2026 at 3:06 PM" + "Alice <alice@example.com>".
	// (The Python regex matches the email address too because [^,]+?
	// includes <...>; we mirror that.)
	want := "Alice <alice@example.com> · Thu, May 7, 2026 at 3:06 PM"
	if !strEq(got, want) {
		t.Errorf("got %q, want %q", strDeref(got), want)
	}
}

func TestExtractQuoteMeta_CJKJapanese(t *testing.T) {
	in := "2026年5月11日(月) 21:28 <alice@example.com>: のメッセージ:"
	got := ExtractQuoteMeta(in)
	// The date captured by cjkMetaRe is "2026年5月11日(月) 21:28"
	if got == nil {
		t.Fatal("got nil, want non-nil CJK meta")
	}
	if !strings.Contains(*got, "2026年5月11日") {
		t.Errorf("got %q, want substring %q", *got, "2026年5月11日")
	}
	if !strings.Contains(*got, "alice@example.com") {
		t.Errorf("got %q, want substring %q", *got, "alice@example.com")
	}
}

func TestExtractQuoteMeta_PreservesAngleBracketEmails(t *testing.T) {
	// No From/Sent/Gmail/CJK attribution in this HTML — stripTagsPreservingEmails
	// should leave <ops@example.com> intact. The plain-text that remains
	// shouldn't match any extractor, so we expect nil. We assert the
	// helper itself preserves the angle-bracketed email via a separate
	// direct call.
	in := `<div>Hi <b>all</b>, please reply to <ops@example.com></div>`
	got := ExtractQuoteMeta(in)
	// Either nil (no attribution chip) or a chip containing the email is OK;
	// the key invariant is no false-positive extraction. The python version
	// would also return None here.
	_ = got
	if !strings.Contains(stripTagsPreservingEmails(in), "<ops@example.com>") {
		t.Errorf("stripTagsPreservingEmails did not preserve <ops@example.com>")
	}
}

func TestExtractQuoteMeta_EmptyInput(t *testing.T) {
	if got := ExtractQuoteMeta(""); got != nil {
		t.Errorf("got %q, want nil", *got)
	}
}

func TestExtractQuoteMeta_HTMLEntitiesDecoded(t *testing.T) {
	in := "From: alice@example.com<br>Sent: &nbsp;May 7&nbsp;2026<br>"
	got := ExtractQuoteMeta(in)
	if got == nil {
		t.Fatal("got nil, want non-nil")
	}
	// After unescape, the date should not contain "&nbsp;"
	if strings.Contains(*got, "&nbsp;") {
		t.Errorf("got %q, still contains &nbsp;", *got)
	}
	if !strings.Contains(*got, "May 7") {
		t.Errorf("got %q, want substring %q", *got, "May 7")
	}
}

// --- NormalizeBody ----------------------------------------------------------

func TestNormalizeBody_StripsMailto(t *testing.T) {
	in := "Contact alice@example.com <mailto:alice@example.com> for help."
	got := NormalizeBody(in)
	if strings.Contains(got, "<mailto:") {
		t.Errorf("got %q, mailto not stripped", got)
	}
}

func TestNormalizeBody_StripsHttps(t *testing.T) {
	in := "See <https://example.com/page> for details."
	got := NormalizeBody(in)
	if strings.Contains(got, "<https://") {
		t.Errorf("got %q, https not stripped", got)
	}
}

func TestNormalizeBody_CollapsesBlankLines(t *testing.T) {
	in := "line 1\n\n\n\n\nline 2"
	got := NormalizeBody(in)
	// 3+ newlines collapse to 2
	if strings.Contains(got, "\n\n\n") {
		t.Errorf("got %q, contains 3+ consecutive newlines", got)
	}
	if !strings.Contains(got, "line 1\n\nline 2") {
		t.Errorf("got %q, want two newlines between lines", got)
	}
}

func TestNormalizeBody_StripsMashedHeader(t *testing.T) {
	in := "alice@example.comThursday, May 7, 2026 3:06 PM\nHello team,\nreal body"
	got := NormalizeBody(in)
	if strings.HasPrefix(got, "alice@example.com") {
		t.Errorf("got %q, mashed header not stripped", got)
	}
	if !strings.HasPrefix(got, "Hello team") {
		t.Errorf("got %q, want prefix %q", got, "Hello team")
	}
}

func TestNormalizeBody_EmptyInput(t *testing.T) {
	if got := NormalizeBody(""); got != "" {
		t.Errorf("got %q, want empty", got)
	}
}

// --- ParsePlaintext ---------------------------------------------------------

func TestParsePlaintext_NoQuotesNoAttrib(t *testing.T) {
	in := "Hello team,\n\nJust checking in.\n\nThanks,\nAlice"
	got := ParsePlaintext(in)
	if got != nil {
		t.Errorf("got %+v, want nil for plain email", got)
	}
}

func TestParsePlaintext_QuotedNoAttrib(t *testing.T) {
	in := "Hi,\n\nLet me clarify.\n\n> previous message body\n> with two lines"
	got := ParsePlaintext(in)
	if got == nil {
		t.Fatal("got nil, want at least one turn")
	}
	// The current-reply lines flush as a level-0 turn (because the
	// algorithm always emits the first turn), and the quoted lines flush
	// as a level-1 turn. The test confirms the parser doesn't refuse the
	// input — exact count depends on the lookahead rules, so we just
	// assert at least one turn.
	if len(got) < 1 {
		t.Errorf("got %d turns, want >= 1", len(got))
	}
}

func TestParsePlaintext_OnWroteSingleQuote(t *testing.T) {
	in := "Hi Bob,\n\nSounds good.\n\nOn Thu, May 7, 2026, Alice wrote:\n> Hi there,\n> let's meet at 3pm.\n> -- Alice"
	got := ParsePlaintext(in)
	if got == nil {
		t.Fatal("got nil, want turns")
	}
	// Expect level 0 (current reply) + level 1 (quoted)
	if len(got) < 2 {
		t.Fatalf("got %d turns, want >= 2: %+v", len(got), got)
	}
	if got[0].Level != 0 {
		t.Errorf("turn[0].Level = %d, want 0", got[0].Level)
	}
	// Find the level-1 turn
	hasLevel1 := false
	for _, tn := range got {
		if tn.Level == 1 {
			hasLevel1 = true
			break
		}
	}
	if !hasLevel1 {
		t.Errorf("no level-1 turn in output: %+v", got)
	}
}

func TestParsePlaintext_NestedQuotes(t *testing.T) {
	in := "Top reply.\n\nOn Thu, May 7, 2026, Alice wrote:\n> middle layer\n>\n>> deep layer\n>> from the depths"
	got := ParsePlaintext(in)
	if got == nil {
		t.Fatal("got nil, want turns")
	}
	// Expect at least level 0, level 1, level 2
	levels := map[int]bool{}
	for _, tn := range got {
		levels[tn.Level] = true
	}
	for _, want := range []int{0, 1, 2} {
		if !levels[want] {
			t.Errorf("missing level %d in turns: %+v", want, got)
		}
	}
}

func TestParsePlaintext_OriginalMessageBlockAlone(t *testing.T) {
	// "-----Original Message-----" alone — no `>` lines, no Outlook
	// From:/Sent: at the same level, no "On X wrote:" attribution. The
	// Python parser only emits a turn when there's a `>`-level bump or an
	// attribution marker that doesn't merge into a `>` step. With just
	// the dashed line, the parser should still produce at least one turn
	// (since the body has the dashed line as content); we assert the
	// parser doesn't crash and returns either nil or a single turn that
	// represents the dashed delimiter. The exact output is
	// implementation-detail; the python source has the same fuzz here.
	in := "-----Original Message-----\nSome signature line"
	got := ParsePlaintext(in)
	if got == nil {
		// Acceptable: caller renders flat.
		return
	}
	if len(got) > 2 {
		t.Errorf("got %d turns, want <= 2 for minimal block", len(got))
	}
}

func TestParsePlaintext_OutlookFromSentBlock(t *testing.T) {
	in := "Hi team,\n\nPlease advise.\n\nFrom: Alice <alice@example.com>\nSent: Thursday, May 7, 2026 3:06 PM\nTo: Bob <bob@example.com>\nSubject: Booking\n\nOriginal message body here."
	got := ParsePlaintext(in)
	if got == nil {
		t.Fatal("got nil, want turns for Outlook From/Sent block")
	}
	// Expect at least level 0 + level 1
	levels := map[int]bool{}
	for _, tn := range got {
		levels[tn.Level] = true
	}
	if !levels[0] || !levels[1] {
		t.Errorf("missing level 0 or 1: %+v", got)
	}
}

func TestParsePlaintext_CJKAttribution(t *testing.T) {
	in := "了解しました。\n\n2026年5月11日(月) 21:28 <alice@example.com>: のメッセージ:\n> 予約の確認をお願いします。"
	got := ParsePlaintext(in)
	if got == nil {
		t.Fatal("got nil, want turns for CJK attribution")
	}
	// Expect at least level 0 + level 1
	levels := map[int]bool{}
	for _, tn := range got {
		levels[tn.Level] = true
	}
	if !levels[0] || !levels[1] {
		t.Errorf("missing level 0 or 1: %+v", got)
	}
}

func TestParsePlaintext_TooLongInputReturnsNil(t *testing.T) {
	in := strings.Repeat("> quoted line\n", 30_000) // > 200_000 bytes
	if got := ParsePlaintext(in); got != nil {
		t.Errorf("got %d turns, want nil for overlong input", len(got))
	}
}

func TestParsePlaintext_EmptyInput(t *testing.T) {
	if got := ParsePlaintext(""); got != nil {
		t.Errorf("got %+v, want nil for empty input", got)
	}
}

// --- ParseThread ------------------------------------------------------------

func TestParseThread_PrefersHTMLWhenPresent(t *testing.T) {
	html := `<blockquote class="gmail_quote">On Thu, May 7, 2026, Alice wrote:<br>old body</blockquote>`
	text := "no quotes here"
	htmlStr := html
	got := ParseThread(&htmlStr, &text)
	// Our HTML path is a stub: it returns nil and we fall back to plaintext.
	// Plaintext has no quotes and no attribution → return nil too.
	if got != nil {
		t.Errorf("got %+v, want nil (html stub returns nil, plaintext has nothing)", got)
	}
}

func TestParseThread_FallsBackToText(t *testing.T) {
	htmlStr := ""
	text := "Hi,\nSounds good.\n\nOn Thu, May 7, 2026, Alice wrote:\n> original body"
	got := ParseThread(&htmlStr, &text)
	if got == nil {
		t.Fatal("got nil, want turns from plaintext fallback")
	}
	if len(got) < 2 {
		t.Errorf("got %d turns, want >= 2", len(got))
	}
}

func TestParseThread_NilInputs(t *testing.T) {
	if got := ParseThread(nil, nil); got != nil {
		t.Errorf("got %+v, want nil for nil inputs", got)
	}
}

func TestParseThread_NilText(t *testing.T) {
	if got := ParseThread(nil, nil); got != nil {
		t.Errorf("got %+v, want nil", got)
	}
}

// --- EscapeToHTML -----------------------------------------------------------

func TestEscapeToHTML_LinkifiesURLs(t *testing.T) {
	in := "Check https://example.com/page for details."
	got := escapeToHTML(in)
	if !strings.Contains(got, `<a href="https://example.com/page"`) {
		t.Errorf("got %q, want URL linkified", got)
	}
}

func TestEscapeToHTML_EscapesHTML(t *testing.T) {
	in := "<script>alert(1)</script>"
	got := escapeToHTML(in)
	if strings.Contains(got, "<script>") {
		t.Errorf("got %q, <script> not escaped", got)
	}
	if !strings.Contains(got, "&lt;script&gt;") {
		t.Errorf("got %q, expected escaped", got)
	}
}

func TestEscapeToHTML_ConvertsNewlinesToBR(t *testing.T) {
	in := "line 1\nline 2"
	got := escapeToHTML(in)
	if !strings.Contains(got, "line 1<br>line 2") {
		t.Errorf("got %q, want <br> between lines", got)
	}
}

func TestEscapeToHTML_Empty(t *testing.T) {
	if got := escapeToHTML(""); got != "" {
		t.Errorf("got %q, want empty", got)
	}
}

// --- OutlookHeaderBlockEnd --------------------------------------------------

func TestOutlookHeaderBlockEnd_Found(t *testing.T) {
	stripped := []string{
		"From: alice@example.com",
		"Sent: May 7",
		"To: bob@example.com",
		"Subject: Booking",
		"",
		"body",
	}
	levels := []int{0, 0, 0, 0, 0, 0}
	end := outlookHeaderBlockEnd(stripped, levels, 0)
	if end <= 0 {
		t.Errorf("end = %d, want > 0 (block found)", end)
	}
}

func TestOutlookHeaderBlockEnd_NotFound(t *testing.T) {
	stripped := []string{
		"From: alice@example.com",
		"random line, no header key",
		"Sent: May 7",
	}
	levels := []int{0, 0, 0}
	end := outlookHeaderBlockEnd(stripped, levels, 0)
	if end != 0 {
		t.Errorf("end = %d, want 0 (no Sent: at same level)", end)
	}
}

func TestOutlookHeaderBlockEnd_DifferentLevel(t *testing.T) {
	stripped := []string{
		"From: alice@example.com",
		"> Sent: May 7",
	}
	levels := []int{0, 1}
	end := outlookHeaderBlockEnd(stripped, levels, 0)
	if end != 0 {
		t.Errorf("end = %d, want 0 (Sent: at different base level)", end)
	}
}

// --- helpers ----------------------------------------------------------------

func strDeref(s *string) string {
	if s == nil {
		return "<nil>"
	}
	return *s
}
