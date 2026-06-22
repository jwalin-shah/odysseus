// Helpers for UntrustedContextMessage — port of the two leading-underscore
// private helpers in src/prompt_security.py. Kept in their own file so the
// message-building public API stays readable.
package promptsecurity

import "strings"

// escapeGuardMarkers neutralises delimiter literals inside untrusted text. If
// an attacker embeds the exact guard marker strings they can prematurely close
// the sandbox block and inject instructions outside it. Replacing them with a
// visually distinct but structurally inert token prevents the breakout while
// preserving the original meaning for human review.
//
// Mirrors src.prompt_security._escape_guard_markers.
func escapeGuardMarkers(text string) string {
	text = strings.ReplaceAll(text, GuardOpen, escapedGuardOpen)
	text = strings.ReplaceAll(text, GuardClose, escapedGuardClose)
	return text
}

// sanitizeLabel prepares a source label for inclusion inside the guarded
// block. Even though the label now lives inside the sandboxed region we still
// scrub it for defence-in-depth:
//
//  1. Strip leading/trailing whitespace.
//  2. Collapse every CR/LF run to a single space so the label cannot inject
//     newlines that could escape the "Source: <label>" framing line.
//  3. Escape any embedded guard-marker literals so the label cannot
//     prematurely close the sandbox block.
//
// Mirrors src.prompt_security._sanitize_label.
func sanitizeLabel(label string) string {
	label = strings.TrimSpace(label)
	// Order matters: replace \r\n first, then bare \r, then bare \n. Each
	// subsequent pass is a no-op on the previous run because \r\n has been
	// collapsed to a single space.
	label = strings.ReplaceAll(label, "\r\n", " ")
	label = strings.ReplaceAll(label, "\r", " ")
	label = strings.ReplaceAll(label, "\n", " ")
	label = escapeGuardMarkers(label)
	return label
}
