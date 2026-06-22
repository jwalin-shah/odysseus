package promptsecurity

import "fmt"

// Message is the LLM message envelope produced by UntrustedContextMessage. It
// mirrors the Python dict returned by `untrusted_context_message(label,
// content)`:
//
//	{"role": "user", "content": "...", "metadata": {"trusted": False, "source": label}}
//
// The struct shape is what callers typically marshal to JSON before sending to
// the LLM provider. Go does not have dicts, so a typed struct with explicit
// fields is the closest behavioural equivalent.
type Message struct {
	// Role is always "user" — the Python helper hardcodes this. The LLM is
	// told via the pre-guard header that the following content is data, so
	// the role itself is just the standard user channel.
	Role string `json:"role"`

	// Content is the rendered guarded block. It begins with the
	// UntrustedContextHeader, opens with GuardOpen, embeds the source label
	// and body, and closes with GuardClose.
	Content string `json:"content"`

	// Metadata carries the structured fields callers use to attribute the
	// message in logs / audit pipelines. Trusted is always false; Source is
	// the original (un-sanitized) label passed by the caller.
	Metadata Metadata `json:"metadata"`
}

// Metadata is the structured sidecar that mirrors the Python dict's
// "metadata" key.
type Metadata struct {
	// Trusted is always false. Mirrors the Python helper's hardcoded
	// {"trusted": False}.
	Trusted bool `json:"trusted"`

	// Source is the caller's original label, un-sanitized. The sanitized
	// version (safe for LLM consumption) is embedded in Content; this field
	// preserves the original for logging.
	Source string `json:"source"`
}

// UntrustedContextMessage returns an LLM message that keeps retrieved/source
// text out of the system role. The template is structured so that ONLY the
// hardcoded UntrustedContextHeader appears before GuardOpen — no user- or
// caller-derived text is placed in the pre-guard trusted framing zone. The
// source label and the body content are both placed inside the guarded block
// where the LLM treats them as untrusted data.
//
// A nil content is rendered as an empty string (matches the Python
// `text = "" if content is None else str(content)` branch). Any other type is
// rendered with fmt.Sprintf("%v", content) — close to Python's `str(content)`
// for the common case of a string but does not promise identical formatting
// for exotic types. Callers that need exact byte-for-byte parity for non-
// string content should pre-convert to string before calling.
//
// Mirrors src.prompt_security.untrusted_context_message.
func UntrustedContextMessage(label string, content any) Message {
	safeLabel := sanitizeLabel(label)

	var text string
	if content == nil {
		text = ""
	} else {
		text = fmt.Sprintf("%v", content)
	}
	text = escapeGuardMarkers(text)

	content2 := fmt.Sprintf(
		"%s\n%s\nSource: %s\n%s\n%s",
		UntrustedContextHeader,
		GuardOpen,
		safeLabel,
		text,
		GuardClose,
	)

	return Message{
		Role:    "user",
		Content: content2,
		Metadata: Metadata{
			Trusted: false,
			Source:  label,
		},
	}
}
