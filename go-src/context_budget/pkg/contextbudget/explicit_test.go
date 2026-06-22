package contextbudget

import "testing"

// ---- BudgetIsExplicit ---------------------------------------------------

func TestBudgetIsExplicit_Zero(t *testing.T) {
	// 0 → false. The bare zero is the materialized-default sentinel
	// for "not set" — also explicit if we treat zero as non-default.
	// The contract is: zero reads as auto.
	if BudgetIsExplicit(0, DefaultOptions()) {
		t.Errorf("BudgetIsExplicit(0) = true, want false")
	}
}

func TestBudgetIsExplicit_DefaultValueIsAuto(t *testing.T) {
	// configured == DefaultBudget (6000) is the materialized-default
	// sentinel and must read as auto. This is the regression #4121 —
	// a persisted default must still read as auto.
	if BudgetIsExplicit(DefaultBudget, DefaultOptions()) {
		t.Errorf("BudgetIsExplicit(%d) = true, want false", DefaultBudget)
	}
}

func TestBudgetIsExplicit_OneIsExplicit(t *testing.T) {
	// Any positive value different from the default is explicit,
	// even when very small.
	if !BudgetIsExplicit(1, DefaultOptions()) {
		t.Errorf("BudgetIsExplicit(1) = false, want true")
	}
}

func TestBudgetIsExplicit_JustAboveDefaultIsExplicit(t *testing.T) {
	// 6001 — one above the default — must read as explicit.
	if !BudgetIsExplicit(6001, DefaultOptions()) {
		t.Errorf("BudgetIsExplicit(6001) = false, want true")
	}
}

func TestBudgetIsExplicit_CustomDefault_MaterializedDefaultStillAuto(t *testing.T) {
	// WithDefault(6000), configured=6000 → still auto because the
	// value matches the active sentinel.
	if BudgetIsExplicit(6000, DefaultOptions().WithDefault(6000)) {
		t.Errorf("BudgetIsExplicit(6000, WithDefault(6000)) = true, want false")
	}
}

func TestBudgetIsExplicit_CustomDefault_AnyOtherValueIsExplicit(t *testing.T) {
	// WithDefault(5000), configured=6000 → explicit because 6000
	// is no longer the sentinel.
	if !BudgetIsExplicit(6000, DefaultOptions().WithDefault(5000)) {
		t.Errorf("BudgetIsExplicit(6000, WithDefault(5000)) = false, want true")
	}
}

func TestBudgetIsExplicit_NegativeIsNotExplicit(t *testing.T) {
	// Negative inputs are normalized to zero (mirrors Python's
	// `int(configured or 0)`), so they read as auto.
	if BudgetIsExplicit(-10, DefaultOptions()) {
		t.Errorf("BudgetIsExplicit(-10) = true, want false")
	}
}

func TestBudgetIsExplicit_NegativeOneIsNotExplicit(t *testing.T) {
	// -1 specifically — defensive coercion.
	if BudgetIsExplicit(-1, DefaultOptions()) {
		t.Errorf("BudgetIsExplicit(-1) = true, want false")
	}
}

// ---- Table-driven sweep covering the rules end-to-end -------------------

func TestBudgetIsExplicit_TableDriven(t *testing.T) {
	cases := []struct {
		name       string
		configured int
		opts       Options
		want       bool
	}{
		{
			name:       "zero_is_auto",
			configured: 0,
			opts:       DefaultOptions(),
			want:       false,
		},
		{
			name:       "default_value_is_auto",
			configured: DefaultBudget,
			opts:       DefaultOptions(),
			want:       false,
		},
		{
			name:       "one_is_explicit",
			configured: 1,
			opts:       DefaultOptions(),
			want:       true,
		},
		{
			name:       "just_above_default_is_explicit",
			configured: DefaultBudget + 1,
			opts:       DefaultOptions(),
			want:       true,
		},
		{
			name:       "way_above_default_is_explicit",
			configured: 100_000,
			opts:       DefaultOptions(),
			want:       true,
		},
		{
			name:       "negative_normalised_to_auto",
			configured: -1,
			opts:       DefaultOptions(),
			want:       false,
		},
		{
			name:       "very_negative_normalised_to_auto",
			configured: -9999,
			opts:       DefaultOptions(),
			want:       false,
		},
		{
			name:       "custom_default_match_is_auto",
			configured: 6000,
			opts:       DefaultOptions().WithDefault(6000),
			want:       false,
		},
		{
			name:       "custom_default_mismatch_is_explicit",
			configured: 6000,
			opts:       DefaultOptions().WithDefault(5000),
			want:       true,
		},
		{
			name:       "value_below_custom_default_is_explicit",
			configured: 4000,
			opts:       DefaultOptions().WithDefault(5000),
			want:       true,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := BudgetIsExplicit(tc.configured, tc.opts)
			if got != tc.want {
				t.Errorf("BudgetIsExplicit(%d, %+v) = %v, want %v",
					tc.configured, tc.opts, got, tc.want)
			}
		})
	}
}
