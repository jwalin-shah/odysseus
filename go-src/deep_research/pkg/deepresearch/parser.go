package deepresearch

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
)

// StripCodeBlock removes markdown code-block fences (```json ... ```) from
// the start and end of text.  If the text is not fenced, it is returned
// trimmed.
func StripCodeBlock(text string) string {
	text = strings.TrimSpace(text)
	if !strings.HasPrefix(text, "```") {
		return text
	}
	text = fenceOpenRE.ReplaceAllString(text, "")
	text = fenceCloseRE.ReplaceAllString(text, "")
	return strings.TrimSpace(text)
}

var (
	fenceOpenRE  = regexp.MustCompile(`(?s)^` + "```" + `(?:json)?\s*`)
	fenceCloseRE = regexp.MustCompile(`(?s)\s*` + "```" + `$`)
)

// ParseJSONArray extracts a JSON array of strings from LLM output.  It
// mirrors the Python implementation's multi-pass repair strategy:
//  1. Strip code-block fences, try strict json.Unmarshal.
//  2. If the reply is truncated (last '[' has no closing ']'), harvest
//     complete quoted strings after the LAST '['.
//  3. Greedy outermost '\[...\]' match — fall back on parse failure.
//  4. Non-greedy scan keeping the LAST parseable array (handles echoed
//     example arrays in the same reply).
//  5. Last resort: harvest quoted strings from the first '['.
func ParseJSONArray(text string) []string {
	text = StripCodeBlock(text)

	var parsed []any
	if err := json.Unmarshal([]byte(text), &parsed); err == nil {
		if isJSONArray(parsed) {
			return stringifyArray(parsed)
		}
	}

	// Truncated array repair — last '[' has no matching ']'.  Per the Python
	// source, when the reply looks like a truncated array we fall back to
	// harvesting complete quoted strings after the LAST '['.  Only fully
	// closed quoted strings count — a partial trailing fragment like
	// `"query thr` is discarded, matching `re.findall(r'"([^"]*)"', text)`.
	lastStart := strings.LastIndex(text, "[")
	if lastStart != -1 && !strings.Contains(text[lastStart:], "]") {
		if items := quotedStrings(text[lastStart:]); len(items) > 0 {
			return items
		}
	}

	// Greedy outermost array match — mirrors Python's
	// `re.search(r'\[[\s\S]*\]', text)` which spans any inner brackets too.
	if m := greedyArrayRE.FindString(text); m != "" {
		var p []any
		if err := json.Unmarshal([]byte(m), &p); err == nil && isJSONArray(p) {
			return stringifyArray(p)
		}
	}

	// Multiple complete arrays — keep the last parseable one.
	var lastParsed []any
	for _, m := range nonGreedyArrayRE.FindAllString(text, -1) {
		var p []any
		if err := json.Unmarshal([]byte(m), &p); err == nil && isJSONArray(p) {
			lastParsed = p
		}
	}
	if lastParsed != nil {
		return stringifyArray(lastParsed)
	}

	// Last resort — harvest quoted strings from the first '['.
	arrStart := strings.Index(text, "[")
	if arrStart != -1 {
		if items := quotedStrings(text[arrStart:]); len(items) > 0 {
			return items
		}
	}
	return nil
}

var (
	// greedyArrayRE matches the widest [...] pair, including any nested
	// brackets, mirroring Python's `re.search(r'\[[\s\S]*\]', text)`.
	// Using `[\s\S]*` (greedy) means a reply with two complete arrays
	// concatenates into one (oversized) match, which then fails to parse
	// and falls through to the non-greedy multi-array scan.
	greedyArrayRE = regexp.MustCompile(`(?s)\[[\s\S]*\]`)
	// nonGreedyArrayRE matches the smallest [...] pair so we can iterate
	// and pick the last parseable one (handles echoed example arrays).
	nonGreedyArrayRE = regexp.MustCompile(`(?s)\[[^\[\]]*?\]`)
	quotedStrRE      = regexp.MustCompile(`"([^"]*)"`)
)

// ParseJSONObject extracts a JSON object from LLM output.  Mirrors the
// Python implementation: try strict parse after stripping fences, then fall
// back to a greedy outermost match.
func ParseJSONObject(text string) map[string]any {
	text = StripCodeBlock(text)

	var parsed map[string]any
	if err := json.Unmarshal([]byte(text), &parsed); err == nil {
		return parsed
	}

	if m := greedyObjectRE.FindString(text); m != "" {
		var p map[string]any
		if err := json.Unmarshal([]byte(m), &p); err == nil {
			return p
		}
	}
	return nil
}

var greedyObjectRE = regexp.MustCompile(`(?s)\{[^{}]*\}`)

// FormatFindings renders a findings list as markdown with one section per
// finding.  URLs become markdown link targets.  Used as the "new findings"
// section of the synthesis prompt.
func FormatFindings(findings []Finding) string {
	parts := make([]string, 0, len(findings))
	for i, f := range findings {
		url := f.URL
		if url == "" {
			url = "unknown"
		}
		content := f.Summary
		if content == "" {
			if f.Evidence != "" {
				content = truncate(f.Evidence, 1000)
			} else {
				content = "(no content)"
			}
		}
		parts = append(parts, fmt.Sprintf("**Finding %d** — [%s](%s)\n%s",
			i+1, f.Title, url, content))
	}
	return strings.Join(parts, "\n\n")
}

// FallbackReport compiles the gathered findings into a basic report when the
// LLM synthesis step produced no report but the search rounds did collect
// findings.  Mirrors _fallback_report in src/deep_research.py (#1551).
func FallbackReport(question string, findings []Finding) string {
	return fmt.Sprintf(
		"# %s\n\n"+
			"_Automatic synthesis did not complete, so this report lists the "+
			"%d finding(s) gathered during research._\n\n"+
			"%s",
		question, len(findings), FormatFindings(findings))
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func isJSONArray(v []any) bool { return v != nil }

func stringifyArray(items []any) []string {
	out := make([]string, 0, len(items))
	for _, item := range items {
		out = append(out, fmt.Sprintf("%v", item))
	}
	return out
}

func quotedStrings(s string) []string {
	matches := quotedStrRE.FindAllStringSubmatch(s, -1)
	out := make([]string, 0, len(matches))
	for _, m := range matches {
		out = append(out, m[1])
	}
	return out
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
