package assistantlog

import "regexp"

// legacyTagPattern mirrors the Python regex in src/assistant_log.py:
//
//	r"^\s*\*\*\[([^\]]{1,40})\]\*\*\s*"
//
// It captures the optional "**[Category]**" prefix callers used to embed
// in the content so the UI could colour-code by category without
// re-parsing markdown. Go's RE2 syntax matches the Python regex with
// the obvious escapes (\s stays \s inside a backtick literal; \*\* and
// \[\] keep their backslashes).
//
// Character class breakdown:
//
//	^\s*         — leading whitespace is allowed
//	\*\*         — two literal asterisks (markdown bold)
//	\[ ... \]    — square brackets holding the category
//	([^\]]{1,40})— 1..40 chars that are not ']'
//	\]\*\*       — closing bold
//	\s*          — trailing whitespace
var legacyTagPattern = regexp.MustCompile(`^\s*\*\*\[([^\]]{1,40})\]\*\*\s*`)

// ParseLegacyTag extracts the optional "**[Category]**" prefix from s.
//
// On a match:
//
//   - category is the captured inner text (no leading/trailing spaces —
//     the leading \s* in the regex anchors outside the capture, so the
//     trimmed category is what callers should pass to the UI).
//   - rest is s with the prefix stripped, including the trailing
//     whitespace the regex ate.
//   - ok is true.
//
// When s does not start with the prefix, ok is false and category /
// rest are empty. rest equals s when ok is false, so callers can
// safely use rest regardless.
func ParseLegacyTag(s string) (category string, rest string, ok bool) {
	m := legacyTagPattern.FindStringSubmatch(s)
	if m == nil {
		return "", s, false
	}
	return m[1], s[len(m[0]):], true
}
