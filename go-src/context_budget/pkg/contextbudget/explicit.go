package contextbudget

// BudgetIsExplicit reports whether a configured
// agent_input_token_budget is a deliberate explicit cap.
//
// The default value is the "auto" sentinel (scale to the model's
// window), so only a NON-default positive value counts as explicit.
// This keys off the VALUE, not settings *presence* — the
// settings-save path materializes every default into settings.json,
// so a persisted default must still read as auto (the regressions
// #4121 / #1230 are about). Centralised here so the
// materialized-default contract is unit-testable and can't silently
// regress to a presence check.
//
// Use Options.WithDefault to override the "what counts as the default"
// sentinel — for example, when the settings layer has applied a
// profile-specific default that is NOT the package constant.
func BudgetIsExplicit(configured int, opts Options) bool {
	if configured < 0 {
		configured = 0
	}
	return configured > 0 && configured != opts.Default
}
