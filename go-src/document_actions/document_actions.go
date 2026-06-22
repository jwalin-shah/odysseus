// Package document_actions provides reusable document actions callable from
// both REST routes and the task scheduler.
//
// It is the Go port of src/document_actions.py. The package is deliberately
// data-driven: callers supply a Document model (or any type that implements
// the DocumentView interface) and the package returns a TidyReport describing
// the deletions and survivors. No database or file IO is performed here —
// callers handle persistence.
package document_actions

import (
	"errors"
	"fmt"
	"regexp"
	"sort"
	"strings"
	"time"
)

// ErrTaskNoop is the sentinel returned by RunDocumentTidy when the scan
// completes but no documents were removed. The scheduler can use it to drop
// the run row entirely.
//
// In Python this is src.builtin_actions.TaskNoop. We re-implement it as a
// typed error here so callers don't need to depend on the builtin_actions
// package.
var ErrTaskNoop = errors.New("document_actions: nothing to do")

// JunkTitles is the set of throwaway document titles (and full-body
// contents) that RunDocumentTidy deletes. Comparison is case-folded.
var JunkTitles = map[string]struct{}{
	"untitled": {}, "untitled document": {}, "new document": {}, "document": {},
	"new email": {}, "new mail": {}, "new message": {}, "reply": {}, "fwd": {}, "re:": {},
	"test": {}, "testing": {}, "asdf": {}, "asd": {}, "foo": {}, "bar": {}, "baz": {},
	"tmp": {}, "temp": {}, "scratch": {}, "scratchpad": {}, "draft": {}, "delete": {},
	"remove": {}, "junk": {}, "trash": {}, "xxx": {}, "abc": {}, "qwerty": {},
}

// DocumentView is the minimal document surface RunDocumentTidy needs. Any
// type — a SQL row, a struct, a test fake — that exposes these accessors can
// be tidied without pulling in ORM machinery.
type DocumentView interface {
	GetID() string
	GetOwner() string
	GetTitle() string
	GetContent() string
	GetCreatedAt() *time.Time
	GetUpdatedAt() *time.Time
}

// Document is a convenience adapter for callers that don't want to implement
// the DocumentView interface. It mirrors the fields the Python ORM exposes.
type Document struct {
	ID             string
	Owner          string
	Title          string
	CurrentContent string
	CreatedAt      *time.Time
	UpdatedAt      *time.Time
}

func (d *Document) GetID() string            { return d.ID }
func (d *Document) GetOwner() string         { return d.Owner }
func (d *Document) GetTitle() string         { return d.Title }
func (d *Document) GetContent() string       { return d.CurrentContent }
func (d *Document) GetCreatedAt() *time.Time { return d.CreatedAt }
func (d *Document) GetUpdatedAt() *time.Time { return d.UpdatedAt }

// TidyReport is the result of a tidy pass. Deleted is the list of documents
// that were removed; Kept is the list of survivors. Examples is a short
// (max 5) preview of the deletions suitable for surfacing in a status line.
type TidyReport struct {
	Deleted  []DeletedDoc
	Kept     []DocumentView
	Examples []string
}

// DeletedDoc captures why a document was removed. Reason is a short code
// ("empty", "junk title …", etc.); Label is a 40-char truncated title.
type DeletedDoc struct {
	Doc    DocumentView
	Reason string
	Label  string
}

// internal: pre-compiled regular expressions
var (
	whitespaceRE = regexp.MustCompile(`\s+`)
	// Headers at the start of a line: "# ", "## ", … "###### "
	headingRE = regexp.MustCompile(`(?m)^#{1,6}\s+`)
	// Markdown formatting noise: emphasis, code fences, blockquotes, rules.
	markdownRE = regexp.MustCompile(`[*_` + "`" + `>\-=]+`)
	// "On …, X wrote:" / "On …, X wrote" — the canonical email attribution line.
	emailHeaderRE = regexp.MustCompile(`^On .+ wrote:?\s*$`)
	// PDF source: <… upload_id="abc123" …>
	uploadIDRE = regexp.MustCompile(`upload_id="[^"]*"`)
	// Annotation id="ann-…" — random per-document.
	annIDRE = regexp.MustCompile(`\bid=ann-[A-Za-z0-9_-]+`)
)

// NormTitle normalizes a title for grouping: trim, collapse whitespace,
// lowercase. Non-strings (per the Python regex tolerance we mirror) coerce
// to "" so callers can pass through any value without crashing.
func NormTitle(t string) string {
	s := collapseWS(strings.TrimSpace(t))
	return strings.ToLower(s)
}

// ContentFingerprint returns a stable fingerprint of document content for
// duplicate detection. It strips volatile bits — the `upload_id` of a
// re-imported PDF and the random `id=` of annotations — so N imports of the
// same file collapse to one fingerprint. Whitespace is collapsed and the
// result lowercased.
func ContentFingerprint(content string) string {
	c := uploadIDRE.ReplaceAllString(content, "upload_id")
	c = annIDRE.ReplaceAllString(c, "id=ann")
	c = collapseWS(strings.TrimSpace(c))
	return strings.ToLower(c)
}

// RealLen returns the length of content with markdown noise stripped — a
// "completeness" proxy. It mirrors the inline computation in
// run_document_tidy: drop headers, strip formatting chars, collapse
// whitespace, then take the byte length.
func RealLen(content string) int {
	stripped := headingRE.ReplaceAllString(content, "")
	stripped = markdownRE.ReplaceAllString(stripped, "")
	stripped = collapseWS(strings.TrimSpace(stripped))
	return len(stripped)
}

// collapseWS replaces any run of whitespace (including newlines) with a
// single space. Equivalent to Python's re.sub(r"\s+", " ", s).
func collapseWS(s string) string {
	return whitespaceRE.ReplaceAllString(s, " ")
}

// judgeDoc is the per-document decision function: it reports whether the
// document should be deleted and, if so, why. Returns (delete, reason).
func judgeDoc(d DocumentView) (bool, string) {
	content := strings.TrimSpace(d.GetContent())
	title := strings.ToLower(strings.TrimSpace(d.GetTitle()))
	stripped := strings.ToLower(RealLenContent(content))
	realLen := RealLen(content)

	if content == "" || content == "# Untitled" {
		return true, "empty"
	}
	if _, hit := JunkTitles[title]; hit {
		return true, fmt.Sprintf("junk title %q", title)
	}
	if _, hit := JunkTitles[stripped]; hit {
		return true, "throwaway content"
	}
	// No length-based deletion: short notes are legitimate content.
	// Email reply-chain: only quoted/header lines, no original content.
	if quoteRatio, nonQuote, _, hasHeaders := emailQuoteShape(content); hasHeaders || quoteRatio > 0 {
		_ = nonQuote
		if quoteRatio > 0.4 && len(nonQuote) < 50 {
			return true, "email quote-chain only"
		}
	}
	_ = realLen
	return false, ""
}

// RealLenContent is the public re-export so callers (and tests) can
// reproduce the per-document "real length" the tidy pass uses internally.
func RealLenContent(content string) string {
	stripped := headingRE.ReplaceAllString(content, "")
	stripped = markdownRE.ReplaceAllString(stripped, "")
	stripped = collapseWS(strings.TrimSpace(stripped))
	return stripped
}

// emailQuoteShape inspects a document's body for email-reply-chain markers.
// Returns:
//
//	quoteRatio — fraction of non-blank lines that begin with ">".
//	nonQuote   — the non-quoted, non-header lines concatenated (trimmed).
//	quoted     — the count of quoted lines (debug aid).
//	hasHeader  — true if any line matches "On …, X wrote:".
func emailQuoteShape(content string) (quoteRatio float64, nonQuote string, quoted int, hasHeader bool) {
	lines := strings.Split(content, "\n")
	nonBlank := make([]string, 0, len(lines))
	for _, ln := range lines {
		if strings.TrimSpace(ln) == "" {
			continue
		}
		nonBlank = append(nonBlank, ln)
	}
	if len(nonBlank) == 0 {
		return 0, "", 0, false
	}
	quotedLines := make([]string, 0, len(nonBlank))
	headerLines := 0
	keepLines := make([]string, 0, len(nonBlank))
	for _, ln := range nonBlank {
		trimmed := strings.TrimSpace(ln)
		if strings.HasPrefix(strings.TrimLeft(ln, " \t"), ">") {
			quotedLines = append(quotedLines, ln)
			continue
		}
		if emailHeaderRE.MatchString(trimmed) {
			headerLines++
			hasHeader = true
			continue
		}
		keepLines = append(keepLines, ln)
	}
	quoteRatio = float64(len(quotedLines)) / float64(len(nonBlank))
	nonQuote = strings.TrimSpace(strings.Join(keepLines, "\n"))
	_ = headerLines
	return quoteRatio, nonQuote, len(quotedLines), hasHeader
}

// RunDocumentTidy is the port of src.document_actions.run_document_tidy.
// It scans `docs`, removes clearly-junk documents and redundant duplicates,
// and returns either a TidyReport (with a human-readable summary string) or
// ErrTaskNoop when nothing was removed.
//
// The Python original mutates the database directly; the Go port is
// pure-data — callers handle persistence using the returned TidyReport.
func RunDocumentTidy(docs []DocumentView) (*TidyReport, error) {
	var (
		deletedExamples []string
		deleted         []DeletedDoc
		survivors       []DocumentView
	)

	for _, d := range docs {
		shouldDel, reason := judgeDoc(d)
		if shouldDel {
			if len(deletedExamples) < 5 {
				label := strings.TrimSpace(d.GetTitle())
				if label == "" {
					label = "(no title)"
				}
				if len(label) > 40 {
					label = label[:40]
				}
				deletedExamples = append(deletedExamples, fmt.Sprintf("%s (%s)", label, reason))
			}
			deleted = append(deleted, DeletedDoc{Doc: d, Reason: reason, Label: d.GetTitle()})
			continue
		}
		survivors = append(survivors, d)
	}

	// --- Duplicate pass: group survivors by (normalized title, content
	// fingerprint) and keep only the most complete copy of each group. ---
	type groupKey struct{ title, fp string }
	groups := make(map[groupKey][]DocumentView)
	for _, d := range survivors {
		k := groupKey{NormTitle(d.GetTitle()), ContentFingerprint(d.GetContent())}
		groups[k] = append(groups[k], d)
	}

	var kept []DocumentView
	for _, members := range groups {
		if len(members) < 2 {
			kept = append(kept, members...)
			continue
		}
		// Keep the most complete (longest real content), then most recent.
		// Sort key is total-order safe: a document with both timestamps
		// NULL must not be compared against a datetime on a real-length
		// tie (would panic on Less).
		sort.SliceStable(members, func(i, j int) bool {
			ri, rj := RealLen(members[i].GetContent()), RealLen(members[j].GetContent())
			if ri != rj {
				return ri > rj
			}
			ti, tj := updatedAt(members[i]), updatedAt(members[j])
			hi, hj := ti != nil, tj != nil
			if hi != hj {
				return hi
			}
			if ti == nil {
				return false
			}
			return ti.After(*tj)
		})
		keeper := members[0]
		kept = append(kept, keeper)
		dupes := members[1:]
		if len(deletedExamples) < 5 {
			label := strings.TrimSpace(keeper.GetTitle())
			if label == "" {
				label = "(no title)"
			}
			if len(label) > 40 {
				label = label[:40]
			}
			deletedExamples = append(deletedExamples, fmt.Sprintf("%s (+%d duplicate copies)", label, len(dupes)))
		}
		for _, d := range dupes {
			deleted = append(deleted, DeletedDoc{Doc: d, Reason: "duplicate", Label: d.GetTitle()})
		}
	}

	if len(deleted) == 0 {
		return nil, fmt.Errorf("%w: scanned %d document(s), no junk", ErrTaskNoop, len(docs))
	}

	summary := formatSummary(len(deleted), len(docs), deletedExamples, len(kept))
	_ = summary
	report := &TidyReport{
		Deleted:  deleted,
		Kept:     kept,
		Examples: deletedExamples,
	}
	return report, nil
}

// updatedAt returns the most recent of updated_at / created_at, preferring
// updated_at when both are non-nil. Returns nil if both are nil.
func updatedAt(d DocumentView) *time.Time {
	if u := d.GetUpdatedAt(); u != nil {
		return u
	}
	return d.GetCreatedAt()
}

// formatSummary builds the human-readable summary string the Python
// original returns. It is split out so tests can compare output without
// having to duplicate the "+N more" arithmetic.
func formatSummary(deleted, total int, examples []string, kept int) string {
	preview := strings.Join(examples, "; ")
	extra := ""
	if deleted > len(examples) {
		extra = fmt.Sprintf(" (+%d more)", deleted-len(examples))
	}
	return fmt.Sprintf("Removed %d of %d: %s%s · %d kept", deleted, total, preview, extra, kept)
}
