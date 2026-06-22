package aiint

import (
	"strings"
	"testing"
)

func TestParsePipeline_JSON_StepsField(t *testing.T) {
	content := `{"steps":[
		{"model":"a","instruction":"first"},
		{"model":"b","instruction":"second"}
	]}`
	steps, err := ParsePipeline(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(steps) != 2 {
		t.Fatalf("expected 2 steps, got %d", len(steps))
	}
	if steps[0].Model != "a" || steps[0].Instruction != "first" {
		t.Fatalf("unexpected first step: %+v", steps[0])
	}
	if steps[1].Model != "b" || steps[1].Instruction != "second" {
		t.Fatalf("unexpected second step: %+v", steps[1])
	}
}

func TestParsePipeline_JSON_BareArray(t *testing.T) {
	content := `[{"model":"x","instruction":"do x"},{"model":"y","instruction":"do y"}]`
	steps, err := ParsePipeline(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(steps) != 2 || steps[0].Model != "x" || steps[1].Model != "y" {
		t.Fatalf("unexpected steps: %+v", steps)
	}
}

func TestParsePipeline_LineFormat(t *testing.T) {
	content := "model-a | write a haiku about clouds\nmodel-b | translate to french\n"
	steps, err := ParsePipeline(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(steps) != 2 {
		t.Fatalf("expected 2 steps, got %d", len(steps))
	}
	if steps[0].Model != "model-a" || steps[0].Instruction != "write a haiku about clouds" {
		t.Fatalf("unexpected first step: %+v", steps[0])
	}
}

func TestParsePipeline_LineFormat_BlankLinesIgnored(t *testing.T) {
	content := "\n\nmodel-a | first\n\nmodel-b | second\n\n"
	steps, err := ParsePipeline(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(steps) != 2 {
		t.Fatalf("expected 2 steps (blank lines skipped), got %d", len(steps))
	}
}

func TestParsePipeline_EmptyContent(t *testing.T) {
	steps, err := ParsePipeline("")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(steps) != 0 {
		t.Fatalf("expected empty steps, got %+v", steps)
	}
}

func TestParsePipeline_LineMissingPipe(t *testing.T) {
	_, err := ParsePipeline("just-some-text-without-a-pipe")
	if err == nil {
		t.Fatalf("expected error for line without pipe")
	}
	if !strings.Contains(err.Error(), "model | instruction") {
		t.Fatalf("expected helpful error message, got %q", err.Error())
	}
}

func TestParsePipeline_JSON_StepsNotList(t *testing.T) {
	_, err := ParsePipeline(`{"steps":"oops"}`)
	if err == nil {
		t.Fatalf("expected error when steps is not a list")
	}
}

func TestParsePipeline_JSON_StepNotObject(t *testing.T) {
	_, err := ParsePipeline(`{"steps":["bad"]}`)
	if err == nil {
		t.Fatalf("expected error when step is not an object")
	}
}

func TestParsePipeline_MaxStepsAllowed(t *testing.T) {
	// Build MaxPipelineSteps+1 valid steps via line format.
	var b strings.Builder
	for i := 0; i <= MaxPipelineSteps; i++ {
		if i > 0 {
			b.WriteString("\n")
		}
		b.WriteString("model | step instruction ")
	}
	steps, err := ParsePipeline(b.String())
	if err != nil {
		t.Fatalf("unexpected parser error: %v", err)
	}
	if len(steps) <= MaxPipelineSteps {
		t.Fatalf("test setup: expected > MaxPipelineSteps steps, got %d", len(steps))
	}
}

func TestParsePipeline_MissingModelOrInstruction(t *testing.T) {
	_, err := ParsePipeline(`{"steps":[{"model":"","instruction":"x"}]}`)
	if err != nil {
		t.Fatalf("parser should accept empty fields, validation happens later: %v", err)
	}
}

func TestFormatPipelineMarkdown_TruncatesLongOutput(t *testing.T) {
	steps := []PipelineStep{{Model: "m", Instruction: "i"}}
	longOut := strings.Repeat("x", MaxPipelineOutputBytes+50)
	md := FormatPipelineMarkdown(steps, []string{longOut})
	if !strings.Contains(md, "Pipeline Results (1 steps)") {
		t.Fatalf("expected header, got %q", md[:200])
	}
	if strings.Count(md, "x") != MaxPipelineOutputBytes {
		t.Fatalf("expected exactly %d 'x' chars in truncated output, got %d",
			MaxPipelineOutputBytes, strings.Count(md, "x"))
	}
}

func TestFormatPipelineMarkdown_EmptySteps(t *testing.T) {
	if got := FormatPipelineMarkdown(nil, nil); got != "" {
		t.Fatalf("expected empty string for empty steps, got %q", got)
	}
}
