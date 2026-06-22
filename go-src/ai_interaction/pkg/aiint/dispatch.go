package aiint

import (
	"context"
	"errors"
	"fmt"
)

// ErrUnsupported is returned by handler entry points when the caller
// supplied a tool that requires an HTTP-backed interface (LLMRunner,
// ImageRunner, ModelResolver) but the Manager doesn't have one wired up.
// Mirrors the Python module's failure shape: {"error": "..."}.
var ErrUnsupported = errors.New("runner not configured for this tool")

// Dispatch routes `tool` to the matching handler. Pure dispatch — the
// handlers themselves are responsible for validating content and talking
// to the supplied interfaces.
//
// Recognized tools: pipeline, manage_memory, manage_rag, ui_control,
// generate_image. Anything else returns (description, error result).
func Dispatch(tool, content string, mgr *Manager) (description string, result *Result, err error) {
	switch tool {
	case "pipeline":
		result, err = dispatchPipeline(content, mgr)
		return "pipeline: running steps", result, err
	case "manage_memory":
		first := firstNonEmptyLine(content)
		result, err = dispatchManageMemory(content, mgr)
		return fmt.Sprintf("manage_memory: %s", truncate(first, 40)), result, err
	case "manage_rag":
		first := firstNonEmptyLine(content)
		result, err = dispatchManageRAG(content, mgr)
		return fmt.Sprintf("manage_rag: %s", truncate(first, 40)), result, err
	case "ui_control":
		first := firstNonEmptyLine(content)
		result, err = dispatchUIControl(content, mgr)
		return fmt.Sprintf("ui_control: %s", truncate(first, 60)), result, err
	case "generate_image":
		result, err = dispatchGenerateImage(content, mgr)
		return "generate_image", result, err
	default:
		return fmt.Sprintf("unknown ai tool: %s", tool),
			errorResult(fmt.Sprintf("Unknown AI interaction tool: %s", tool)), nil
	}
}

func dispatchPipeline(content string, mgr *Manager) (*Result, error) {
	if mgr == nil {
		return errorResult("Manager not configured"), nil
	}
	if mgr.LLM == nil || mgr.Resolver == nil {
		return errorResult("pipeline requires Resolver + LLM"), nil
	}
	steps, err := ParsePipeline(content)
	if err != nil {
		return errorResult(err.Error()), nil
	}
	if len(steps) == 0 {
		return errorResult("No pipeline steps provided"), nil
	}
	if len(steps) > MaxPipelineSteps {
		return errorResult(fmt.Sprintf("Maximum %d steps allowed", MaxPipelineSteps)), nil
	}

	// Resolve every model first (fail fast) so a missing model short-circuits
	// before any LLM call is made.
	resolved := make([]PipelineStep, len(steps))
	for i, s := range steps {
		if s.Model == "" || s.Instruction == "" {
			return errorResult(fmt.Sprintf("Step %d: both 'model' and 'instruction' are required", i+1)), nil
		}
		r, err := mgr.Resolver.Resolve(context.Background(), s.Model, "")
		if err != nil {
			return errorResult(fmt.Sprintf("Step %d: %s", i+1, err)), nil
		}
		resolved[i] = PipelineStep{Model: r.ModelID, Instruction: s.Instruction}
	}

	outputs := make([]string, len(resolved))
	previous := ""
	ctx, cancel := context.WithTimeout(context.Background(), AIChatTimeout)
	defer cancel()

	for i, s := range resolved {
		var userContent string
		if previous != "" {
			userContent = fmt.Sprintf("Previous step's output:\n\n%s\n\nYour task: %s", previous, s.Instruction)
		} else {
			userContent = s.Instruction
		}
		messages := []ChatMessage{
			{Role: "system", Content: fmt.Sprintf("You are step %d in a processing pipeline. %s", i+1, s.Instruction)},
			{Role: "user", Content: userContent},
		}
		resp, err := mgr.LLM.Complete(ctx, "", s.Model, nil, messages)
		if err != nil {
			return errorResult(fmt.Sprintf("Pipeline failed at step %d: %s", i+1, err)), nil
		}
		if len(resp) > MaxPipelineOutputBytes {
			resp = resp[:MaxPipelineOutputBytes]
		}
		outputs[i] = resp
		previous = resp
	}

	md := FormatPipelineMarkdown(resolved, outputs)

	stepsJSON := make([]map[string]any, len(resolved))
	for i, s := range resolved {
		stepsJSON[i] = map[string]any{
			"step":        i + 1,
			"model":       s.Model,
			"instruction": s.Instruction,
			"output":      outputs[i],
		}
	}

	return &Result{
		OK:      true,
		Details: map[string]any{"steps": stepsJSON, "final_output": previous},
		Results: md,
	}, nil
}

func dispatchManageMemory(content string, mgr *Manager) (*Result, error) {
	if mgr == nil || mgr.Memory == nil {
		return errorResult("Memory manager not available"), nil
	}
	return ManageMemory(content, mgr.Memory, mgr.MemoryVector, "")
}

func dispatchManageRAG(content string, mgr *Manager) (*Result, error) {
	return ManageRAG(content, mgr)
}

func dispatchUIControl(content string, mgr *Manager) (*Result, error) {
	if mgr == nil {
		return errorResult("Manager not configured"), nil
	}
	return UIControl(content, mgr, nil)
}

// dispatchGenerateImage calls mgr.Image.Generate if a runner is wired.
// A nil runner returns ErrUnsupported so callers can branch on the error.
func dispatchGenerateImage(content string, mgr *Manager) (*Result, error) {
	if mgr == nil || mgr.Image == nil {
		return nil, ErrUnsupported
	}
	res, err := mgr.Image.Generate(context.Background(), firstNonEmptyLine(content), "", "", "medium", "")
	if err != nil {
		return errorResult(err.Error()), nil
	}
	return &Result{
		OK: true,
		Details: map[string]any{
			"image_url": res.URL, "image_id": res.ID, "image_prompt": res.Prompt,
			"image_model": res.Model, "image_size": res.Size, "image_quality": res.Quality,
		},
		Results: res.Summary,
	}, nil
}

func firstNonEmptyLine(s string) string {
	for _, l := range splitNonEmptyLines(s) {
		return l
	}
	return s
}

func truncate(s string, n int) string {
	if n <= 0 || len(s) <= n {
		return s
	}
	return s[:n]
}
