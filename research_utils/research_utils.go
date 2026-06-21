// Package research_utils provides shared utilities for deep research.
//
// This is a Go port of src/research_utils.py. It centralizes text cleaning
// (stripping of thinking / reasoning patterns from LLM output) and source
// quality filtering (detection of low-quality boilerplate / error text).
//
// The original Python strip_thinking delegates to src.text_helpers.strip_think
// which is not part of this port. StripThinking below is a best-effort inline
// reimplementation of the same intent: it removes common thinking / reasoning
// patterns and passes everything else through unchanged.
package research_utils

import (
	"regexp"
	"strings"
)

// LowQualityMarkers is the case-insensitive list of substrings used by
// IsLowQuality to detect boilerplate, error text, and other low-quality
// content. Order and contents are an exact port of the Python
// LOW_QUALITY_MARKERS list.
//
// Callers may append to this slice at runtime to extend detection.
var LowQualityMarkers = []string{
	"insufficient to",
	"content is insufficient",
	"no substantive data",
	"does not contain",
	"not relevant to",
	"no relevant information",
	"unable to extract",
	"completely unrelated",
	"boilerplate",
	"footer text",
	// Phrases (not bare "cookie"/"copyright") so we still catch boilerplate
	// like consent banners and footers without discarding legitimate findings
	// that merely discuss cookies or copyright as their subject.
	"cookie consent",
	"cookie banner",
	"cookie notice",
	"copyright notice",
	"copyright footer",
	"all rights reserved",
}

// thinkingBlockRe matches a <thinking>...</thinking> or <reasoning>...</reasoning>
// block (non-greedy, case-insensitive, dotall via [\s\S]).
var thinkingBlockRe = regexp.MustCompile(`(?is)<(?:thinking|reasoning)>[\s\S]*?</(?:thinking|reasoning)>`)

// ellipsisThinkingRe matches "...thinking..."-style blocks. The original Python
// helper from src.text_helpers strips sections wrapped in triple-dotted
// thinking markers; we approximate that by removing any line that consists
// entirely of "..." separators surrounding the word "thinking" (or its
// reasoning analogues). Anything else is left untouched.
var ellipsisThinkingRe = regexp.MustCompile(`(?im)^\s*\.{3,}\s*(thinking|reasoning|thoughts?|reasoning trace)\s*\.{3,}\s*$[\s\S]*?^\s*\.{3,}\s*$\n?`)

// thoughtPrefixRe matches a line that begins with "Thought:" or "Reasoning:".
// These are common LLM prefix tokens that should be stripped.
var thoughtPrefixRe = regexp.MustCompile(`(?im)^\s*(?:thought|reasoning)\s*:\s*[^\n]*\n?`)

// quoteReasoningRe matches Markdown-style blockquote lines that look like
// reasoning traces: lines starting with ">" and containing the word
// "think" or "reason".
var quoteReasoningRe = regexp.MustCompile(`(?im)^[ \t]*>[^\n]*(?:think|reason)[^\n]*\n?`)

// stripThink is the best-effort Go port of the Python
// src.text_helpers.strip_think helper that the original
// src/research_utils.py delegates to. It strips:
//
//   - <thinking>...</thinking> and <reasoning>...</reasoning> blocks
//   - "...thinking..." / "...reasoning..." fenced blocks
//   - Lines that begin with "Thought:" or "Reasoning:"
//   - Markdown blockquote lines that look like reasoning traces
//
// Unknown patterns are passed through unchanged. The caller is expected to
// have already verified the input is non-nil.
func stripThink(text string) string {
	if text == "" {
		return text
	}
	out := text
	out = thinkingBlockRe.ReplaceAllString(out, "")
	out = ellipsisThinkingRe.ReplaceAllString(out, "")
	out = thoughtPrefixRe.ReplaceAllString(out, "")
	out = quoteReasoningRe.ReplaceAllString(out, "")
	// Collapse runs of 3+ blank lines produced by stripping into a single
	// blank line, and trim trailing whitespace on each line.
	out = collapseBlankLines(out)
	return out
}

var threeOrMoreNewlinesRe = regexp.MustCompile(`\n{3,}`)

// collapseBlankLines replaces runs of three or more consecutive newlines
// (with optional whitespace between them) with a single blank line, and
// trims trailing whitespace from each line.
func collapseBlankLines(s string) string {
	lines := strings.Split(s, "\n")
	for i, ln := range lines {
		lines[i] = strings.TrimRight(ln, " \t\r")
	}
	joined := strings.Join(lines, "\n")
	return threeOrMoreNewlinesRe.ReplaceAllString(joined, "\n\n")
}

// StripThinking removes thinking / reasoning patterns from LLM output.
//
// This is the Go equivalent of the Python
// src.research_utils.strip_thinking helper. It mirrors the Python
// "preserve None passthrough" contract by accepting a *string and
// returning a *string: nil in, nil out.
//
// Behavior on non-nil input is a best-effort inline port of
// src.text_helpers.strip_think (which is not part of this port). It
// strips <thinking>...</thinking> and <reasoning>...</reasoning> blocks,
// "...thinking..."-style fenced sections, "Thought:" / "Reasoning:"
// prefixed lines, and Markdown blockquote lines that look like reasoning
// traces. Unknown patterns are passed through unchanged.
func StripThinking(text *string) *string {
	if text == nil {
		return nil
	}
	cleaned := stripThink(*text)
	return &cleaned
}

// IsLowQuality reports whether summary looks like boilerplate, error text,
// or other low-quality content. The check is a direct port of the Python
// is_low_quality: empty input is low quality, otherwise any of the
// LowQualityMarkers substrings (case-insensitive) present in summary
// triggers a true result. On any unexpected panic (defensive — Go strings
// rarely panic, but unicode operations can surprise), it returns false to
// match the Python "fail open" semantics.
func IsLowQuality(summary string) (result bool) {
	defer func() {
		if r := recover(); r != nil {
			result = false
		}
	}()
	if summary == "" {
		return true
	}
	low := strings.ToLower(summary)
	for _, marker := range LowQualityMarkers {
		if strings.Contains(low, marker) {
			return true
		}
	}
	return false
}
