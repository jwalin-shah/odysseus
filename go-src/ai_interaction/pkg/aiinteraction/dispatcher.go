package aiinteraction

import (
	"fmt"
	"strings"
)

// DispatchTool is the Go port of src.ai_interaction.dispatch_ai_tool.
// The Python source only dispatches three tools: pipeline,
// manage_memory, and ui_control. generate_image is exposed as a
// top-level agent tool elsewhere (the dispatcher doesn't route it).
//
// The dispatcher returns a (description, ToolResult) pair mirroring
// the Python source's return shape so a caller can drop the result
// into an SSE / WebSocket stream without translation.
//
// Optional deps are passed via DriverDeps. The dispatcher itself is
// purely synchronous; the LLMCall inside RunPipeline is what the
// caller wires against their async surface.
func DispatchTool(tool, content, sessionID, owner string, deps DriverDeps) (string, ToolResult) {
	action := ""
	if idx := strings.Index(content, "\n"); idx >= 0 {
		action = strings.TrimSpace(content[:idx])
	} else {
		action = strings.TrimSpace(content)
	}
	switch tool {
	case "pipeline":
		desc := "pipeline: running steps"
		req, err := ParsePipelineSteps(content)
		if err != nil {
			return desc, ToolResult{Error: stripErrPrefix(err)}
		}
		out, _ := RunPipeline(req, deps.Resolver, deps.LLM)
		return desc, out
	case "manage_memory":
		preview := action
		if len(preview) > 40 {
			preview = preview[:40]
		}
		desc := fmt.Sprintf("manage_memory: %s", preview)
		out, _ := RunManageMemory(content, deps.MemoryStore, deps.MemoryVector, deps.EventBus, owner)
		return desc, out
	case "ui_control":
		preview := action
		if len(preview) > 60 {
			preview = preview[:60]
		}
		desc := fmt.Sprintf("ui_control: %s", preview)
		out, _ := RunUIControl(content, UIControlOptions{
			SessionID:    sessionID,
			Owner:        owner,
			CustomThemes: deps.Prefs.CustomThemes(),
			Resolver:     deps.Resolver,
		})
		return desc, out
	default:
		desc := fmt.Sprintf("unknown ai tool: %s", tool)
		return desc, ToolResult{Error: fmt.Sprintf("Unknown AI interaction tool: %s", tool)}
	}
}

// StreamTool mirrors stream_ai_tool. The Python source yields an
// async generator that produces one final event with the dispatch
// result. The Go port returns a channel that closes after one send
// — same contract, easier to compose.
func StreamTool(tool, content, sessionID, owner string, deps DriverDeps) <-chan StreamEvent {
	ch := make(chan StreamEvent, 1)
	go func() {
		defer close(ch)
		desc, result := DispatchTool(tool, content, sessionID, owner, deps)
		ch <- StreamEvent{Final: true, Desc: desc, Result: result}
	}()
	return ch
}

// StreamEvent is the per-event payload StreamTool yields. The Python
// source yields {"_final": True, "desc": ..., "result": ...}; the Go
// port exposes the same fields.
type StreamEvent struct {
	Final  bool
	Desc   string
	Result ToolResult
}

// DriverDeps wires the optional surfaces the dispatchers need. All
// fields are optional except Resolver / LLMCall (which RunPipeline
// requires) and MemoryStore (which RunManageMemory requires).
//
// Prefs is the only field that has its own type instead of a flat
// interface — the dispatchers do not call methods on it directly;
// RunUIControl only reads CustomThemes().
type DriverDeps struct {
	Resolver     ModelResolver
	LLM          LLMCall
	MemoryStore  MemoryStore
	MemoryVector MemoryVector
	EventBus     EventBus
	Prefs        PrefsLookup
	// ImageDriver is the surface do_generate_image needs. The
	// dispatcher does not call it directly — callers route the
	// generate_image tool to RunGenerateImage themselves.
	ImageDriver *ImageDriver
}

// PrefsLookup is the minimal PrefsStore surface the dispatcher
// reads. Returning nil for CustomThemes is safe.
type PrefsLookup interface {
	CustomThemes() map[string]any
}

// ImageDriver carries the dependencies RunGenerateImage needs. The
// dispatcher does not route generate_image itself (the Python source
// dispatches it elsewhere); the type lives here so callers that wire
// the full driver set have a single import to make.
type ImageDriver struct {
	Resolver        ModelResolver
	Transport       ImageTransport
	Writer          ImageFileWriter
	Gallery         GalleryWriter
	Safety          URLSafetyChecker
	BlockPrivateIPs bool
	DefaultModel    string
}
