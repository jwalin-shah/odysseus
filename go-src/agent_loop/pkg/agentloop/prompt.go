package agentloop

import "sort"

// AssemblePrompt builds a deterministic system prompt from a list of tool
// names, a disabled set, and a compact flag. It is the Go port of Python's
// _assemble_prompt + _build_system_prompt. Behavior:
//
//   - toolNames is the SET of tool names the agent has access to (not
//     guaranteed to exist in the prompt template — missing sections are
//     rendered as "[no section: <name>]").
//   - disabledTools names tools the loop should NOT advertise to the model.
//   - compact=true produces a single-line summary listing all tools; false
//     produces full sections joined by "\n\n".
//
// Output is deterministic for a given input — sort.SliceStable of names
// guarantees a stable join order, so test snapshots and prompt caches work.
func AssemblePrompt(toolNames []string, disabledTools map[string]bool, compact bool) string {
	if disabledTools == nil {
		disabledTools = map[string]bool{}
	}
	names := append([]string(nil), toolNames...)
	sort.Strings(names)

	included := make([]string, 0, len(names))
	for _, n := range names {
		if disabledTools[n] {
			continue
		}
		included = append(included, n)
	}

	if compact {
		return assembleCompact(included)
	}
	return assembleFull(included, names, disabledTools)
}

func assembleCompact(included []string) string {
	toolList := "none"
	if len(included) > 0 {
		toolList = joinComma(included)
	}
	return "You are an AI assistant with tool access.\n\n" +
		"Available tools: " + toolList + ".\n\n" +
		defaultAgentRules()
}

func assembleFull(included, all []string, disabledTools map[string]bool) string {
	parts := []string{defaultAgentPreamble()}

	// Full-block sections for known tools, "[no section: ...]" defaults for the rest.
	var fullBlocks []string
	var oneLiners []string
	for _, n := range included {
		section := sectionText(n)
		if section == "" {
			section = "[no section: " + n + "]"
		}
		switch {
		case len(section) >= 3 && section[:3] == "```":
			fullBlocks = append(fullBlocks, section)
		case len(section) >= 2 && section[:2] == "- ":
			oneLiners = append(oneLiners, section)
		default:
			fullBlocks = append(fullBlocks, section)
		}
	}

	if len(fullBlocks) > 0 {
		parts = append(parts, joinSep(fullBlocks, "\n\n"))
	}
	if len(oneLiners) > 0 {
		parts = append(parts, "## Additional tools\n"+joinSep(oneLiners, "\n"))
	}

	// Hint about known-but-not-included tools.
	known := knownToolNames()
	notShown := make([]string, 0)
	for _, n := range known {
		if containsString(included, n) || disabledTools[n] {
			continue
		}
		if !containsString(all, n) {
			continue
		}
		notShown = append(notShown, n)
	}
	if len(notShown) > 0 {
		sample := notShown
		if len(sample) > 5 {
			sample = sample[:5]
		}
		hint := joinComma(sample)
		if len(notShown) > 5 {
			hint += ", ... (" + itoa(len(notShown)-5) + " more)"
		}
		parts = append(parts, "(Other tools available when needed: "+hint+")")
	}

	parts = append(parts, defaultAgentRules())
	return joinSep(parts, "\n\n")
}

// sectionText returns the shipped default prompt section for a tool name.
// Go port: a tiny static table keyed by tool name. The Python source's
// TOOL_SECTIONS dictionary has dozens of entries; the port ships a small
// representative subset and falls back to "[no section: ...]" for the rest.
// This matches the spec's "missing sections get a default" requirement.
func sectionText(name string) string {
	if v, ok := toolSections[name]; ok {
		return v
	}
	return ""
}

// knownToolNames is the static list of tool names the prompt template knows
// about (the "well-known" set).
func knownToolNames() []string {
	out := make([]string, 0, len(toolSections))
	for k := range toolSections {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// toolSections is a tiny representative subset. Real prompt content lives
// in Python's TOOL_SECTIONS; the Go port only needs enough surface area to
// prove AssemblePrompt's join / disable / missing-section logic.
var toolSections = map[string]string{
	"bash":            "- bash: run a shell command (60s timeout, 10K char output limit).",
	"web_search":      "- web_search: search the public web for the given query.",
	"web_fetch":       "- web_fetch: fetch a URL and return its text content.",
	"read_file":       "- read_file: return the contents of a file at <path>.",
	"write_file":      "- write_file: write <content> to <path>.",
	"create_document": "```create_document\n{\"path\": \"...\", \"content\": \"...\"}\n```",
	"edit_document":   "```edit_document\n{\"path\": \"...\", \"edits\": [{\"find\": \"...\", \"replace\": \"...\"}]}\n```",
	"manage_calendar": "- manage_calendar: list/create/update/delete calendar events.",
	"manage_notes":    "- manage_notes: create / list / edit user notes and todos.",
	"manage_memory":   "- manage_memory: add or query persistent user facts.",
	"list_emails":     "- list_emails: list recent messages in an inbox.",
	"send_email":      "```send_email\n{\"to\": \"...\", \"subject\": \"...\", \"body\": \"...\"}\n```",
}

func defaultAgentPreamble() string {
	return "You are an AI assistant with tool access. You can run shell commands, " +
		"execute Python, search the web, read/write files, create and edit documents, " +
		"and more. To use a tool, write a fenced code block with the tool name as " +
		"the language tag."
}

func defaultAgentRules() string {
	return "## Rules\n" +
		"- Only use tools when needed. Don't search for things you already know.\n" +
		"- For web lookup/search/latest/current requests, use web_search or web_fetch.\n" +
		"- Multiple tool blocks per response OK. 60s timeout per tool, 10K char output limit.\n" +
		"- Bias toward action on edit requests. Don't ask for clarification on minor ambiguity.\n" +
		"- Declare when the job is done: stop calling tools and write the final answer."
}

// ---- tiny stdlib shims (avoid dragging strings/strconv for one-liners) ----

func joinComma(s []string) string {
	out := ""
	for i, v := range s {
		if i > 0 {
			out += ", "
		}
		out += v
	}
	return out
}

func joinSep(s []string, sep string) string {
	out := ""
	for i, v := range s {
		if i > 0 {
			out += sep
		}
		out += v
	}
	return out
}

func containsString(s []string, v string) bool {
	for _, x := range s {
		if x == v {
			return true
		}
	}
	return false
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := false
	if n < 0 {
		neg = true
		n = -n
	}
	digits := []byte{}
	for n > 0 {
		digits = append([]byte{byte('0' + n%10)}, digits...)
		n /= 10
	}
	if neg {
		digits = append([]byte{'-'}, digits...)
	}
	return string(digits)
}
