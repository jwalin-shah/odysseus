// Package document_actions identifies and removes clearly-junk documents and
// redundant duplicates for an owner. It mirrors the Python
// `src/document_actions.py` module — same conservative rules, same sort-key
// shape — but exposes a small `Store` interface so the function can be tested
// without SQLAlchemy or any database driver.
//
// The package is stdlib-only.
package document_actions

import (
	"errors"
	"regexp"
	"sort"
	"strings"
	"time"
)

// JunkTitles is the set of normalized titles / stripped content strings that
// are considered throwaway. The Python source stores this as a `set`; we
// expose it as a sorted slice so callers (notably the CLI) can pretty-print
// it without depending on map iteration order. Membership checks go through
// IsJunkTitle / IsJunkStrippedContent.
var JunkTitles = []string{
	"untitled", "untitled document", "new document", "document",
	"new email", "new mail", "new message", "reply", "fwd", "re:",
	"test", "testing", "asdf", "asd", "foo", "bar", "baz",
	"tmp", "temp", "scratch", "scratchpad", "draft", "delete",
	"remove", "junk", "trash", "xxx", "abc", "qwerty",
}

var junkTitleSet = func() map[string]struct{} {
	m := make(map[string]struct{}, len(JunkTitles))
	for _, t := range JunkTitles {
		m[t] = struct{}{}
	}
	return m
}()

// MaxExamples caps the number of deletion examples returned in TidyReport.
// The Python source also limits this to 5; the constant lives here so tests
// can assert against it without re-deriving the magic number.
const MaxExamples = 5

// SentinelNoChange is returned by Tidy when the scan produced no deletions.
// The Python source raises `TaskNoop` in that case so the scheduler can
// drop the run row entirely. Go callers can `errors.Is(err, SentinelNoChange)`
// to detect the no-op branch and avoid double-reporting it.
var SentinelNoChange = errors.New("document_actions: no changes")

// Document is the minimal surface Tidy needs from a persisted document. The
// shape mirrors the Python `Document` ORM model — `Title` and `Content` come
// from `current_content`. `UpdatedAt` is a pointer so a doc with neither
// `updated_at` nor `created_at` set round-trips through the sort without
// panicking on a `time.Time{}` vs `time.Time{}` comparison.
type Document struct {
	ID        int64
	Title     string
	Content   string
	Owner     string
	CreatedAt time.Time
	UpdatedAt *time.Time
}

// Store is the dependency the function reads from / writes to. The default
// production wiring is a SQLAlchemy session; the interface lets tests and
// the CLI use a plain in-memory slice.
type Store interface {
	// ListByOwner returns all documents for an owner. An empty owner matches
	// every document, matching the Python `db.query(Document).all()` branch.
	ListByOwner(owner string) ([]Document, error)
	// Delete removes the given document ids. Implementations should be
	// transactional — Tidy calls Delete at most once per invocation.
	Delete(ids []int64) error
}

// TidyReport summarizes a Tidy run. Examples is capped at MaxExamples; the
// "(+N more)" suffix on the summary string accounts for the rest.
type TidyReport struct {
	Scanned    int
	Deleted    int
	Kept       int
	DeletedIDs []int64
	Examples   []string
}

// IsJunkTitle reports whether a normalized (lowercased, whitespace-collapsed)
// title is in the JunkTitles set. Callers must pass a title that has already
// been normalized — Tidy does the normalization itself before calling this.
func IsJunkTitle(s string) bool {
	_, ok := junkTitleSet[s]
	return ok
}

// IsJunkStrippedContent reports whether a content string — after markdown
// noise has been stripped, whitespace collapsed, and the result lowercased
// (i.e. the result of RealLen's intermediate, lowercased) — is in the
// JunkTitles set. This is the third junk rule in the Python source.
func IsJunkStrippedContent(s string) bool {
	return IsJunkTitle(s)
}

// NormTitle normalizes a title for grouping: trim, collapse runs of
// whitespace, lowercase. Non-string inputs collapse to an empty string
// (matches the Python `t if isinstance(t, str) else ""` guard).
func NormTitle(t string) string {
	return collapseWS(strings.TrimSpace(t))
}

// ContentFingerprint builds a stable fingerprint for duplicate detection.
// It strips the `upload_id="..."` attribute of a re-imported PDF and the
// `id=ann-…` random annotation ids, then collapses whitespace and
// lowercases. N imports of the same file collapse to one fingerprint.
func ContentFingerprint(content string) string {
	c := uploadIDRe.ReplaceAllString(content, "upload_id")
	c = annIDRe.ReplaceAllString(c, "id=ann")
	// Replace any run of whitespace with a single space, then trim and
	// lowercase. We do this explicitly (rather than via collapseWS) so
	// the fingerprint matches the Python source's "re.sub(r'\s+', ' ',
	// c).strip().lower()" exactly.
	c = wsRe.ReplaceAllString(c, " ")
	return strings.ToLower(strings.TrimSpace(c))
}

// RealLen returns the length of `content` with markdown noise stripped —
// a "completeness" proxy used to rank duplicates. The function is the same
// in spirit as the Python helper of the same name.
func RealLen(content string) int {
	stripped := headerRe.ReplaceAllString(content, "")
	stripped = markdownNoiseRe.ReplaceAllString(stripped, "")
	stripped = collapseWS(stripped)
	return len(stripped)
}

// IsQuoteChainOnly reports whether `content` looks like an email reply chain
// with no original (non-quote) content. The Python source applies this rule
// only when there's at least one quoted line or an "On … wrote:" header and
// the non-quote content is shorter than 50 chars with a quote ratio above
// 0.4. Tidy is the public entry point that combines those thresholds with
// the other rules; this helper is exported for unit testing.
func IsQuoteChainOnly(content string) bool {
	lines := nonEmptyLines(content)
	if len(lines) == 0 {
		return false
	}
	quoted := 0
	header := 0
	var nonQuote strings.Builder
	for _, ln := range lines {
		trimmed := strings.TrimSpace(ln)
		if strings.HasPrefix(strings.TrimLeft(ln, " \t"), ">") {
			quoted++
			continue
		}
		if onWroteRe.MatchString(trimmed) {
			header++
			continue
		}
		nonQuote.WriteString(trimmed)
		nonQuote.WriteByte('\n')
	}
	if quoted == 0 && header == 0 {
		return false
	}
	nonQuoteContent := strings.TrimSpace(nonQuote.String())
	quoteRatio := float64(quoted) / float64(len(lines))
	return len(nonQuoteContent) < 50 && quoteRatio > 0.4
}

// Tidy is the Go port of `run_document_tidy`. It reads documents for
// `owner` from `store`, applies the four junk rules, then collapses
// duplicate groups down to the most complete copy. Returns a populated
// TidyReport on a successful run; returns SentinelNoChange when nothing
// was deleted (callers can use `errors.Is` to distinguish).
func Tidy(store Store, owner string) (*TidyReport, error) {
	docs, err := store.ListByOwner(owner)
	if err != nil {
		return nil, err
	}

	report := &TidyReport{Scanned: len(docs)}
	survivors := make([]Document, 0, len(docs))
	var deletedIDs []int64

	pushExample := func(label, reason string) {
		if len(report.Examples) >= MaxExamples {
			return
		}
		title := label
		if title == "" {
			title = "(no title)"
		}
		if len(title) > 40 {
			title = title[:40]
		}
		report.Examples = append(report.Examples, title+" ("+reason+")")
	}

	for _, doc := range docs {
		content := strings.TrimSpace(doc.Content)
		title := strings.ToLower(strings.TrimSpace(doc.Title))
		stripped := stripMarkdown(content)
		realLen := len(stripped)

		var reason string
		switch {
		case content == "" || content == "# Untitled":
			reason = "empty"
		case IsJunkTitle(title):
			reason = "junk title '" + title + "'"
		case IsJunkStrippedContent(strings.ToLower(stripped)):
			reason = "throwaway content"
		case IsQuoteChainOnly(content):
			reason = "email quote-chain only"
		default:
			survivors = append(survivors, doc)
			continue
		}
		_ = realLen
		pushExample(doc.Title, reason)
		deletedIDs = append(deletedIDs, doc.ID)
	}

	// Duplicate pass: group survivors by (normalized title, content
	// fingerprint). Groups of size 1 are kept; groups of size >= 2 keep the
	// most complete copy (longest real content, then most recent timestamp)
	// and delete the rest.
	type groupKey struct {
		title string
		fp    string
	}
	groups := make(map[groupKey][]Document)
	for _, doc := range survivors {
		k := groupKey{
			title: NormTitle(doc.Title),
			fp:    ContentFingerprint(doc.Content),
		}
		groups[k] = append(groups[k], doc)
	}

	// Stable order so examples + summary are deterministic across runs.
	keys := make([]groupKey, 0, len(groups))
	for k := range groups {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].title != keys[j].title {
			return keys[i].title < keys[j].title
		}
		return keys[i].fp < keys[j].fp
	})

	for _, k := range keys {
		members := groups[k]
		report.Kept++
		if len(members) < 2 {
			continue
		}
		// Sort by (real_len, hasTimestamp, updatedAt) descending. The
		// hasTimestamp bool prevents Go from comparing a zero time.Time{}
		// against a populated one when both updated_at and created_at are
		// nil — mirrors the Python `_updated(d) is not None` rank.
		sort.SliceStable(members, func(i, j int) bool {
			ri, hi, ti := duplicateSortKey(members[i])
			rj, hj, tj := duplicateSortKey(members[j])
			if ri != rj {
				return ri > rj
			}
			if hi != hj {
				return hi && !hj
			}
			return ti.After(tj)
		})
		keeper := members[0]
		dupes := members[1:]
		pushExample(keeper.Title, "+"+itoa(len(dupes))+" duplicate copies")
		for _, d := range dupes {
			deletedIDs = append(deletedIDs, d.ID)
		}
	}

	report.Deleted = len(deletedIDs)
	report.DeletedIDs = append([]int64(nil), deletedIDs...)

	if report.Deleted > 0 {
		if err := store.Delete(deletedIDs); err != nil {
			return nil, err
		}
	} else {
		return report, SentinelNoChange
	}
	return report, nil
}

// --- helpers ---------------------------------------------------------------

// duplicateSortKey returns the (real_len, hasTimestamp, updatedAt) triple
// used to rank duplicates. `hasTimestamp` is true when the document has
// either an updated_at or a created_at value; this rank-then-timestamp
// shape mirrors the Python source exactly so a nil timestamp never
// collides with a populated one in the comparison.
func duplicateSortKey(d Document) (realLen int, hasTimestamp bool, updatedAt time.Time) {
	realLen = RealLen(d.Content)
	if d.UpdatedAt != nil {
		hasTimestamp = true
		updatedAt = *d.UpdatedAt
		return
	}
	if !d.CreatedAt.IsZero() {
		hasTimestamp = true
		updatedAt = d.CreatedAt
	}
	return
}

// stripMarkdown is the shared markdown-stripping pipeline used by the
// empty/content/quote-chain rules so they all see the same intermediate
// representation that the duplicate pass would compute via RealLen.
func stripMarkdown(content string) string {
	stripped := headerRe.ReplaceAllString(content, "")
	stripped = markdownNoiseRe.ReplaceAllString(stripped, "")
	return collapseWS(stripped)
}

// collapseWS replaces any run of whitespace with a single space.
var wsRe = regexp.MustCompile(`\s+`)

func collapseWS(s string) string {
	return strings.ToLower(strings.TrimSpace(wsRe.ReplaceAllString(s, " ")))
}

// nonEmptyLines splits content on "\n" and drops the lines that are pure
// whitespace. The Python source does this with a list comprehension that
// filters `ln.strip()`, so we do the same.
func nonEmptyLines(content string) []string {
	parts := strings.Split(content, "\n")
	out := parts[:0]
	for _, ln := range parts {
		if strings.TrimSpace(ln) != "" {
			out = append(out, ln)
		}
	}
	return out
}

// itoa is a small dependency-free int formatter used for the duplicate-copy
// count in example labels.
func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}

// Compiled once at package init. Identical to the Python regexes.
var (
	// headerRe matches a leading "#" through "######" at the start of a line
	// followed by whitespace. MULTILINE so "^" anchors on each line.
	headerRe = regexp.MustCompile(`(?m)^#{1,6}\s+`)
	// markdownNoiseRe strips the common markdown emphasis / quote / list /
	// ruler characters the Python source lists.
	markdownNoiseRe = regexp.MustCompile(`[*_` + "`" + `>\-=]+`)
	// uploadIDRe matches the upload_id="..." attribute in HTML-ish content
	// left behind by PDF re-imports. The attribute value can be anything
	// except a double-quote.
	uploadIDRe = regexp.MustCompile(`upload_id="[^"]*"`)
	// annIDRe matches `id=ann-XXX` annotation ids. The character class is
	// [A-Za-z0-9_-]+ to match the Python regex exactly; the leading \b keeps
	// it from eating parts of larger identifiers like `myid=ann-…`.
	annIDRe = regexp.MustCompile(`\bid=ann-[A-Za-z0-9_-]+`)
	// onWroteRe matches a line like "On Mon, 1 Jan 2024, alice@example.com wrote:".
	// The trailing `?` allows the colon-less form ("wrote" with no ":") that
	// the Python regex permits via `?:` in the source regex string.
	onWroteRe = regexp.MustCompile(`^On .+ wrote:?\s*$`)
)
