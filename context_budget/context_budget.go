// Package context_budget derives the effective soft input-token budget for the
// agent loop. It is a faithful port of src/context_budget.py (#1170).
//
// The agent soft-trims its input context to “agent_input_token_budget“ (default
// 6000). The old computation was “min(context_length or budget, budget)“, which
// made the 6000 default a hard ceiling for *every* model — so a 128K or 1M
// context model was silently capped at 6000 input tokens even though it can hold
// far more.
//
// This package derives the effective budget from the model's discovered context
// window when the user has NOT set an explicit budget, while still honouring an
// explicit setting exactly (clamped to the window). Pure and side-effect free
// so it is unit-testable.
package context_budget

// DefaultHardMax is the auto-budget ceiling. Generous so long-context models
// are unblocked without sending a pathologically large prompt every agent
// turn. Tunable; chosen to fully cover 128K models and give 1M models a large
// but bounded budget.
const DefaultHardMax = 200_000

// DefaultBudget is the conservative fallback used when the model window is
// unknown. It is also the "auto" sentinel — a configured value that equals
// this default does NOT count as explicit (see BudgetIsExplicit).
const DefaultBudget = 6_000

// DefaultHeadroom is the fraction of the model's discovered context window to
// use as the auto budget.
const DefaultHeadroom = 0.85

// Options carries the keyword-only arguments of the Python implementation.
// Zero values mean "use the corresponding Default* constant".
//
//   - Default: conservative fallback used when the model window is unknown
//     AND no configured value is supplied.
//   - Headroom: fraction of the model's context window used as the auto budget.
//   - HardMax: ceiling for the auto budget. Does NOT apply to an explicit user
//     budget (the user's deliberate choice wins — see #1230).
type Options struct {
	Default  int
	Headroom float64
	HardMax  int
}

// resolve fills in zero-valued fields from the package-level defaults.
// Caller never sees an Options with zero values.
func (o Options) resolve() Options {
	if o.Default == 0 {
		o.Default = DefaultBudget
	}
	if o.Headroom == 0 {
		o.Headroom = DefaultHeadroom
	}
	if o.HardMax == 0 {
		o.HardMax = DefaultHardMax
	}
	return o
}

// ComputeInputTokenBudget returns the effective soft input-token budget.
//
// Arguments mirror the Python signature:
//
//	configured:      the value read from settings (may be the default).
//	contextLength:   the model's discovered context window. Pass 0 when the
//	                 window is unknown — auto-scaling then stays conservative
//	                 instead of trusting an unproven window (review on #4122).
//	explicit:        true if the user set a NON-default budget. The default
//	                 value is the "auto" sentinel (scale to the window); any
//	                 other value is an explicit cap.
//	opts:            keyword-only arguments (default, headroom, hardMax).
//
// Rules:
//   - Explicit user budget is honoured exactly, only clamped to the model's
//     window when that window is known (the user's deliberate choice wins;
//     hardMax is an auto-budget ceiling only — see #1230).
//   - Otherwise (auto), scale to headroom of the context window, capped at
//     hardMax — so long-context models use their capacity.
//   - When the window is unknown (contextLength <= 0), use the conservative
//     Default and do NOT scale off the fallback.
func ComputeInputTokenBudget(configured, contextLength int, explicit bool, opts Options) int {
	opts = opts.resolve()

	// Go ints are zero-valued automatically when no value is supplied, so the
	// Python ``int(configured or 0)`` coercion collapses to plain arithmetic.

	if explicit && configured > 0 {
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
		capped := scaled
		if capped > opts.HardMax {
			capped = opts.HardMax
		}
		if capped < 1 {
			capped = 1
		}
		return capped
	}

	if configured > 0 {
		return configured
	}
	return opts.Default
}

// BudgetIsExplicit reports whether a configured agent_input_token_budget is a
// deliberate explicit cap.
//
// The default value is the "auto" sentinel (scale to the model's window), so
// only a NON-default positive value counts as explicit. This keys off the
// VALUE, not settings *presence* — the settings-save path materializes every
// default into settings.json, so a persisted default must still read as auto
// (the regression #4121 / #1230 are about). Centralised here so the
// materialized-default contract is unit-testable and can't silently regress to
// a presence check.
func BudgetIsExplicit(configured int, opts Options) bool {
	opts = opts.resolve()
	return configured > 0 && configured != opts.Default
}
