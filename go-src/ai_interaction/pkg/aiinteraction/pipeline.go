package aiinteraction

import (
	"encoding/json"
	"fmt"
	"strings"
)

// ParsePipelineSteps parses the pipeline tool input. It mirrors
// src/ai_interaction.py:do_pipeline: it first tries a JSON parse
// (looking for either {"steps": [...]} or a bare list), then falls
// back to the "model | instruction" line format.
//
// Return values:
//
//   - on success, returns a non-nil *PipelineRequest.
//   - on parse error or schema error, returns nil plus an error whose
//     message starts with "error: " — matching the {"error": ...}
//     shape the Python source returns so callers don't have to branch
//     on language.
//
// The input is not lower-cased — model specifiers are case-sensitive
// (Anthropic model ids are lower-case already, OpenAI-compatible
// providers may be mixed case).
func ParsePipelineSteps(content string) (*PipelineRequest, error) {
	trimmed := strings.TrimSpace(content)
	if trimmed == "" {
		return nil, fmt.Errorf("error: No pipeline steps provided")
	}

	// 1. Try JSON first.
	var (
		data any
		err  error
	)
	if trimmed[0] == '{' || trimmed[0] == '[' {
		err = json.Unmarshal([]byte(trimmed), &data)
	} else {
		err = fmt.Errorf("not json")
	}
	if err == nil {
		switch v := data.(type) {
		case map[string]any:
			if rawSteps, ok := v["steps"]; ok {
				steps, e := coerceSteps(rawSteps)
				if e != nil {
					return nil, e
				}
				return &PipelineRequest{Steps: steps, Format: "json", Content: content}, nil
			}
			return nil, fmt.Errorf("error: JSON object must contain 'steps' (or use line format: model | instruction)")
		case []any:
			steps, e := coerceSteps(v)
			if e != nil {
				return nil, e
			}
			return &PipelineRequest{Steps: steps, Format: "json", Content: content}, nil
		}
	}

	// 2. Fall back to line format: "model | instruction".
	steps := []PipelineStep{}
	for _, line := range strings.Split(trimmed, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if !strings.Contains(line, "|") {
			return nil, fmt.Errorf("error: Each line must be: model | instruction (or use JSON format)")
		}
		parts := strings.SplitN(line, "|", 2)
		steps = append(steps, PipelineStep{
			Model:       strings.TrimSpace(parts[0]),
			Instruction: strings.TrimSpace(parts[1]),
		})
	}
	if len(steps) == 0 {
		return nil, fmt.Errorf("error: No pipeline steps provided")
	}
	return &PipelineRequest{Steps: steps, Format: "lines", Content: content}, nil
}

// coerceSteps walks an arbitrary []any / []map[string]any / []PipelineStep
// shape and produces a []PipelineStep. Errors carry an "error:" prefix
// so the caller can return them verbatim.
func coerceSteps(raw any) ([]PipelineStep, error) {
	list, ok := raw.([]any)
	if !ok {
		return nil, fmt.Errorf("error: 'steps' must be a list")
	}
	out := make([]PipelineStep, 0, len(list))
	for i, item := range list {
		switch v := item.(type) {
		case map[string]any:
			s := PipelineStep{}
			if m, ok := v["model"].(string); ok {
				s.Model = m
			}
			if inst, ok := v["instruction"].(string); ok {
				s.Instruction = inst
			}
			if s.Model == "" || s.Instruction == "" {
				return nil, fmt.Errorf("error: Step %d: both 'model' and 'instruction' are required", i+1)
			}
			out = append(out, s)
		case PipelineStep:
			if v.Model == "" || v.Instruction == "" {
				return nil, fmt.Errorf("error: Step %d: both 'model' and 'instruction' are required", i+1)
			}
			out = append(out, v)
		default:
			return nil, fmt.Errorf("error: Step %d: must be an object with 'model' and 'instruction'", i+1)
		}
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("error: No pipeline steps provided")
	}
	return out, nil
}

// ValidatePipelineSteps enforces the step limits do_pipeline checks:
// at least one step, no more than MaxPipelineSteps, and per-step both
// model and instruction are non-empty. Returns the same "error: "
// shape ParsePipelineSteps does.
func ValidatePipelineSteps(steps []PipelineStep) error {
	if len(steps) == 0 {
		return fmt.Errorf("error: No pipeline steps provided")
	}
	if len(steps) > MaxPipelineSteps {
		return fmt.Errorf("error: Maximum %d steps allowed", MaxPipelineSteps)
	}
	for i, s := range steps {
		if strings.TrimSpace(s.Model) == "" || strings.TrimSpace(s.Instruction) == "" {
			return fmt.Errorf("error: Step %d: both 'model' and 'instruction' are required", i+1)
		}
	}
	return nil
}

// FormatPipelineResults renders step_outputs in the same shape as the
// Python source's "# Pipeline Results (N steps)\n## Step ...\n" layout.
// The function is pure — the caller provides the per-step outputs.
//
// stepOutputs is the list of {step, model, instruction, output} dicts
// the Python source appends. The Go port reuses the PipelineStepOutput
// struct so callers can populate it directly.
type PipelineStepOutput struct {
	Step        int
	Model       string
	Instruction string
	Output      string
}

func FormatPipelineResults(steps []PipelineStepOutput) string {
	if len(steps) == 0 {
		return "# Pipeline Results (0 steps)\n"
	}
	var b strings.Builder
	fmt.Fprintf(&b, "# Pipeline Results (%d steps)\n", len(steps))
	for _, so := range steps {
		fmt.Fprintf(&b, "## Step %d: %s\n", so.Step, so.Model)
		fmt.Fprintf(&b, "*Instruction: %s*\n\n", so.Instruction)
		b.WriteString(so.Output)
		b.WriteString("\n---\n")
	}
	return b.String()
}

// TruncateOutput mirrors the Python `response[:5000]` truncation in
// do_pipeline. Returning 5000 + "…" would diverge from the Python
// source, so the Go port caps at exactly 5000 bytes (no ellipsis).
func TruncateOutput(s string) string {
	const cap = 5000
	if len(s) > cap {
		return s[:cap]
	}
	return s
}
