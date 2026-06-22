// Package emailthreadparser walks an email body (plain text or HTML) and
// returns a tree of reply turns that a client can render directly without
// re-parsing.
//
// It is the Go port of src/email_thread_parser.py. The Python
// implementation has two paths:
//
//   - HTML path: walks BeautifulSoup quote containers (<blockquote>,
//     gmail_quote, Apple Mail type=cite, Yahoo yahoo_quoted, Outlook
//     divRplyFwdMsg / OutlookMessageHeader, etc.) and recurses into
//     nested containers.
//   - Plaintext path: walks `>` quote prefix levels + inline attribution
//     markers (multilingual "On <date>, <name> wrote:", Outlook
//     "From:/Sent:/Subject:" header blocks, "----- Original Message -----"
//     delimiters, CJK attribution lines).
//
// The Go port preserves the plaintext path in full — it does not depend on
// any HTML parser library. The HTML path is intentionally stubbed: the
// public ParseThread entry point falls back to the plaintext parser when
// only an HTML body is supplied (returning nil when no quoted material is
// found, mirroring Python's behaviour when BeautifulSoup is not
// installed).
package emailthreadparser

import (
	"html"
	"regexp"
	"strings"
)

// ThreadParserVersion is the parser's output shape / splitting rules
// version. The cache layer wraps turns as
//
//	{"v": ThreadParserVersion, "turns": [...]}
//
// and treats anything with a different version as stale. It must be
// bumped whenever the output shape or splitting rules change.
const ThreadParserVersion = 6

// Turn is a single reply turn extracted from a thread body. Level 0 is
// the current reply; higher levels are deeper in the chain. Meta holds
// attribution metadata (e.g. "Alice <a@x> · May 5") when the parser
// could extract it, otherwise the empty string. JSON callers that need
// null should compare Meta == "".
type Turn struct {
	Level    int    `json:"level"`
	BodyHTML string `json:"body_html"`
	Meta     string `json:"meta"`
}

// ---------------------------------------------------------------------------
// Locale tables (mirror static/js/emailLibrary.js _TALON_*)
// ---------------------------------------------------------------------------

const (
	wrotePart = `(?:wrote|écrit|escribió|scrisse|schrieb|skrev|schreef|napisał|написал|` +
		`napsal|написа|έγραψε|katselivat|napisao|написав|napisała|napisali|` +
		`hat geschrieben|kirjoitti|написала|escreveu)`

	fromPart = `(?:From|Från|Von|De|Da|От|Od|Van|差出人|发件人|寄件人|Lähettäjä|` +
		`Avsender|Pošiljatelj|Frá)`

	sentPart = `(?:Sent|Skickat|Gesendet|Envoy[ée]|Inviato|Enviado|Verzonden|Отправлено|` +
		`Wysłane|Date|送信日時|发送时间|寄件日期|Sendt|Lähetetty|Tarih|Datum|Data)`

	subjPart = `(?:Subject|Ämne|Betreff|Objet|Oggetto|Asunto|Onderwerp|Тема|Temat|` +
		`件名|主题|主旨|Emne|Aihe|Konu)`

	toPart = `(?:To|Till|An|À|A|Voor|Para|Naar|Кому|Do|宛先|收件人|Komu)`

	ccBccPart = `(?:Cc|Bcc|Kopie|Skrytá kopie|Копия)`

	hdrKeys = `(?:` + fromPart + `|` + sentPart + `|` + subjPart + `|` + toPart +
		`|` + ccBccPart + `|Importance|Priority)`
)

// cjkWeekdayParens matches "(曜)" / "（曜）" style weekday parens regardless
// of which bracket flavour the sender used.
const cjkWeekdayParens = `(?:\s*[\(\(][^\)\)]+?[\)\)])?`

// origRe matches "----- Original Message -----" style delimiters in many
// locales. The leading newline is required so we don't false-positive on
// strings of dashes embedded mid-line.
var origRe = regexp.MustCompile(`(?i)(?:^|\n)[\s>]*[-_=]{3,}\s*(?:Original\s+Message|Forwarded\s+message|` +
	`Ursprüngliche\s+Nachricht|` +
	`Mensaje\s+original|Messaggio\s+originale|Message\s+d['’]origine|` +
	`Oorspronkelijk\s+bericht|Original\s+meddelande|原文|原始邮件|転送)` +
	`\s*[-_=]{3,}`)

// wroteLineRe matches a full attribution line ("On Tue, Alice wrote:"
// style) — anchored at the start of a line so we don't false-positive on
// prose containing "wrote".
var wroteLineRe = regexp.MustCompile(`(?im)^\s*On\s.+?\s` + wrotePart + `\s*:\s*$`)

// cjkAttribLineRe matches CJK-style attribution lines such as:
//
//	2026年5月11日(月) 21:28 <alice@example.com>:
//	2026年5月11日(月) 21:28に Alice Smith <alice@example.com> のメッセージ:
//	2026年5月11日 21:28、alice@example.com さんは書きました:
//	Alice さんは 2026/05/11 21:28 に書きました:
//	xxx 写道:
//	xxx님이 작성:
var cjkAttribLineRe = regexp.MustCompile(`(?m)^\s*(?:` +
	// date(weekday) time <email>: (Gmail JP default)
	`\d{4}[年/.-]\d{1,2}[月/.-]\d{1,2}日?` + cjkWeekdayParens +
	`\s+\d{1,2}:\d{2}(?:\s*[ＡＰAP][ＭM])?` +
	`(?:に|、|,)?\s*(?:.+?\s+)?[<＜]?[\w.+\-]+@[\w.\-]+\.[A-Za-z]{2,}[>＞]?` +
	`\s*(?:のメッセージ|さんは(?:書|お?書き)きました|wrote)?\s*[:：]\s*$` +
	`|` +
	// "xxx さんは 2026/05/11 21:28 に書きました:"
	`.+?(?:さん|様)\s*(?:は|が)\s+\d{4}[年/.-]\d{1,2}[月/.-]\d{1,2}日?` +
	cjkWeekdayParens + `\s+\d{1,2}:\d{2}\s*(?:に)?\s*(?:書|お?書き)きました\s*[:：]\s*$` +
	`|` +
	// Chinese "XXX 写道:" preceded by a date or address
	`.+?\s*写道\s*[:：]\s*$` +
	`|` +
	// Korean "님이 작성:"
	`.+?\s*님이\s*작성(?:한\s*내용)?\s*[:：]\s*$` +
	`)`)

// outlookHeaderRe matches an Outlook-style header block: "From: ..."
// followed by a "Sent: ..." line.
var outlookHeaderRe = regexp.MustCompile(`(?i)` + fromPart +
	`\s*:\s*[^\n]+\s*\n\s*(?:.+\n)?` + sentPart + `\s*:\s*[^\n]+\s*\n`)

// quoteMetaFromStopRe matches the next header key that should terminate
// the From: capture. Capturing as a non-anchored alternation lets the
// From: pattern scan forward; the lookahead that Go's regexp engine
// does not support is replaced by a non-capturing group match against
// the rest of the string.
const (
	quoteMetaFromStop = `(?:From|Från|Von|De|Da|От|Od|Van|差出人|发件人|寄件人|Lähettäjä|` +
		`Avsender|Pošiljatelj|Frá)|(?:Sent|Skickat|Gesendet|Envoy[ée]|Inviato|Enviado|` +
		`Verzonden|Отправлено|Wysłane|Date|送信日時|发送时间|寄件日期|Sendt|Lähetetty|` +
		`Tarih|Datum|Data)|(?:Subject|Ämne|Betreff|Objet|Oggetto|Asunto|Onderwerp|` +
		`Тема|Temat|件名|主题|主旨|Emne|Aihe|Konu)|(?:To|Till|An|À|A|Voor|Para|Naar|` +
		`Кому|Do|宛先|收件人|Komu)|(?:Cc|Bcc|Kopie|Skrytá kopie|Копия)|Importance|Priority`

	quoteMetaDateStop = `(?:From|Från|Von|De|Da|От|Od|Van|差出人|发件人|寄件人|Lähettäjä|` +
		`Avsender|Pošiljatelj|Frá)|(?:Subject|Ämne|Betreff|Objet|Oggetto|Asunto|` +
		`Onderwerp|Тема|Temat|件名|主题|主旨|Emne|Aihe|Konu)|(?:To|Till|An|À|A|Voor|` +
		`Para|Naar|Кому|Do|宛先|收件人|Komu)|(?:Cc|Bcc|Kopie|Skrytá kopie|Копия)|` +
		`Importance|Priority`
)

// extractHeaderValue extracts the value of a header line `Key: value`,
// stopping at the next header-key line. The plain text has already been
// whitespace-collapsed so we only need to look for the next "Word:"
// pattern. Returns "" if not found.
func extractHeaderValue(plain, keyRe string) string {
	// Find the start of the header (e.g. "From: ...").
	start := regexp.MustCompile(`(?i)(?:` + keyRe + `)\s*:\s*`).FindStringIndex(plain)
	if start == nil {
		return ""
	}
	rest := plain[start[1]:]
	// Walk until we hit the next header-key word followed by a colon.
	stopRe := regexp.MustCompile(`(?i)\s+(?:` + quoteMetaFromStop + `)\s*:`)
	stop := stopRe.FindStringIndex(rest)
	if stop == nil {
		return strings.TrimSpace(rest)
	}
	return strings.TrimSpace(rest[:stop[0]])
}

// gmailAttrib matches the "On <date>, <author> wrote:" attribution line.
// We greedily capture the date so multi-comma dates like "Thu, May 7,
// 2026, 11:33 AM," don't collapse to just the day, then let the comma +
// lazy author match back off to the LAST comma before "wrote:".
var gmailAttrib = regexp.MustCompile(`(?is)On\s+(.+),\s+([^,]+?)\s+` + wrotePart + `\s*:`)

// gmailLineRe matches a single "On <date>, <name> wrote:" attribution
// line for the line-by-line plaintext walker.
var gmailLineRe = regexp.MustCompile(`(?i)^\s*On\s.+?\s` + wrotePart + `\s*:\s*$`)

// styleTagRe strips <style>...</style> blocks before extracting plain
// text.
var styleTagRe = regexp.MustCompile(`<style[\s\S]*?</style>`)

// stripHTMLTagsExceptEmails removes HTML tags from s, but preserves
// <foo@bar> patterns so the sender's address survives to downstream
// consumers. Go's regexp engine does not support negative lookahead,
// so we hand-roll the scan: scan for `<...>` and either keep the match
// (if it's a <foo@bar>) or replace it with a space.
func stripHTMLTagsExceptEmails(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	i := 0
	for i < len(s) {
		if s[i] != '<' {
			b.WriteByte(s[i])
			i++
			continue
		}
		end := strings.IndexByte(s[i:], '>')
		if end < 0 {
			b.WriteByte(s[i])
			i++
			continue
		}
		tag := s[i : i+end+1]
		inner := tag[1 : len(tag)-1]
		if isEmailAngle(inner) {
			b.WriteString(tag)
		} else {
			b.WriteByte(' ')
		}
		i += end + 1
	}
	return b.String()
}

// isEmailAngle reports whether s looks like a "foo@bar" address (the
// contents of an angle-bracketed email).
func isEmailAngle(s string) bool {
	at := strings.IndexByte(s, '@')
	if at <= 0 || at == len(s)-1 {
		return false
	}
	// Must have something on either side of @, and no whitespace.
	for _, r := range s {
		if r == ' ' || r == '\t' || r == '\n' || r == '\r' || r == '>' || r == '<' {
			return false
		}
	}
	return true
}

// cjkMetaRe extracts a "YYYY年MM月DD日(曜) HH:MM <email>:" style chip from
// a quoted block, returning the date and optional display name + email.
var cjkMetaRe = regexp.MustCompile(`(\d{4}[年/.-]\d{1,2}[月/.-]\d{1,2}日?` + cjkWeekdayParens +
	`\s+\d{1,2}:\d{2}(?:\s*[ＡＰAP][ＭM])?)` +
	`\s*(?:に|、|,)?\s*` +
	`(?:(.+?)\s+)?` + // optional display name
	`[<＜]?([\w.+\-]+@[\w.\-]+\.[A-Za-z]{2,})[>＞]?`)

// quotePrefixRe matches the leading `>` quote-prefix of a line.
var quotePrefixRe = regexp.MustCompile(`^((?:>\s?)+)`)

// mailtoLinkRe matches `<mailto:foo@bar>` decorations Outlook appends.
var mailtoLinkRe = regexp.MustCompile(`<mailto:[^<>\s]*>`)

// httpLinkRe matches `<https://...>` decorations Outlook appends.
var httpLinkRe = regexp.MustCompile(`<https?://[^<>\s]*>`)

// trailingWSOrNBSP matches whitespace that should be trimmed at the end
// of a line (preserving the newline itself).
var trailingWSOrNBSP = regexp.MustCompile(`[^\S\n]+(\n|$)`)

// multiNewlineRe matches 3+ consecutive newlines (vertical-space soup).
var multiNewlineRe = regexp.MustCompile(`\n{3,}`)

// leadingNewlinesRe matches leading blank lines after a stripped prefix.
var leadingNewlinesRe = regexp.MustCompile(`^\s*\n+`)

// mashedHeaderRe matches Outlook's mashed conversation-header line that
// appears at the top of replies when the reading pane is copied.
var mashedHeaderRe = regexp.MustCompile(`(?i)^\s*[\w.+\-]+@[\w.\-]+\.[A-Za-z]{2,}` +
	`\s*` +
	`(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+` +
	`\S+\s+\d+,?\s*\d{4}\s+\d{1,2}:\d{2}` +
	`(?:\s*[AP]M)?` +
	`(?:\s+` + toPart + `\s*:\s*[^\n]+(?:\s+` + subjPart + `\s*:\s*[^\n]*)?)?` +
	`\s*(?:\n|$)`)

// fromLineRe matches a "From: ..." line at the start of a string.
var fromLineRe = regexp.MustCompile(`(?i)^` + fromPart + `\s*:\s*\S`)

// sentLineRe matches a "Sent: ..." or "Date: ..." line.
var sentLineRe = regexp.MustCompile(`(?i)^` + sentPart + `\s*:`)

// hdrKeyLineRe matches any header key (From/Sent/Subject/To/Cc/
// Importance/Priority).
var hdrKeyLineRe = regexp.MustCompile(`(?i)^` + hdrKeys + `\s*:`)

// httpLinkifyRe matches URLs to convert into anchor tags.
var httpLinkifyRe = regexp.MustCompile(`(https?://[^\s<>"]+)`)

// ---------------------------------------------------------------------------
// Meta extraction
// ---------------------------------------------------------------------------

// extractQuoteMeta pulls a "<sender> · <date>" chip from a quoted block.
// Angle-bracketed email addresses (<foo@bar.com>) are preserved so
// downstream consumers can identify the sender for chat-bubble alignment.
func extractQuoteMeta(textOrHTML string) string {
	if textOrHTML == "" {
		return ""
	}
	plain := styleTagRe.ReplaceAllString(textOrHTML, " ")
	plain = stripHTMLTagsExceptEmails(plain)
	plain = strings.ReplaceAll(plain, "&nbsp;", " ")
	plain = strings.NewReplacer(
		"&amp;", "&",
		"&lt;", "<",
		"&gt;", ">",
		"&quot;", `"`,
	).Replace(plain)
	if len(plain) > 1500 {
		plain = plain[:1500]
	}
	plain = strings.TrimSpace(collapseWhitespace(plain))

	if fromVal, dateVal := extractHeaderValue(plain, fromPart), extractHeaderValue(plain, sentPart); fromVal != "" || dateVal != "" {
		if len(dateVal) > 80 {
			dateVal = dateVal[:80]
		}
		if fromVal != "" && dateVal != "" {
			return fromVal + " · " + dateVal
		}
		if fromVal != "" {
			return fromVal
		}
		if dateVal != "" {
			return dateVal
		}
	}
	if g := gmailAttrib.FindStringSubmatch(plain); g != nil {
		date := strings.TrimSpace(g[1])
		who := strings.TrimSpace(g[2])
		return who + " · " + date
	}
	if cjk := cjkMetaRe.FindStringSubmatch(plain); cjk != nil {
		date := strings.TrimSpace(cjk[1])
		who := strings.TrimSpace(firstNonEmpty(cjk[2], cjk[3]))
		if who != "" {
			return who + " · " + date
		}
		return date
	}
	return ""
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}

func collapseWhitespace(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	prevSpace := false
	for _, r := range s {
		if r == ' ' || r == '\t' || r == '\n' || r == '\r' {
			if !prevSpace {
				b.WriteByte(' ')
				prevSpace = true
			}
			continue
		}
		prevSpace = false
		b.WriteRune(r)
	}
	return b.String()
}

// ---------------------------------------------------------------------------
// Plaintext path
// ---------------------------------------------------------------------------

// stripMashedHeader removes Outlook's mashed conversation-header line
// from the top of a plaintext body. The same info lives in the envelope
// so it adds no signal.
func stripMashedHeader(text string) string {
	if text == "" {
		return text
	}
	loc := mashedHeaderRe.FindStringIndex(text)
	if loc == nil {
		return text
	}
	rest := text[loc[1]:]
	rest = leadingNewlinesRe.ReplaceAllString(rest, "")
	return rest
}

// normalizeBody strips noise that mail clients (mostly Outlook) inject
// into the plaintext body: duplicate `<mailto:>` link decorations,
// bracketed-URL annotations, repeated blank lines, and the mashed
// conversation-header at the top.
func normalizeBody(text string) string {
	if text == "" {
		return text
	}
	text = stripMashedHeader(text)
	text = mailtoLinkRe.ReplaceAllString(text, "")
	text = httpLinkRe.ReplaceAllString(text, "")
	text = trailingWSOrNBSP.ReplaceAllString(text, `$1`)
	text = multiNewlineRe.ReplaceAllString(text, "\n\n")
	return text
}

// outlookHeaderBlockEnd returns N (exclusive end of the Outlook
// From/Sent/To/Subject header block) if lines[start..N] form an Outlook
// header block at the same base level, otherwise returns start. Requires
// a From: line followed within 5 lines by a Sent:/Date: line.
func outlookHeaderBlockEnd(stripped []string, levels []int, start int) int {
	if start >= len(stripped) {
		return start
	}
	base := levels[start]
	first := strings.TrimSpace(stripped[start])
	if !fromLineRe.MatchString(first) {
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
		if sentLineRe.MatchString(nl) {
			foundSent = true
			break
		}
		if !hdrKeyLineRe.MatchString(nl) {
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
		if hdrKeyLineRe.MatchString(nl) {
			j++
			continue
		}
		break
	}
	return j
}

// plaintextBodyLimit is the maximum plaintext body length we'll attempt
// to parse. Larger bodies return nil (caller renders flat).
const plaintextBodyLimit = 200_000

// parsePlaintext walks `>` quote prefix levels + inline attribution
// markers at any level. Each attribution event AND each `>`-level
// increment counts as one conversation step, with one exception: an
// attribution marker IMMEDIATELY followed by a deeper `>` block is the
// same event as that `>` increase (the classic Gmail "On X wrote:\n>
// quoted" pattern) and contributes only one step.
//
// Returns a flat list of Turn or nil when nothing quoted is detected.
func parsePlaintext(text string) []Turn {
	if text == "" || len(text) > plaintextBodyLimit {
		return nil
	}
	text = normalizeBody(text)
	lines := strings.Split(text, "\n")

	baseLevels := make([]int, len(lines))
	strippedLines := make([]string, len(lines))
	for i, line := range lines {
		prefix := quotePrefixRe.FindString(line)
		n := strings.Count(prefix, ">")
		baseLevels[i] = n
		if n > 0 {
			strippedLines[i] = quotePrefixRe.ReplaceAllString(line, "")
		} else {
			strippedLines[i] = line
		}
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

	turns := make([]Turn, 0)
	var buf []string
	curLevel := 0
	pendingMeta := ""
	depthAtBase := map[int]int{0: 0}
	depth := 0
	prevBase := 0

	lookaheadContentBase := func(startIdx int) int {
		j := startIdx
		for j < len(lines) && strings.TrimSpace(strippedLines[j]) == "" {
			j++
		}
		if j < len(lines) {
			return baseLevels[j]
		}
		return -1
	}

	flush := func() {
		if len(buf) == 0 {
			return
		}
		body := strings.TrimRight(strings.Join(buf, "\n"), " \t")
		if body != "" || curLevel > 0 {
			turns = append(turns, Turn{
				Level:    curLevel,
				BodyHTML: escapeToHTML(body),
				Meta:     pendingMeta,
			})
		}
		buf = buf[:0]
		pendingMeta = ""
	}

	for i := 0; i < len(lines); {
		base := baseLevels[i]
		stripped := strippedLines[i]

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

		isGmail := stripped != "" && gmailLineRe.MatchString(stripped)
		isCJK := cjkAttribLineRe.MatchString(stripped)
		isOrig := origRe.MatchString("\n" + stripped)
		outlookEnd := outlookHeaderBlockEnd(strippedLines, baseLevels, i)
		isOutlook := outlookEnd > i

		if isGmail || isCJK || isOrig || isOutlook {
			attribEnd := outlookEnd
			if !isOutlook {
				attribEnd = i + 1
			}
			metaText := strings.Join(strippedLines[i:attribEnd], "\n")

			// "-----Original Message-----" is almost always immediately
			// followed by an Outlook From:/Sent: header — fold that
			// into the SAME attribution event so we don't double-bump.
			if isOrig {
				j := attribEnd
				for j < len(lines) && baseLevels[j] == base &&
					strings.TrimSpace(strippedLines[j]) == "" {
					j++
				}
				if j < len(lines) && baseLevels[j] == base {
					oe2 := outlookHeaderBlockEnd(strippedLines, baseLevels, j)
					if oe2 > j {
						metaText = metaText + "\n" +
							strings.Join(strippedLines[j:oe2], "\n")
						attribEnd = oe2
					}
				}
			}

			nextBase := lookaheadContentBase(attribEnd)
			flush()
			meta := extractQuoteMeta(metaText)
			if meta == "" {
				lines2 := strings.Split(strings.TrimSpace(metaText), "\n")
				if len(lines2) > 0 {
					meta = lines2[0]
				}
			}
			if nextBase >= 0 && nextBase > base {
				pendingMeta = meta
			} else {
				depth++
				depthAtBase[base] = depth
				curLevel = depth
				pendingMeta = meta
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

// escapeToHTML is a conservative plaintext → HTML conversion: escape,
// then linkify URLs and convert newlines to <br>.
func escapeToHTML(text string) string {
	if text == "" {
		return ""
	}
	out := html.EscapeString(text)
	out = httpLinkifyRe.ReplaceAllStringFunc(out, func(m string) string {
		return `<a href="` + m + `" target="_blank" rel="noopener">` + m + `</a>`
	})
	out = strings.ReplaceAll(out, "\n", "<br>")
	return out
}

// ---------------------------------------------------------------------------
// Public entry point
// ---------------------------------------------------------------------------

// ParseThread is the public entry point. Prefer HTML when available, else
// plaintext. Returns nil if no quoted material was found.
//
// The Go port preserves the plaintext path in full and intentionally
// does not implement the HTML path (no stdlib HTML parser). When an HTML
// body is supplied alone, the function returns nil — callers should
// fall back to the client-side parser, matching the Python
// implementation's behaviour when BeautifulSoup is not installed.
//
// Non-string body_html / body_text arguments return nil (mirrors the
// Python test test_parse_thread_ignores_non_string_bodies).
func ParseThread(bodyHTML, bodyText interface{}) []Turn {
	if s, ok := bodyHTML.(string); ok && s != "" {
		// HTML path intentionally not ported — see package doc. Try
		// the plaintext path (the HTML may be wrapped in <pre> or
		// otherwise contain inline quoting) and otherwise return nil.
		if out := parsePlaintext(s); out != nil {
			return out
		}
	}
	if s, ok := bodyText.(string); ok && s != "" {
		return parsePlaintext(s)
	}
	return nil
}

// ParseThreadStrings is the typed-string convenience wrapper. Equivalent
// to calling ParseThread(bodyHTML, bodyText) with two strings.
func ParseThreadStrings(bodyHTML, bodyText string) []Turn {
	return ParseThread(bodyHTML, bodyText)
}

// ExtractQuoteMeta exposes the meta-extraction helper for callers that
// want to reuse the chip from outside the full thread walker.
func ExtractQuoteMeta(textOrHTML string) string {
	return extractQuoteMeta(textOrHTML)
}
