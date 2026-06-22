package agentloop

import (
	"strings"
	"testing"
)

func TestAssemblePrompt_AllSectionsPresent(t *testing.T) {
	t.Parallel()
	got := AssemblePrompt([]string{"bash", "read_file", "web_search"}, nil, false)
	for _, want := range []string{"bash", "read_file", "web_search"} {
		if !strings.Contains(got, want) {
			t.Errorf("prompt missing tool %q", want)
		}
	}
}

func TestAssemblePrompt_CompactShorter(t *testing.T) {
	t.Parallel()
	full := AssemblePrompt([]string{"bash", "read_file", "write_file"}, nil, false)
	compact := AssemblePrompt([]string{"bash", "read_file", "write_file"}, nil, true)
	if len(compact) >= len(full) {
		t.Fatalf("compact (%d) should be shorter than full (%d)", len(compact), len(full))
	}
	if !strings.Contains(compact, "Available tools:") {
		t.Fatal("compact prompt missing 'Available tools:'")
	}
}

func TestAssemblePrompt_DisabledToolsListed(t *testing.T) {
	t.Parallel()
	disabled := map[string]bool{"bash": true}
	got := AssemblePrompt([]string{"bash", "read_file"}, disabled, false)
	// The disabled tool's section should be excluded from the included set,
	// but the prompt should still mention it in the "other tools" hint or
	// hint at its absence. Most importantly, the bash fence must not appear.
	if strings.Contains(got, "run a shell command (60s timeout, 10K char output limit)") {
		t.Fatal("disabled tool 'bash' section leaked into prompt")
	}
}

func TestAssemblePrompt_MissingSectionDefaultText(t *testing.T) {
	t.Parallel()
	got := AssemblePrompt([]string{"not_a_real_tool_xyz"}, nil, false)
	if !strings.Contains(got, "[no section: not_a_real_tool_xyz]") {
		t.Fatalf("expected '[no section: ...]' placeholder; got:\n%s", got)
	}
}
