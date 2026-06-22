package aiinteraction

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// ---------------------------------------------------------------------------
// Top-level tool drivers
//
// The Python module's do_pipeline, do_manage_memory, do_manage_rag,
// do_ui_control, and do_generate_image all return dicts with a
// "results" or "error" key. The Go port preserves the same shape via
// the ToolResult struct and the corresponding Driver functions below.
// ---------------------------------------------------------------------------

// ToolResult mirrors the dicts the Python tool functions return.
// Results, Error, and the per-action action tags are exposed as
// exported fields. Callers that need to round-trip JSON can serialise
// directly.
//
// The Go port keeps the same field name as the Python source so
// callers that previously read the dict shape can do so without
// translation.
type ToolResult struct {
	Results string `json:"results,omitempty"`
	Error   string `json:"error,omitempty"`
	Action  string `json:"action,omitempty"`
	// Steps is the pipeline's per-step list. The Python source returns
	// it as a list of dicts; the Go port uses PipelineStepOutput so
	// the same field serialises cleanly.
	Steps []PipelineStepOutput `json:"steps,omitempty"`
	// FinalOutput is the pipeline's last assistant reply.
	FinalOutput string `json:"final_output,omitempty"`
	// ImageURL/ImageID/ImagePrompt/ImageModel/ImageSize/ImageQuality
	// are the fields do_generate_image returns.
	ImageURL     string `json:"image_url,omitempty"`
	ImageID      string `json:"image_id,omitempty"`
	ImagePrompt  string `json:"image_prompt,omitempty"`
	ImageModel   string `json:"image_model,omitempty"`
	ImageSize    string `json:"image_size,omitempty"`
	ImageQuality string `json:"image_quality,omitempty"`
	// MemoryID is the id do_manage_memory returns on add/edit/delete.
	MemoryID string `json:"memory_id,omitempty"`
	// Directory is the directory the RAG add/remove action touched.
	Directory string `json:"directory,omitempty"`
	// Extra carries per-action payload (e.g. ui_control event bodies).
	Extra map[string]any `json:"-"`
}

// RunPipeline mirrors do_pipeline. The caller supplies:
//
//   - req: the parsed pipeline request (steps are validated here).
//   - resolver: turns each step's model spec into a (URL, model, headers) tuple.
//   - llm: a synchronous LLM call stub. The Go port does not preserve
//     the Python source's async behaviour — the dispatcher is sync,
//     callers wire their own async surface.
//
// The return value mirrors the dict do_pipeline emits: on success
// {"results": ..., "steps": [...], "final_output": ...}; on failure
// {"error": ...}.
func RunPipeline(req *PipelineRequest, resolver ModelResolver, llm LLMCall) (ToolResult, error) {
	if req == nil {
		return ToolResult{}, fmt.Errorf("error: pipeline request is nil")
	}
	if err := ValidatePipelineSteps(req.Steps); err != nil {
		return ToolResult{Error: stripErrPrefix(err)}, nil
	}
	if resolver == nil {
		return ToolResult{Error: "ResolveModel is not configured"}, nil
	}
	if llm == nil {
		return ToolResult{Error: "LLM runtime is not configured"}, nil
	}

	// Resolve all models first (fail fast, matching the Python source).
	type resolvedStep struct {
		URL         string
		Model       string
		Headers     map[string]string
		Instruction string
		Spec        string
	}
	resolved := make([]resolvedStep, 0, len(req.Steps))
	for i, step := range req.Steps {
		spec := strings.TrimSpace(step.Model)
		if spec == "" {
			return ToolResult{Error: fmt.Sprintf("Step %d: both 'model' and 'instruction' are required", i+1)}, nil
		}
		m, err := resolver(spec, "")
		if err != nil {
			return ToolResult{Error: fmt.Sprintf("Step %d: %s", i+1, stripErrPrefix(err))}, nil
		}
		resolved = append(resolved, resolvedStep{
			URL:         m.EndpointURL,
			Model:       m.ModelID,
			Headers:     m.Headers,
			Instruction: step.Instruction,
			Spec:        spec,
		})
	}

	stepOutputs := make([]PipelineStepOutput, 0, len(resolved))
	previousOutput := ""
	ctx := context.Background()
	for i, r := range resolved {
		userContent := r.Instruction
		if previousOutput != "" {
			userContent = fmt.Sprintf("Previous step's output:\n\n%s\n\nYour task: %s", previousOutput, r.Instruction)
		}
		messages := []ChatMessage{
			{Role: "system", Content: fmt.Sprintf("You are step %d in a processing pipeline. %s", i+1, r.Instruction)},
			{Role: "user", Content: userContent},
		}
		reply, err := llm(ctx, r.URL, r.Model, r.Headers, messages, AIChatTimeout)
		if err != nil {
			return ToolResult{Error: fmt.Sprintf("Pipeline failed at step %d: %s", i+1, err.Error())}, nil
		}
		stepOutputs = append(stepOutputs, PipelineStepOutput{
			Step:        i + 1,
			Model:       r.Model,
			Instruction: r.Instruction,
			Output:      TruncateOutput(reply),
		})
		previousOutput = reply
	}
	return ToolResult{
		Results:     FormatPipelineResults(stepOutputs),
		Steps:       stepOutputs,
		FinalOutput: previousOutput,
	}, nil
}

// RunManageMemory mirrors do_manage_memory. The action parser is
// reusable; the driver applies the parsed action against the
// injected MemoryStore. The MemoryVector interface is optional — the
// driver probes Healthy() and skips the vector update when it
// reports false.
func RunManageMemory(content string, store MemoryStore, vec MemoryVector, bus EventBus, owner string) (ToolResult, error) {
	action, err := ParseMemoryAction(content)
	if err != nil {
		return ToolResult{Error: stripErrPrefix(err)}, nil
	}
	if store == nil {
		return ToolResult{Error: "Memory manager not available"}, nil
	}

	switch action.Action {
	case "list":
		memories := store.Load(owner)
		filtered := memories
		if action.Category != "" {
			filtered = make([]MemoryEntry, 0, len(memories))
			for _, m := range memories {
				if strings.EqualFold(m.Category, action.Category) {
					filtered = append(filtered, m)
				}
			}
		}
		return ToolResult{Results: FormatMemoryList(filtered, "")}, nil

	case "add":
		entry, err := store.AddEntry(action.Text, "ai_agent", action.Category, owner)
		if err != nil {
			return ToolResult{Error: err.Error()}, nil
		}
		// Persist alongside LoadAll so the in-memory list reflects the
		// new entry. The Python source does this exact dance.
		all := store.LoadAll()
		all = append(all, entry)
		if err := store.Save(all); err != nil {
			return ToolResult{Error: err.Error()}, nil
		}
		if vec != nil && vec.Healthy() {
			_ = vec.Add(entry.ID, entry.Text)
		}
		if bus != nil {
			bus.Fire("memory_added", owner)
		}
		return ToolResult{
			Action:   "add",
			MemoryID: entry.ID,
			Results:  fmt.Sprintf("Memory added: [%s] %s", entry.Category, entry.Text),
		}, nil

	case "edit":
		all := store.LoadAll()
		fullID := ""
		found := false
		for i, m := range all {
			if !strings.HasPrefix(m.ID, action.MemoryID) {
				continue
			}
			if owner != "" && m.Owner != owner {
				return ToolResult{Error: fmt.Sprintf("Memory '%s' not found", action.MemoryID)}, nil
			}
			all[i].Text = action.NewText
			all[i].Timestamp = time.Now().Unix()
			fullID = m.ID
			found = true
			break
		}
		if !found {
			return ToolResult{Error: fmt.Sprintf("Memory '%s' not found", action.MemoryID)}, nil
		}
		if err := store.Save(all); err != nil {
			return ToolResult{Error: err.Error()}, nil
		}
		if vec != nil && vec.Healthy() {
			_ = vec.Add(fullID, action.NewText)
		}
		return ToolResult{
			Action:   "edit",
			MemoryID: action.MemoryID,
			Results:  fmt.Sprintf("Memory updated: %s", action.NewText),
		}, nil

	case "delete":
		all := store.LoadAll()
		fullID := ""
		deleteID := ""
		found := false
		for _, m := range all {
			if !strings.HasPrefix(m.ID, action.MemoryID) {
				continue
			}
			if owner != "" && m.Owner != owner {
				return ToolResult{Error: fmt.Sprintf("Memory '%s' not found", action.MemoryID)}, nil
			}
			fullID = m.ID
			deleteID = m.ID
			found = true
			break
		}
		if !found {
			return ToolResult{Error: fmt.Sprintf("Memory '%s' not found", action.MemoryID)}, nil
		}
		filtered := make([]MemoryEntry, 0, len(all))
		for _, m := range all {
			if m.ID != deleteID {
				filtered = append(filtered, m)
			}
		}
		if err := store.Save(filtered); err != nil {
			return ToolResult{Error: err.Error()}, nil
		}
		if vec != nil && fullID != "" && vec.Healthy() {
			_ = vec.Remove(fullID)
		}
		return ToolResult{
			Action:   "delete",
			MemoryID: action.MemoryID,
			Results:  fmt.Sprintf("Memory '%s' deleted", action.MemoryID),
		}, nil

	case "search":
		all := store.Load(owner)
		var results []MemoryEntry
		if r, ok := tryRelevantMemories(store, action.Query, all); ok {
			results = r
		}
		if results == nil {
			results = FilterMemoriesByText(all, action.Query)
		}
		return ToolResult{Results: FormatMemorySearch(results, action.Query)}, nil

	default:
		return ToolResult{Error: fmt.Sprintf("Unknown action '%s'. Use: list, add, edit, delete, search", action.Action)}, nil
	}
}

// RunManageRAG mirrors do_manage_rag. The PersonalDocsManager is
// used for the list/remove paths; the RAGManager is used for the
// add_directory path.
func RunManageRAG(content string, rag RAGManager, pdocs PersonalDocsManager) (ToolResult, error) {
	action, err := ParseRAGAction(content)
	if err != nil {
		return ToolResult{Error: stripErrPrefix(err)}, nil
	}
	switch action.Action {
	case "list":
		if pdocs == nil {
			return ToolResult{Results: "Personal docs manager not available. RAG may not be configured."}, nil
		}
		files := pdocs.IndexedFiles()
		dirs := pdocs.IndexedDirectories()
		return ToolResult{Results: FormatRAGList(files, dirs)}, nil
	case "add_directory":
		expanded := ExpandDirectory(action.Directory)
		// File-system check is delegated to the caller (the package
		// doesn't know whether the path is reachable in the test
		// environment). RAGManager.IndexPersonalDocuments returns an
		// error if the path is missing.
		if rag == nil {
			return ToolResult{Error: "RAG manager not available"}, nil
		}
		result, err := rag.IndexPersonalDocuments(expanded)
		if err != nil {
			return ToolResult{Error: fmt.Sprintf("Failed to index directory: %s", err.Error())}, nil
		}
		indexed := 0
		if result != nil {
			indexed = result["indexed"]
		}
		return ToolResult{
			Action:    "add_directory",
			Directory: expanded,
			Results:   fmt.Sprintf("Directory '%s' added to RAG index (%d files indexed)", expanded, indexed),
		}, nil
	case "remove_directory":
		if pdocs == nil {
			return ToolResult{Error: "Personal docs manager not available"}, nil
		}
		if err := pdocs.RemoveDirectory(action.Directory); err != nil {
			return ToolResult{Error: fmt.Sprintf("Failed to remove directory: %s", err.Error())}, nil
		}
		return ToolResult{
			Action:    "remove_directory",
			Directory: action.Directory,
			Results:   fmt.Sprintf("Directory '%s' removed from RAG index", action.Directory),
		}, nil
	default:
		return ToolResult{Error: fmt.Sprintf("Unknown action '%s'. Use: list, add_directory, remove_directory", action.Action)}, nil
	}
}

// RunUIControl mirrors do_ui_control. The opts struct wires the
// per-action dependencies the dispatch needs.
func RunUIControl(content string, opts UIControlOptions) (ToolResult, error) {
	evt, err := BuildUIControlEvent(content, opts)
	if err != nil {
		return ToolResult{Error: stripErrPrefix(err)}, nil
	}
	return ToolResult{
		Results: evt.Results,
		Extra:   evt.ToMap(),
	}, nil
}

// RunGenerateImage mirrors do_generate_image. The driver is split
// into discrete stages so tests can plug each one independently.
//
// The driver's "success" path returns an ImageResponse-shaped
// ToolResult: image_url/image_id/image_prompt/image_model/image_size/
// image_quality. The Python source returns the same set of fields.
func RunGenerateImage(content string, opts ImageOptions) (ToolResult, error) {
	req, err := ParseImageRequest(content)
	if err != nil {
		return ToolResult{Error: stripErrPrefix(err)}, nil
	}
	// Resolve the model. The Go port delegates this to the resolver
	// so production callers wire the real ModelEndpoint store.
	if opts.Resolver == nil {
		return ToolResult{Error: "Image model resolver is not configured"}, nil
	}
	spec := strings.TrimSpace(req.Model)
	if spec == "" && opts.DefaultModel != "" {
		spec = opts.DefaultModel
	}
	if spec == "" {
		// Auto-detect: try the same fallback list do_generate_image uses.
		for _, candidate := range ImageFallbackCandidates {
			if _, err := opts.Resolver(candidate, opts.Owner); err == nil {
				spec = candidate
				break
			}
		}
	}
	if spec == "" {
		return ToolResult{Error: "No image model found. Configure one in Admin → Image Generation."}, nil
	}
	resolved, err := opts.Resolver(spec, opts.Owner)
	if err != nil {
		return ToolResult{Error: fmt.Sprintf("No endpoint found with image model '%s'. Configure an OpenAI-compatible endpoint with image generation support.", spec)}, nil
	}
	isGPTImage, isDalle, isLocalDiff := ClassifyImageModel(resolved.ModelID)
	size := NormalizeImageSize(req.Size, isGPTImage, isDalle)
	quality := NormalizeImageQuality(req.Quality, isGPTImage, isLocalDiff)

	imagesURL := buildImagesURL(resolved.EndpointURL)
	payload := ImageAPIPayload(resolved.ModelID, req.Prompt, size, quality, isGPTImage, isDalle, isLocalDiff)

	body, err := opts.Transport.Generate(opts.Context, imagesURL, resolved.Headers, mustJSON(payload))
	if err != nil {
		return ToolResult{Error: fmt.Sprintf("Image generation error: %s", err.Error())}, nil
	}
	parsed, err := parseJSONObject(body)
	if err != nil {
		return ToolResult{Error: fmt.Sprintf("Image generation error: invalid response: %s", err.Error())}, nil
	}
	images, _ := parsed["data"].([]any)
	if len(images) == 0 {
		return ToolResult{Error: "No images returned from API"}, nil
	}
	img, _ := images[0].(map[string]any)
	if img == nil {
		return ToolResult{Error: "Image API returned unexpected format (no b64_json or url)"}, nil
	}

	imageURL := ""
	imageID := ""
	if b64, ok := img["b64_json"].(string); ok && b64 != "" {
		bytes, err := DecodeBase64Image(b64)
		if err != nil {
			return ToolResult{Error: fmt.Sprintf("Image generation error: invalid b64: %s", err.Error())}, nil
		}
		filename, err := opts.Writer.WriteFile(req.Prompt, bytes)
		if err != nil {
			return ToolResult{Error: fmt.Sprintf("Image generation error: write failed: %s", err.Error())}, nil
		}
		imageURL = "/api/generated-image/" + filename
		if opts.Gallery != nil {
			imageID = opts.Gallery.SaveImage(filename, req.Prompt, resolved.ModelID, size, quality, opts.SessionID, opts.Owner)
		}
	} else if u, ok := img["url"].(string); ok && u != "" {
		if opts.Safety != nil {
			ok, reason := opts.Safety.CheckOutbound(u, opts.BlockPrivateIPs)
			if !ok {
				return ToolResult{Error: "Image API returned unsafe image URL: " + reason}, nil
			}
		}
		dl, err := opts.Transport.Download(opts.Context, u)
		if err == nil && len(dl) > 0 {
			filename, err := opts.Writer.WriteFile(req.Prompt, dl)
			if err == nil {
				imageURL = "/api/generated-image/" + filename
				if opts.Gallery != nil {
					imageID = opts.Gallery.SaveImage(filename, req.Prompt, resolved.ModelID, size, quality, opts.SessionID, opts.Owner)
				}
			} else {
				imageURL = u
			}
		} else {
			imageURL = u
		}
	} else {
		return ToolResult{Error: "Image API returned unexpected format (no b64_json or url)"}, nil
	}

	finalQuality := quality
	if finalQuality == "" {
		finalQuality = "medium"
	}
	return ToolResult{
		Results:      fmt.Sprintf("Generated image for: %s", truncate(req.Prompt, 100)),
		ImageURL:     imageURL,
		ImageID:      imageID,
		ImagePrompt:  req.Prompt,
		ImageModel:   resolved.ModelID,
		ImageSize:    size,
		ImageQuality: finalQuality,
	}, nil
}

// ImageOptions configures RunGenerateImage. Resolver + Transport are
// required; the other fields are optional with safe fallbacks.
type ImageOptions struct {
	Context         context.Context
	Resolver        ModelResolver
	Transport       ImageTransport
	Writer          ImageFileWriter
	Gallery         GalleryWriter
	Safety          URLSafetyChecker
	BlockPrivateIPs bool
	DefaultModel    string
	SessionID       string
	Owner           string
}

// ImageFileWriter writes the raw bytes for a generated image and
// returns the filename used for the web-facing URL.
type ImageFileWriter interface {
	WriteFile(prompt string, data []byte) (filename string, err error)
}

// buildImagesURL mirrors the base-url surgery do_generate_image does
// to convert the chat-completions URL into the images endpoint URL.
func buildImagesURL(chatURL string) string {
	base := chatURL
	base = strings.ReplaceAll(base, "/chat/completions", "")
	base = strings.ReplaceAll(base, "/v1/messages", "")
	base = strings.TrimRight(base, "/")
	return base + "/images/generations"
}

// mustJSON is a tiny shim around encoding/json.Marshal that panics on
// failure. The package only ever marshals map[string]any with string
// values, so a marshal error is a programmer error and a panic is
// the right behaviour. Tests can swap the call site if they need a
// non-panicking variant.
func mustJSON(v any) []byte {
	b, err := jsonMarshal(v)
	if err != nil {
		// The Go port converts a marshal error to an empty body; the
		// caller will surface a transport error.
		return nil
	}
	return b
}

// stripErrPrefix removes the optional "error: " prefix the parser
// helpers add. ToolResult.Error carries the same shape the Python
// source emits — callers that pre-strip the prefix should pass the
// un-stripped error here.
func stripErrPrefix(err error) string {
	if err == nil {
		return ""
	}
	s := err.Error()
	s = strings.TrimPrefix(s, "error: ")
	return s
}

// relevantMemoriesProbe is the type-assertion helper the dispatch
// layer uses to call a MemoryStore's optional RelevantMemories
// method without burning a build-time check on the function value
// being non-nil (which is always true — Go disallows assigning nil
// to a method-bound field of an interface value, but the call would
// still fail with a nil receiver at runtime).
//
// The helper returns ok=false when the underlying type does not
// implement RelevantMemories; callers fall back to a substring scan.
type relevantMemoriesProbe interface {
	RelevantMemories(query string, memories []MemoryEntry, threshold float64, maxItems int) ([]MemoryEntry, bool)
}

func tryRelevantMemories(store MemoryStore, query string, all []MemoryEntry) ([]MemoryEntry, bool) {
	if probe, ok := store.(relevantMemoriesProbe); ok {
		return probe.RelevantMemories(query, all, 0.05, 20)
	}
	return nil, false
}

// truncate mirrors Python's "..." suffix for prompt previews.
func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}
