// Package contextbudget is the Go port of src/context_budget.py.
//
// The Python module exposes two pure functions used by the agent loop
// to derive the effective input-token budget from the configured
// settings and the model's discovered context window:
//
//	compute_input_token_budget(configured, context_length, explicit,
//	                           *, default=..., headroom=..., hard_max=...)
//	budget_is_explicit(configured, *, default=...)
//
// The Go port keeps the same contracts. The first three arguments
// (configured, contextLength, explicit) are passed positionally and
// the optional tuning parameters are passed via a small Options
// struct, populated by the DefaultOptions constructor and overridden
// per-call via a fluent With* API:
//
//	budget := contextbudget.ComputeInputTokenBudget(
//	    contextbudget.DefaultOptions().With(4000, 128000, true),
//	)
//
//	budget := contextbudget.ComputeInputTokenBudget(
//	    contextbudget.DefaultOptions().
//	        With(0, 128000, false).
//	        WithHeadroom(0.5).
//	        WithHardMax(100_000),
//	)
//
// Semantics preserved exactly:
//
//   - If `explicit && configured > 0`, the explicit value wins. It is
//     clamped to the model's window when the window is known, otherwise
//     returned as-is. `HardMax` does NOT cap an explicit user choice
//     (only auto-budgets are hard-capped — see Python docstring #1230).
//
//   - Else, when the window is known (`contextLength > 0`), the budget
//     is `int(contextLength * headroom)`, clamped to `[1, HardMax]`.
//
//   - Else (unknown window), the conservative `configured` (if > 0)
//     is used, falling back to `Default`.
//
// `BudgetIsExplicit` keys off the VALUE, not settings presence: a
// positive value different from the (possibly overridden) default is
// explicit. This keeps the materialized-default contract from #4121 /
// #1230 unit-testable.
package contextbudget

// Default constants, exported so callers can introspect or seed
// settings with the canonical defaults. They match the Python
// `DEFAULT_HARD_MAX`, `DEFAULT_BUDGET`, `DEFAULT_HEADROOM`.
const (
	// DefaultHardMax is the ceiling applied to AUTO budgets only.
	// Explicit user values are honoured up to the model's window
	// (never against DefaultHardMax — that is intentional).
	DefaultHardMax = 200_000

	// DefaultBudget is the conservative fallback used when both
	// the explicit flag is false and the model's window is unknown.
	// A user choosing exactly this value still reads as auto (the
	// default value is the "scale to the window" sentinel).
	DefaultBudget = 6000

	// DefaultHeadroom is the fraction of the model's window that an
	// auto-budget is allowed to fill. Expected range: (0, 1]; the
	// computation does not range-check.
	DefaultHeadroom = 0.85
)

// Options bundles the resolved tuning values for
// ComputeInputTokenBudget / BudgetIsExplicit. The zero value is NOT
// usable — populate via DefaultOptions so all fields are sensible.
// Each With* method mutates a copy and returns it (Go-idiomatic fluent
// style), keeping call sites readable without losing immutability of
// the default singleton.
type Options struct {
	// Configured is the value read from settings (may be the default).
	Configured int
	// ContextLength is the model's discovered context window. Pass 0
	// when the window is unknown / only a bare fallback — auto-scaling
	// then stays conservative instead of trusting an unproven window
	// (review on #4122).
	ContextLength int
	// Explicit is true if the user set a NON-default budget. The
	// default value is the "auto" sentinel; any other value is an
	// explicit cap.
	Explicit bool
	// Default is the conservative fallback used when both the explicit
	// flag is false and the model's window is unknown. Defaults to
	// DefaultBudget.
	Default int
	// Headroom is the fraction of the model's window that an auto-budget
	// is allowed to fill. Defaults to DefaultHeadroom.
	Headroom float64
	// HardMax is the ceiling applied to AUTO budgets only. Defaults
	// to DefaultHardMax.
	HardMax int
}

// DefaultOptions returns an Options struct populated with every
// package default. This is the recommended starting point for both
// ComputeInputTokenBudget and BudgetIsExplicit — pass the zero value
// only if you genuinely want every field at zero.
func DefaultOptions() Options {
	return Options{
		Configured:    0,
		ContextLength: 0,
		Explicit:      false,
		Default:       DefaultBudget,
		Headroom:      DefaultHeadroom,
		HardMax:       DefaultHardMax,
	}
}

// With returns a copy of o with the three positional fields replaced.
// Use this to bind configured / contextLength / explicit before
// chaining optional overrides:
//
//	contextbudget.ComputeInputTokenBudget(
//	    contextbudget.DefaultOptions().With(4000, 128000, true),
//	)
func (o Options) With(configured, contextLength int, explicit bool) Options {
	o.Configured = configured
	o.ContextLength = contextLength
	o.Explicit = explicit
	return o
}

// WithDefault overrides Default for this call only. Returns a copy.
func (o Options) WithDefault(d int) Options {
	o.Default = d
	return o
}

// WithHeadroom overrides DefaultHeadroom for this call only. Caller
// is responsible for passing a sane (0, 1] value; the function does
// not range-check. Returns a copy.
func (o Options) WithHeadroom(h float64) Options {
	o.Headroom = h
	return o
}

// WithHardMax overrides DefaultHardMax for this call only. Returns a copy.
func (o Options) WithHardMax(m int) Options {
	o.HardMax = m
	return o
}
