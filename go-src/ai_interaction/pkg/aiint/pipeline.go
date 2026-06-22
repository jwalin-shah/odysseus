package aiint

import (
	"encoding/json"
	"fmt"
	"strings"
)

// PipelineStep is one row of the pipeline input. Mirrors the dict shape
// used in Python's `do_pipeline`: {"model": "...", "instruction": "..."}.
type PipelineStep struct {
	Model       string `json:"model"`
	Instruction string `json:"instruction"`
}

// PipelineResult mirrors the dict returned by Python `do_pipeline`:
// {"results": <markdown>, "steps": [...], "final_output": <string>}.
type PipelineResult struct {
	Results     string           `json:"results"`
	Steps       []map[string]any `json:"steps"`
	FinalOutput string           `json:"final_output"`
}

// ParsePipeline extracts the step list from JSON or line format.
//
// Mirrors the Python parser: try JSON first ({"steps": [...]} or a bare
// array of step dicts), then fall back to the line format
// `model | instruction`. Returns the same error strings the Python module
// emits so tests can match them verbatim.
func ParsePipeline(content string) ([]PipelineStep, error) {
	trimmed := strings.TrimSpace(content)

	if trimmed != "" {
		var raw any
		if err := json.Unmarshal([]byte(trimmed), &raw); err == nil {
			switch v := raw.(type) {
			case map[string]any:
				if s, ok := v["steps"]; ok {
					return decodeSteps(s)
				}
				return nil, fmt.Errorf("steps must be a list")
			case []any:
				return decodeSteps(v)
			}
		}
	}

	// Line-format fallback: each non-empty line is "model | instruction".
	var steps []PipelineStep
	for _, line := range strings.Split(content, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "|", 2)
		if len(parts) != 2 {
			return nil, fmt.Errorf("Each line must be: model | instruction (or use JSON format)")
		}
		steps = append(steps, PipelineStep{
			Model:       strings.TrimSpace(parts[0]),
			Instruction: strings.TrimSpace(parts[1]),
		})
	}
	return steps, nil
}

func decodeSteps(v any) ([]PipelineStep, error) {
	arr, ok := v.([]any)
	if !ok {
		return nil, fmt.Errorf("steps must be a list")
	}
	out := make([]PipelineStep, 0, len(arr))
	for i, item := range arr {
		m, ok := item.(map[string]any)
		if !ok {
			return nil, fmt.Errorf("each step must be an object (index %d)", i)
		}
		out = append(out, PipelineStep{
			Model:       strings.TrimSpace(asString(m["model"])),
			Instruction: strings.TrimSpace(asString(m["instruction"])),
		})
	}
	return out, nil
}

// asString returns the string form of any JSON-decoded scalar (numbers,
// booleans, etc.) so a model id stored as a number still serializes.
func asString(v any) string {
	if v == nil {
		return ""
	}
	if s, ok := v.(string); ok {
		return s
	}
	return fmt.Sprint(v)
}

// FormatPipelineMarkdown builds the readable markdown summary returned by the
// Python module's `do_pipeline`. Truncates each step's output to
// MaxPipelineOutputBytes.
func FormatPipelineMarkdown(steps []PipelineStep, outputs []string) string {
	if len(steps) == 0 {
		return ""
	}
	lines := []string{fmt.Sprintf("# Pipeline Results (%d steps)\n", len(steps))}
	for i, s := range steps {
		out := outputs[i]
		if len(out) > MaxPipelineOutputBytes {
			out = out[:MaxPipelineOutputBytes]
		}
		lines = append(lines, fmt.Sprintf("## Step %d: %s", i+1, s.Model))
		lines = append(lines, fmt.Sprintf("*Instruction: %s*\n", s.Instruction))
		lines = append(lines, out)
		lines = append(lines, "\n---\n")
	}
	return strings.Join(lines, "\n")
}
