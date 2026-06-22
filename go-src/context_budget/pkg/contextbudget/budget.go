package contextbudget

// ComputeInputTokenBudget returns the effective soft input-token budget,
// mirroring `compute_input_token_budget` in src/context_budget.py.
//
// Args:
//
//	configured:    the value read from settings (may be the default).
//	contextLength: the model's discovered context window. Pass 0
//	               when the window is unknown / only a bare fallback
//	               — auto-scaling then stays conservative instead of
//	               trusting an unproven window (review on #4122).
//	explicit:      true if the user set a NON-default budget. The
//	               default value is the "auto" sentinel; any other
//	               value is an explicit cap.
//
// Rules:
//
//   - Explicit user budget is honoured exactly, only clamped to the
//     model's window when that window is known (the user's deliberate
//     choice wins; HardMax is an auto-budget ceiling only — see #1230).
//   - Otherwise (auto), scale to Headroom of the context window,
//     capped at HardMax — so long-context models use their capacity.
//   - When the window is unknown, fall back to Configured (if > 0)
//     or Default.
//
// Negative inputs are normalised to zero, mirroring Python's
// `int(configured or 0)` / `int(context_length or 0)` defensive
// coercion. Headroom is expected to be in (0, 1]; the function does
// not range-check.
func ComputeInputTokenBudget(opts Options) int {
	configured := opts.Configured
	contextLength := opts.ContextLength

	// Mirror `int(configured or 0)` / `int(context_length or 0)`.
	if configured < 0 {
		configured = 0
	}
	if contextLength < 0 {
		contextLength = 0
	}

	if opts.Explicit && configured > 0 {
		if contextLength > 0 {
			if configured < contextLength {
				return configured
			}
			return contextLength
		}
		return configured
	}

	if contextLength > 0 {
		scaled := int(float64(contextLength) * opts.Headroom)
		if scaled > opts.HardMax {
			scaled = opts.HardMax
		}
		if scaled < 1 {
			scaled = 1
		}
		return scaled
	}

	if configured > 0 {
		return configured
	}
	return opts.Default
}
