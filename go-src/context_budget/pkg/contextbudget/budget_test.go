package contextbudget

import "testing"

// ---- ComputeInputTokenBudget ---------------------------------------------

func TestComputeInputTokenBudget_Explicit_ClampsToWindow(t *testing.T) {
	// explicit=true, configured=4000, contextLength=128000 → 4000.
	// The explicit choice is honoured and clamped to contextLength
	// (which is larger, so configured wins).
	got := ComputeInputTokenBudget(DefaultOptions().With(4000, 128000, true))
	if got != 4000 {
		t.Errorf("explicit+clamp = %d, want 4000", got)
	}
}

func TestComputeInputTokenBudget_Explicit_NoWindow(t *testing.T) {
	// explicit=true, configured=4000, contextLength=0 → 4000.
	// Window unknown: explicit value is returned as-is, no clamp.
	got := ComputeInputTokenBudget(DefaultOptions().With(4000, 0, true))
	if got != 4000 {
		t.Errorf("explicit+nowindow = %d, want 4000", got)
	}
}

func TestComputeInputTokenBudget_Explicit_ClampedBelowWindow(t *testing.T) {
	// explicit=true, configured=50_000, contextLength=8000 → 8000
	// (the configured value is larger than the window; window wins).
	got := ComputeInputTokenBudget(DefaultOptions().With(50_000, 8000, true))
	if got != 8000 {
		t.Errorf("explicit+clamp-above = %d, want 8000", got)
	}
}

func TestComputeInputTokenBudget_Explicit_NoClampHardMax(t *testing.T) {
	// explicit=true, configured=180_000, contextLength=0, HardMax=100 → 180_000.
	// Explicit values are NOT capped at HardMax — that ceiling is
	// only for auto-budgets.
	got := ComputeInputTokenBudget(
		DefaultOptions().With(180_000, 0, true).WithHardMax(100),
	)
	if got != 180_000 {
		t.Errorf("explicit+bypass-hardmax = %d, want 180000", got)
	}
}

func TestComputeInputTokenBudget_Explicit_ZeroConfiguredFallsThrough(t *testing.T) {
	// explicit=true, configured=0, contextLength=128000 → 108800.
	// When configured is zero, even with explicit=true we fall through
	// to the auto-scaling branch (configured is the gate).
	got := ComputeInputTokenBudget(DefaultOptions().With(0, 128000, true))
	if got != 108800 {
		t.Errorf("explicit+0-configured = %d, want 108800", got)
	}
}

func TestComputeInputTokenBudget_Auto_ScalesToWindow(t *testing.T) {
	// explicit=false, configured=6000, contextLength=128000 → 108800.
	// int(128000 * 0.85) = 108800, well under the 200k hard max.
	got := ComputeInputTokenBudget(DefaultOptions().With(6000, 128000, false))
	if got != 108800 {
		t.Errorf("auto+128k = %d, want 108800", got)
	}
}

func TestComputeInputTokenBudget_Auto_HardCap(t *testing.T) {
	// explicit=false, configured=6000, contextLength=2_000_000 → 200000.
	// int(2M * 0.85) = 1_700_000, capped at the 200k hard max.
	got := ComputeInputTokenBudget(DefaultOptions().With(6000, 2_000_000, false))
	if got != 200_000 {
		t.Errorf("auto+2M = %d, want 200000", got)
	}
}

func TestComputeInputTokenBudget_Auto_ZeroConfigured(t *testing.T) {
	// explicit=false, configured=0, contextLength=128000 → 108800.
	// configured==0 still triggers the auto-scaling branch.
	got := ComputeInputTokenBudget(DefaultOptions().With(0, 128000, false))
	if got != 108800 {
		t.Errorf("auto+0-configured = %d, want 108800", got)
	}
}

func TestComputeInputTokenBudget_Auto_NoWindow_FallsBackToDefault(t *testing.T) {
	// explicit=false, configured=0, contextLength=0 → 6000.
	// Window unknown, configured is zero → use the package default.
	got := ComputeInputTokenBudget(DefaultOptions().With(0, 0, false))
	if got != 6000 {
		t.Errorf("auto+nowindow+0-configured = %d, want 6000", got)
	}
}

func TestComputeInputTokenBudget_Auto_NoWindow_ConfiguredWinsOverDefault(t *testing.T) {
	// explicit=false, configured=6000, contextLength=0 → 6000.
	// Window unknown but configured is positive → use configured.
	got := ComputeInputTokenBudget(DefaultOptions().With(6000, 0, false))
	if got != 6000 {
		t.Errorf("auto+nowindow+configured = %d, want 6000", got)
	}
}

func TestComputeInputTokenBudget_Auto_ScaleFloorIsOne(t *testing.T) {
	// explicit=false, configured=0, contextLength=1 → 1.
	// The floor of 1 must hold even when the natural scale < 1.
	got := ComputeInputTokenBudget(DefaultOptions().With(0, 1, false))
	if got != 1 {
		t.Errorf("auto+floor-1 = %d, want 1", got)
	}
}

func TestComputeInputTokenBudget_NegativeConfiguredTreatedAsZero(t *testing.T) {
	// explicit=true, configured=-5, contextLength=128000 → 108800.
	// Negative configured is normalised to 0 (mirrors `int(x or 0)`),
	// which falls through to the auto-scaling branch.
	got := ComputeInputTokenBudget(DefaultOptions().With(-5, 128000, true))
	if got != 108800 {
		t.Errorf("negative-configured = %d, want 108800", got)
	}
}

func TestComputeInputTokenBudget_NegativeContextLengthTreatedAsZero(t *testing.T) {
	// explicit=false, configured=6000, contextLength=-128000 → 6000.
	// Negative context_length is normalised to 0, so we use configured.
	got := ComputeInputTokenBudget(DefaultOptions().With(6000, -128000, false))
	if got != 6000 {
		t.Errorf("negative-context-length = %d, want 6000", got)
	}
}

func TestComputeInputTokenBudget_BothNegativeFallBackToDefault(t *testing.T) {
	// explicit=false, configured=-1, contextLength=-1 → 6000.
	// Both negative; falls back to default.
	got := ComputeInputTokenBudget(DefaultOptions().With(-1, -1, false))
	if got != 6000 {
		t.Errorf("both-negative = %d, want 6000", got)
	}
}

func TestComputeInputTokenBudget_WithDefault_OverriddenByConfigured(t *testing.T) {
	// WithDefault(100), explicit=false, configured=100, contextLength=0 → 100.
	// When the window is unknown and configured > 0, configured
	// overrides the WithDefault sentinel.
	got := ComputeInputTokenBudget(
		DefaultOptions().With(100, 0, false).WithDefault(100),
	)
	if got != 100 {
		t.Errorf("withdefault+100 = %d, want 100", got)
	}
}

func TestComputeInputTokenBudget_WithHeadroom(t *testing.T) {
	// WithHeadroom(0.5), explicit=false, configured=0, contextLength=1000 → 500.
	// Custom headroom drives the auto-scale.
	got := ComputeInputTokenBudget(
		DefaultOptions().With(0, 1000, false).WithHeadroom(0.5),
	)
	if got != 500 {
		t.Errorf("withheadroom = %d, want 500", got)
	}
}

func TestComputeInputTokenBudget_WithHardMax(t *testing.T) {
	// WithHardMax(100), explicit=false, configured=0, contextLength=10000 → 100.
	// Custom hard max caps the auto-budget below its natural scale.
	got := ComputeInputTokenBudget(
		DefaultOptions().With(0, 10_000, false).WithHardMax(100),
	)
	if got != 100 {
		t.Errorf("withhardmax = %d, want 100", got)
	}
}

// ---- Table-driven sweep covering the rules end-to-end -------------------

func TestComputeInputTokenBudget_TableDriven(t *testing.T) {
	cases := []struct {
		name string
		opts Options
		want int
	}{
		{
			name: "explicit_honoured_below_window",
			opts: DefaultOptions().With(4000, 128_000, true),
			want: 4000,
		},
		{
			name: "explicit_honoured_no_window",
			opts: DefaultOptions().With(4000, 0, true),
			want: 4000,
		},
		{
			name: "explicit_clamped_above_window",
			opts: DefaultOptions().With(180_000, 8000, true),
			want: 8000,
		},
		{
			name: "explicit_zero_configured_falls_through_to_auto",
			opts: DefaultOptions().With(0, 128_000, true),
			want: 108_800,
		},
		{
			name: "auto_scales_128k",
			opts: DefaultOptions().With(6000, 128_000, false),
			want: 108_800,
		},
		{
			name: "auto_hard_cap_2M",
			opts: DefaultOptions().With(6000, 2_000_000, false),
			want: 200_000,
		},
		{
			name: "auto_zero_configured",
			opts: DefaultOptions().With(0, 128_000, false),
			want: 108_800,
		},
		{
			name: "auto_fallback_default",
			opts: DefaultOptions().With(0, 0, false),
			want: 6000,
		},
		{
			name: "auto_fallback_configured",
			opts: DefaultOptions().With(6000, 0, false),
			want: 6000,
		},
		{
			name: "auto_floor_is_one",
			opts: DefaultOptions().With(0, 1, false),
			want: 1,
		},
		{
			name: "negative_configured_normalised_to_zero",
			opts: DefaultOptions().With(-100, 128_000, true),
			want: 108_800,
		},
		{
			name: "negative_context_length_normalised_to_zero",
			opts: DefaultOptions().With(6000, -128_000, false),
			want: 6000,
		},
		{
			name: "both_negative_falls_back_to_default",
			opts: DefaultOptions().With(-1, -1, false),
			want: 6000,
		},
		{
			name: "with_default_overridden_by_configured",
			opts: DefaultOptions().With(100, 0, false).WithDefault(100),
			want: 100,
		},
		{
			name: "with_headroom_half",
			opts: DefaultOptions().With(0, 1000, false).WithHeadroom(0.5),
			want: 500,
		},
		{
			name: "with_hard_max_caps_auto",
			opts: DefaultOptions().With(0, 10_000, false).WithHardMax(100),
			want: 100,
		},
		{
			name: "explicit_bypasses_hard_max",
			opts: DefaultOptions().With(180_000, 0, true).WithHardMax(100),
			want: 180_000,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := ComputeInputTokenBudget(tc.opts)
			if got != tc.want {
				t.Errorf("ComputeInputTokenBudget(%+v) = %d, want %d", tc.opts, got, tc.want)
			}
		})
	}
}
