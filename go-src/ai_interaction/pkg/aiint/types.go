// Package aiint is the Go port of src/ai_interaction.py.
//
// It mirrors the public surface of the Python module — pipeline parsing and
// dispatch, manage_memory, manage_rag, ui_control, and a stubbed
// generate_image — without dragging in the SQLAlchemy/HTTPX stack. HTTP-
// coupled bits live behind interfaces (Manager, ModelResolver, LLMRunner,
// ImageRunner) so tests can swap in fakes.
package aiint

import "time"

// AIChatTimeout is the wall-clock budget for a single LLM call.
// Ported from AI_CHAT_TIMEOUT in src/ai_interaction.py.
const AIChatTimeout = 120 * time.Second

// MaxDebateRounds caps back-and-forth refinement steps.
// Ported from MAX_DEBATE_ROUNDS.
const MaxDebateRounds = 5

// MaxPipelineSteps caps the number of pipeline steps per call.
// Ported from MAX_PIPELINE_STEPS.
const MaxPipelineSteps = 10

// MaxPipelineOutputBytes is the per-step output truncation limit used in the
// Python module (`response[:5000]`). Mirrored so the Go port doesn't return
// unbounded strings.
const MaxPipelineOutputBytes = 5000
