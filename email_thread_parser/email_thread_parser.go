// Package email_thread_parser is the Go port of src/email_thread_parser.py.
//
// It walks an email body (HTML or plaintext) and returns a flat list of
// reply turns that a client can render directly without re-parsing:
//
//	[]Turn{
//	    {Level: 0, BodyHTML: "...", Meta: nil},
//	    {Level: 1, BodyHTML: "...", Meta: strPtr("Alice <a@x> · May 5")},
//	    ...
//	}
//
// where Level 0 is the current reply, increasing levels = deeper in the
// chain. The HTML path requires a real HTML parser; we intentionally
// stub it (ParseHTML returns nil) and let callers fall back to plaintext
// — keeping the Go build stdlib-only.
package email_thread_parser

import (
	html "html"
	"regexp"
	"strings"
)

// Version is the thread-parser shape version. Bump whenever the parser's
// output shape or splitting rules change. The cache layer wraps turns as
// {"v": Version, "turns": [...]} and treats anything with a different
// version as stale.
const Version = 6

// Turn is one conversation step in the parsed thread.
//
// Mirrors the Python {"level", "body_html", "meta"} dict. Level 0 is the
// current reply; higher levels are deeper in the quote chain. BodyHTML is
// HTML-safe (the plaintext path escapes + linkifies). Meta is the
// "sender · date" chip for that turn, or nil for the top turn.
type Turn struct {
	Level    int     `json:"level"`
	BodyHTML string  `json:"body_html"`
	Meta     *string `json:"meta,omitempty"`
}

// ── Locale tables (mirroring _TALON_* in static/js/emailLibrary.js) ──

// wroteLocale matches "wrote" in 20+ locales.
const wroteLocale = "(?:" +
	"wrote|écrit|escribió|scrisse|schrieb|skrev|schreef|napisał|написал|" +
	"napsal|написа|έγραψε|katselivat|napisao|написав|napisała|napisali|" +
	"hat geschrieben|kirjoitti|написала|escreveu" +
	")"

// fromLocale matches "From" in many locales.
const fromLocale = "(?:" +
	"From|Från|Von|De|Da|От|Od|Van|差出人|发件人|寄件人|Lähettäjä|" +
	"Avsender|Pošiljatelj|Frá" +
	")"

// sentLocale matches "Sent" in many locales.
const sentLocale = "(?:" +
	"Sent|Skickat|Gesendet|Envoy[ée]|Inviato|Enviado|Verzonden|Отправлено|" +
	"Wysłane|Date|送信日時|发送时间|寄件日期|Sendt|Lähetetty|Tarih|Datum|Data" +
	")"

// subjLocale matches "Subject" in many locales.
const subjLocale = "(?:" +
	"Subject|Ämne|Betreff|Objet|Oggetto|Asunto|Onderwerp|Тема|Temat|" +
	"件名|主题|主旨|Emne|Aihe|Konu" +
	")"

// toLocale matches "To" in many locales.
const toLocale = "(?:To|Till|An|À|A|Voor|Para|Naar|Кому|Do|宛先|收件人|Komu)"

// ccbccLocale matches "Cc" / "Bcc" in many locales.
const ccbccLocale = "(?:Cc|Bcc|Kopie|Skrytá kopie|Копия)"

// hdrKeysLocale is the union of header keys we recognise inside Outlook-style blocks.
const hdrKeysLocale = "(?:" + fromLocale + "|" + sentLocale + "|" + subjLocale + "|" +
	toLocale + "|" + ccbccLocale + "|Importance|Priority)"

// origRe matches a "----- Original Message -----" delimiter (or any of
// the locale variants). The Python version also uses re.IGNORECASE.
var origRe = regexp.MustCompile(
	`(?m)(?:^|\n)[\s>]*[-_=]{3,}\s*(?:Original\s+Message|Forwarded\s+message|` +
		`Ursprüngliche\s+Nachricht|` +
		`Mensaje\s+original|Messaggio\s+originale|Message\s+d['’]origine|` +
		`Oorspronkelijk\s+bericht|Original\s+meddelande|原文|原始邮件|転送)` +
		`\s*[-_=]{3,}`,
)

// wroteLineRe matches a "On ... wrote:" attribution line anchored to a
// single line. The Python uses re.IGNORECASE | re.MULTILINE; (?m) and (?i)
// get us the same behaviour here.
var wroteLineRe = regexp.MustCompile(`(?im)^\s*On\s.+?\s` + wroteLocale + `\s*:\s*$`)

// cjkAttribLineRe matches CJK-style attribution lines (Japanese Gmail /
// Yahoo Mail JP / etc.). See the package-level comments in the Python
// source for the supported shapes.
var cjkAttribLineRe = regexp.MustCompile(
	`(?m)^\s*(?:` +
		// date(weekday) time <email>:    (Gmail JP default)
		`\d{4}[年/.-]\d{1,2}[月/.-]\d{1,2}日?(?:\s*[\(\(].+?[\)\)])?` +
		`\s+\d{1,2}:\d{2}(?:\s*[ＡＰAP][ＭM])?` +
		`(?:に|、|,)?\s*(?:.+?\s+)?[<＜]?[\w.+\-]+@[\w.\-]+\.[A-Za-z]{2,}[>＞]?` +
		`\s*(?:のメッセージ|さんは(?:書|お?書き)きました|wrote)?\s*[:：]\s*$` +
		`|` +
		// 何々さんは 2026/05/11 21:28 に書きました:
		`.+?(?:さん|様)\s*(?:は|が)\s+\d{4}[年/.-]\d{1,2}[月/.-]\d{1,2}日?` +
		`(?:\s*[\(\(].+?[\)\)])?\s+\d{1,2}:\d{2}\s*(?:に)?\s*(?:書|お?書き)きました\s*[:：]\s*$` +
		`|` +
		// Chinese "XXX 写道:" preceded by a date or address
		`.+?\s*写道\s*[:：]\s*$` +
		`|` +
		// Korean "님이 작성:"
		`.+?\s*님이\s*작성(?:한\s*내용)?\s*[:：]\s*$` +
		`)`,
)

// outlookHeaderRe matches an Outlook From:/Sent: header block at the start
// of a quoted region.
var outlookHeaderRe = regexp.MustCompile(
	`(?i)` + fromLocale + `\s*:\s*[^\n]+\s*\n\s*(?:.+\n)?` + sentLocale + `\s*:\s*[^\n]+\s*\n`,
)

// fromStop is the set of header keys that terminate the From: capture.
// The Python version uses re.IGNORECASE.
const fromStop = `\s+(?:` + fromLocale + `|` + sentLocale + `|` + subjLocale + `|` +
	toLocale + `|` + ccbccLocale + `|Importance|Priority)\s*:`

// dateStop excludes Sent: so a single Sent: with comma-separated value
// doesn't get truncated at "Date" or other keys.
const dateStop = `\s+(?:` + fromLocale + `|` + subjLocale + `|` + toLocale + `|` +
	ccbccLocale + `|Importance|Priority)\s*:`

// quoteMetaFrom captures the From: value of an Outlook header. The Python
// uses a lookahead `(?:(?=FROM_STOP)|$)` so the next header key is not
// consumed by `.+?`. Go's RE2 lacks lookaheads, so we accept the stop
// markers as a normal alternation and trim them back out of the captured
// group via FindStringSubmatchIndex + manual substring slicing — see
// extractQuoteMetaFrom below.
var quoteMetaFrom = regexp.MustCompile(
	`(?is)` + fromLocale + `\s*:\s*(.+?)(?:` + fromStop + `|$)`,
)

// quoteMetaDate captures the Sent:/Date: value of an Outlook header.
// Same lookahead workaround as quoteMetaFrom.
var quoteMetaDate = regexp.MustCompile(
	`(?is)` + sentLocale + `\s*:\s*(.+?)(?:` + dateStop + `|$)`,
)

// gmailAttrib matches "On <date>, <name> wrote:" — the classic Gmail
// attribution line.
var gmailAttrib = regexp.MustCompile(
	`(?is)On\s+(.+),\s+([^,]+?)\s+` + wroteLocale + `\s*:`,
)

// ExtractQuoteMeta extracts a "sender · date" chip from a quoted block.
// HTML is unescaped; angle-bracketed email addresses (`<foo@bar.com>`) are
// preserved so the bubble renderer can align on the sender.
func ExtractQuoteMeta(textOrHTML string) *string {
	if textOrHTML == "" {
		return nil
	}
	plain := styleTagRe.ReplaceAllString(textOrHTML, " ")
	plain = stripTagsPreservingEmails(plain)
	plain = nbspRe.ReplaceAllString(plain, " ")
	plain = strings.NewReplacer("&amp;", "&", "&lt;", "<", "&gt;", ">", "&quot;", `""`).Replace(plain)
	plain = whitespaceCollapseRe.ReplaceAllString(plain, " ")
	if len(plain) > 1500 {
		plain = plain[:1500]
	}
	plain = strings.TrimSpace(plain)

	if f, fOK := matchMetaFrom(plain); fOK {
		if d, dOK := matchMetaDate(plain); dOK {
			s := strings.TrimSpace(f) + " · " + truncate(strings.TrimSpace(d), 80)
			return strPtr(s)
		}
	}
	if g := gmailAttrib.FindStringSubmatch(plain); g != nil {
		date := strings.TrimSpace(g[1])
		who := strings.TrimSpace(g[2])
		return strPtr(who + " · " + date)
	}
	// CJK attribution: "YYYY年MM月DD日(曜) HH:MM <email>:"
	if cjk := cjkMetaRe.FindStringSubmatch(plain); cjk != nil {
		date := strings.TrimSpace(cjk[1])
		who := strings.TrimSpace(firstNonEmpty(cjk[2], cjk[3]))
		if who == "" {
			return strPtr(date)
		}
		return strPtr(who + " · " + date)
	}
	if f, fOK := matchMetaFrom(plain); fOK {
		if f != "" {
			return strPtr(f)
		}
	}
	if d, dOK := matchMetaDate(plain); dOK {
		if d != "" {
			return strPtr(d)
		}
	}
	return nil
}

// styleTagRe strips <style>...</style> blocks (case-insensitive, dotall).
var styleTagRe = regexp.MustCompile(`(?is)<style[\s\S]*?</style>`)

// keepEmailAngleRe strips HTML tags but preserves angle-bracketed email
// addresses. The Python uses a negative lookahead `(?!...)` which Go's
// RE2 does not support. We replace it with a positive two-step approach:
// first match angle-bracketed emails (kept), then match any remaining
// tags (stripped). See stripTagsPreservingEmails below.
var angleEmailRe = regexp.MustCompile(`<[\w.+\-]+@[\w.\-]+\.[A-Za-z]{2,}>`)
var genericTagRe = regexp.MustCompile(`<[^>]+>`)

// nbspRe matches &nbsp; (case-insensitive). The Python uses
// `re.sub(r"&nbsp;", " ", ..., flags=re.IGNORECASE)`.
var nbspRe = regexp.MustCompile(`(?i)&nbsp;`)

// whitespaceCollapseRe collapses runs of whitespace to a single space.
var whitespaceCollapseRe = regexp.MustCompile(`\s+`)

// cjkMetaRe pulls "date + optional name + email" out of a CJK attribution.
var cjkMetaRe = regexp.MustCompile(
	`(\d{4}[年/.-]\d{1,2}[月/.-]\d{1,2}日?(?:\s*[\(\(][^\)\)]+?[\)\)])?\s+\d{1,2}:\d{2}(?:\s*[ＡＰAP][ＭM])?)` +
		`\s*(?:に|、|,)?\s*` +
		`(?:(.+?)\s+)?` +
		`[<＜]?([\w.+\-]+@[\w.\-]+\.[A-Za-z]{2,})[>＞]?`,
)

// ── Plaintext path ──

// mashedHdrRe matches Outlook's "mashed conversation header" at the very
// top of a reply — an email + weekday + date + optional To:/Subject: on
// a single line. Anchored to start of string; (?m) makes $ match line
// ends.
var mashedHdrRe = regexp.MustCompile(
	`(?im)^\s*[\w.+\-]+@[\w.\-]+\.[A-Za-z]{2,}` + // email
		`\s*` +
		`(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+` + // day name
		`\S+\s+\d+,?\s*\d{4}\s+\d{1,2}:\d{2}` + // date + time
		`(?:\s*[AP]M)?` + // optional AM/PM
		`(?:\s+` + toLocale + `\s*:\s*[^\n]+(?:\s+` + subjLocale + `\s*:\s*[^\n]*)?)?` +
		`\s*(?:\n|$)`,
)

// mailtoStripRe removes <mailto:...> decorations.
var mailtoStripRe = regexp.MustCompile(`(?i)<mailto:[^<>\s]*>`)

// httpsStripRe removes <https://...> decorations.
var httpsStripRe = regexp.MustCompile(`(?i)<https?://[^<>\s]*>`)

// trailWsRe trims trailing whitespace (incl. NBSP / form-feed / tab) so
// blank lines that mail clients fill with non-breaking spaces still
// count as blank for the collapse step.
var trailWsRe = regexp.MustCompile(`[^\S\n]+(\n|$)`)

// manyNewlinesRe collapses 3+ consecutive newlines into 2.
var manyNewlinesRe = regexp.MustCompile(`\n{3,}`)

// blankLinesLeadingRe strips leading blank lines after a mashed header strip.
var blankLinesLeadingRe = regexp.MustCompile(`^\s*\n+`)

// quotePrefixRe captures the leading `> ` prefix of a line.
var quotePrefixRe = regexp.MustCompile(`^((?:>\s?)+)`)

// quotePrefixStripRe strips the leading `> ` prefix.
var quotePrefixStripRe = regexp.MustCompile(`^(?:>\s?)+`)

// httpLinkRe linkifies URLs in plaintext → HTML output.
var httpLinkRe = regexp.MustCompile(`(https?://[^\s<>"]+)`)

// stripMashedHeader removes Outlook's "mashed conversation header" from
// the very top of a plaintext reply.
func stripMashedHeader(text string) string {
	if text == "" {
		return text
	}
	loc := mashedHdrRe.FindStringIndex(text)
	if loc == nil {
		return text
	}
	rest := text[loc[1]:]
	rest = blankLinesLeadingRe.ReplaceAllString(rest, "")
	return rest
}

// NormalizeBody strips noise that mail clients (mostly Outlook) inject
// into the plaintext body — duplicate `<mailto:>` link decorations,
// bracketed-URL annotations, repeated blank lines, and the mashed
// conversation-header at the top.
func NormalizeBody(text string) string {
	if text == "" {
		return text
	}
	text = stripMashedHeader(text)
	text = mailtoStripRe.ReplaceAllString(text, "")
	text = httpsStripRe.ReplaceAllString(text, "")
	text = trailWsRe.ReplaceAllString(text, `$1`)
	text = manyNewlinesRe.ReplaceAllString(text, "\n\n")
	return text
}

// outlookHeaderBlockEnd returns the exclusive end index of an Outlook
// From:/Sent: header block that starts at `start`, at the same `>`
// base level. Returns start if no block is recognised.
func outlookHeaderBlockEnd(stripped []string, levels []int, start int) int {
	if start >= len(stripped) {
		return start
	}
	base := levels[start]
	first := strings.TrimSpace(stripped[start])
	if !headerKeyRe(fromLocale).MatchString(first) {
		return start
	}
	foundSent := false
	j := start + 1
	for j < len(stripped) && j < start+6 && levels[j] == base {
		nl := strings.TrimSpace(stripped[j])
		if nl == "" {
			j++
			continue
		}
		if headerKeyRe(sentLocale).MatchString(nl) {
			foundSent = true
			break
		}
		if !headerKeyRe(hdrKeysLocale).MatchString(nl) {
			return start
		}
		j++
	}
	if !foundSent {
		return start
	}
	j = start + 1
	for j < len(stripped) && levels[j] == base {
		nl := strings.TrimSpace(stripped[j])
		if nl == "" {
			j++
			break
		}
		if headerKeyRe(hdrKeysLocale).MatchString(nl) {
			j++
			continue
		}
		break
	}
	return j
}

// headerKeyRe returns a fresh (?i) regex anchored to the start of the line
// for a given header-key locale table. We construct this on the fly
// because the locale constants contain alternations that vary at runtime.
func headerKeyRe(key string) *regexp.Regexp {
	return regexp.MustCompile(`(?i)^` + key + `\s*:`)
}

// ParsePlaintext walks `>` quote prefix levels + inline attribution
// markers at any level. Each attribution event AND each `>`-level
// increment counts as one conversation step, with one important
// exception: an attribution marker IMMEDIATELY followed by a deeper `>`
// block is the same event as that `>` increase (the classic Gmail
// "On X wrote:\n> quoted" pattern) and contributes only one step.
//
// Returns nil if no quoted material is detected.
func ParsePlaintext(text string) []Turn {
	if text == "" || len(text) > 200_000 {
		return nil
	}
	text = NormalizeBody(text)
	rawLines := strings.Split(text, "\n")

	baseLevels := make([]int, len(rawLines))
	strippedLines := make([]string, len(rawLines))
	for i, line := range rawLines {
		m := quotePrefixRe.FindStringIndex(line)
		if m == nil {
			baseLevels[i] = 0
			strippedLines[i] = line
			continue
		}
		baseLevels[i] = strings.Count(line[:m[1]], ">")
		strippedLines[i] = quotePrefixStripRe.ReplaceAllString(line, "")
	}

	hasQuotes := false
	for _, l := range baseLevels {
		if l > 0 {
			hasQuotes = true
			break
		}
	}
	hasAttrib := wroteLineRe.MatchString(text) ||
		origRe.MatchString(text) ||
		outlookHeaderRe.MatchString(text) ||
		cjkAttribLineRe.MatchString(text)
	if !hasQuotes && !hasAttrib {
		return nil
	}

	turns := make([]Turn, 0, 4)
	buf := make([]string, 0, 8)
	curLevel := 0
	var pendingMeta *string
	// depth_at_base[B] = the effective conversation depth recorded the
	// last time we were at `>` base level B.
	depthAtBase := map[int]int{0: 0}
	depth := 0
	prevBase := 0

	// flush mutates buf/pending_meta in the enclosing scope.
	flush := func() {
		if len(buf) == 0 {
			return
		}
		body := strings.TrimRight(strings.Join(buf, "\n"), "\n")
		if body != "" || curLevel > 0 {
			turns = append(turns, Turn{
				Level:    curLevel,
				BodyHTML: escapeToHTML(body),
				Meta:     pendingMeta,
			})
		}
		buf = buf[:0]
		pendingMeta = nil
	}

	// lookaheadContentBase returns the base level of the next non-blank
	// line at or after startIdx.
	lookaheadContentBase := func(startIdx int) *int {
		j := startIdx
		for j < len(rawLines) && strings.TrimSpace(strippedLines[j]) == "" {
			j++
		}
		if j >= len(rawLines) {
			return nil
		}
		v := baseLevels[j]
		return &v
	}

	i := 0
	for i < len(rawLines) {
		base := baseLevels[i]
		stripped := strippedLines[i]

		// `>` base level change → flush current turn, then step depth.
		if base > prevBase {
			flush()
			for b := prevBase + 1; b <= base; b++ {
				depth++
				depthAtBase[b] = depth
			}
			curLevel = depth
		} else if base < prevBase {
			flush()
			depth = depthAtBase[base]
			if depth == 0 && base != 0 {
				depth = base
			}
			for b := range depthAtBase {
				if b > base {
					delete(depthAtBase, b)
				}
			}
			curLevel = depth
		}
		prevBase = base

		isGmail := wroteLineRe.MatchString(stripped)
		isCJK := cjkAttribLineRe.MatchString(stripped)
		isOrig := origRe.MatchString("\n" + stripped)
		outlookEnd := outlookHeaderBlockEnd(strippedLines, baseLevels, i)
		isOutlook := outlookEnd > i

		if isGmail || isCJK || isOrig || isOutlook {
			attribEnd := i + 1
			if isOutlook {
				attribEnd = outlookEnd
			}
			metaText := strings.Join(strippedLines[i:attribEnd], "\n")

			// "-----Original Message-----" is almost always immediately
			// followed by an Outlook From:/Sent: header — fold that
			// into the SAME attribution event.
			if isOrig {
				j := attribEnd
				for j < len(rawLines) && baseLevels[j] == base && strings.TrimSpace(strippedLines[j]) == "" {
					j++
				}
				if j < len(rawLines) && baseLevels[j] == base {
					oe2 := outlookHeaderBlockEnd(strippedLines, baseLevels, j)
					if oe2 > j {
						metaText = metaText + "\n" + strings.Join(strippedLines[j:oe2], "\n")
						attribEnd = oe2
					}
				}
			}

			// If the next content line lives at a deeper > base, the
			// upcoming `>` increase will be the depth step — suppress
			// our own bump so we don't double up.
			nextBase := lookaheadContentBase(attribEnd)
			flush()
			if nextBase != nil && *nextBase > base {
				pendingMeta = ExtractQuoteMeta(metaText)
				if pendingMeta == nil {
					firstLine := strings.SplitN(strings.TrimSpace(metaText), "\n", 2)[0]
					pendingMeta = strPtr(firstLine)
				}
			} else {
				depth++
				depthAtBase[base] = depth
				curLevel = depth
				pendingMeta = ExtractQuoteMeta(metaText)
				if pendingMeta == nil {
					firstLine := strings.SplitN(strings.TrimSpace(metaText), "\n", 2)[0]
					pendingMeta = strPtr(firstLine)
				}
			}
			i = attribEnd
			continue
		}

		buf = append(buf, stripped)
		i++
	}
	flush()

	if len(turns) == 0 || (len(turns) == 1 && turns[0].Level == 0) {
		return nil
	}
	return turns
}

// escapeToHTML is a conservative plaintext → HTML converter: escape,
// then linkify URLs and convert newlines to <br>.
func escapeToHTML(text string) string {
	if text == "" {
		return ""
	}
	out := html.EscapeString(text)
	out = httpLinkRe.ReplaceAllStringFunc(out, func(m string) string {
		return `<a href="` + m + `" target="_blank" rel="noopener">` + m + `</a>`
	})
	return strings.ReplaceAll(out, "\n", "<br>")
}

// ── HTML path (stub) ──

// ParseHTML is intentionally a stub: the Python version uses BeautifulSoup
// to walk `<blockquote>` and the Gmail/Outlook/Yahoo/Apple Mail quote
// container classes. We don't have a stdlib HTML parser, so we let the
// caller fall back to ParsePlaintext. Document this so callers know to
// not rely on the HTML path until a proper parser is wired in.
func ParseHTML(htmlBody string) []Turn {
	_ = htmlBody
	return nil
}

// ParseThread is the public entry point. Prefers HTML when available,
// else plaintext. Returns nil if no quoted material is found.
func ParseThread(bodyHTML *string, bodyText *string) []Turn {
	if bodyHTML != nil && *bodyHTML != "" {
		if out := ParseHTML(*bodyHTML); out != nil {
			return out
		}
	}
	if bodyText != nil && *bodyText != "" {
		return ParsePlaintext(*bodyText)
	}
	return nil
}

// ── helpers ──

// stripTagsPreservingEmails mirrors the Python
// `re.sub(r"<(?![^@>\s]+@[^@>\s]+>)[^>]+>", " ", text)` — strip HTML
// tags, but preserve `<foo@bar.com>` patterns. Go's RE2 has no
// lookaheads, so we do it in two passes: split the input on angle-bracket
// email tokens, strip remaining tags from each piece, then rejoin.
func stripTagsPreservingEmails(s string) string {
	if !strings.ContainsAny(s, "<>") {
		return s
	}
	idxs := angleEmailRe.FindAllStringIndex(s, -1)
	if len(idxs) == 0 {
		return genericTagRe.ReplaceAllString(s, " ")
	}
	var b strings.Builder
	cursor := 0
	for _, idx := range idxs {
		if idx[0] > cursor {
			b.WriteString(genericTagRe.ReplaceAllString(s[cursor:idx[0]], " "))
		}
		b.WriteString(s[idx[0]:idx[1]])
		cursor = idx[1]
	}
	if cursor < len(s) {
		b.WriteString(genericTagRe.ReplaceAllString(s[cursor:], " "))
	}
	return b.String()
}

// matchMetaFrom returns the From: value (without trailing header-key stop
// markers) and true on a match. Go's RE2 lacks lookaheads, so we find the
// whole match including the stop marker, then chop the stop off the end.
func matchMetaFrom(plain string) (string, bool) {
	m := quoteMetaFrom.FindStringSubmatchIndex(plain)
	if m == nil {
		return "", false
	}
	// Indices: [start, end, group1Start, group1End]. The "stop" group
	// (group 2) only appears when the regex matched the stop alternation,
	// not the end-of-string $ anchor — so it's optional.
	valStart, valEnd := m[2], m[3]
	val := plain[valStart:valEnd]
	if len(m) >= 6 && m[4] != -1 && m[4] > valStart && m[4] < valEnd {
		valEnd = m[4]
		val = plain[valStart:valEnd]
	}
	return strings.TrimSpace(val), true
}

// matchMetaDate is the date counterpart of matchMetaFrom.
func matchMetaDate(plain string) (string, bool) {
	m := quoteMetaDate.FindStringSubmatchIndex(plain)
	if m == nil {
		return "", false
	}
	valStart, valEnd := m[2], m[3]
	val := plain[valStart:valEnd]
	if len(m) >= 6 && m[4] != -1 && m[4] > valStart && m[4] < valEnd {
		valEnd = m[4]
		val = plain[valStart:valEnd]
	}
	return strings.TrimSpace(val), true
}

func strPtr(s string) *string { return &s }

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}
