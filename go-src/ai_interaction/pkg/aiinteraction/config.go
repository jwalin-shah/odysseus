package aiinteraction

// Constants mirror the module-level constants in src/ai_interaction.py.
const (
	// AIChatTimeout is the per-LLM-call timeout in seconds. Mirrors
	// AI_CHAT_TIMEOUT = 120 in the Python source.
	AIChatTimeout = 120

	// MaxDebateRounds is the maximum number of debate rounds allowed
	// in any debate-style tool. Mirrors MAX_DEBATE_ROUNDS = 5.
	MaxDebateRounds = 5

	// MaxPipelineSteps is the maximum number of pipeline steps allowed
	// per pipeline invocation. Mirrors MAX_PIPELINE_STEPS = 10.
	MaxPipelineSteps = 10
)

// EnvImageBlockPrivateIPs mirrors the IMAGE_BLOCK_PRIVATE_IPS env var
// read in src/ai_interaction.py's do_generate_image when validating the
// URL returned by DALL-E.
const EnvImageBlockPrivateIPs = "IMAGE_BLOCK_PRIVATE_IPS"

// EnvGeneratedImagesDir mirrors GENERATED_IMAGES_DIR from src/constants.py.
// It defaults to $DATA_DIR/generated_images when $DATA_DIR is unset; the
// Python constant is computed the same way. The Go port keeps the path
// in package state so tests can override it via SetGeneratedImagesDir.
const EnvGeneratedImagesDir = "ODYSSEUS_GENERATED_IMAGES_DIR"
