package context_budget

import "testing"

func TestComputeInputTokenBudget_ExplicitBranch(t *testing.T) {
	// Explicit + window: configured wins when smaller; window wins when smaller.
	cases := []struct {
		name       string
		configured int
		ctx        int
		want       int
	}{
		{"explicit smaller than window", 1000, 2000, 1000},
		{"explicit larger than window clamps to window", 5000, 2000, 2000},
		{"explicit without window keeps configured", 1000, 0, 1000},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := ComputeInputTokenBudget(tc.configured, tc.ctx, true, Options{})
			if got != tc.want {
				t.Errorf("got %d, want %d", got, tc.want)
			}
		})
	}
}

func TestComputeInputTokenBudget_ExplicitIgnoresHardMax(t *testing.T) {
	// hard_max does NOT apply to an explicit user budget — see #1230.
	got := ComputeInputTokenBudget(50, 10000, true, Options{HardMax: 100})
	if got != 50 {
		t.Errorf("explicit budget should ignore hard_max: got %d, want 50", got)
	}
}

func TestComputeInputTokenBudget_ExplicitZeroFallsThrough(t *testing.T) {
	// explicit=true with configured=0 must NOT take the explicit branch — the
	// Python `if explicit and configured > 0` short-circuits here, so a
	// mis-typed zero is treated as auto.
	got := ComputeInputTokenBudget(0, 100000, true, Options{})
	want := ComputeInputTokenBudget(0, 100000, false, Options{})
	if got != want {
		t.Errorf("explicit+configured=0 should match auto: got %d, want %d", got, want)
	}
}

func TestComputeInputTokenBudget_AutoKnownWindow(t *testing.T) {
	cases := []struct {
		name string
		ctx  int
		opts Options
		want int
	}{
		{"100K @ default headroom", 100_000, Options{}, 85_000},
		{"200K @ default headroom", 200_000, Options{}, 170_000},
		{"300K capped at default hard_max", 300_000, Options{}, 200_000},
		{"300K capped at custom hard_max", 300_000, Options{HardMax: 200_000}, 200_000},
		{"ctx=1 floored to 1 (was 0.85)", 1, Options{}, 1},
		{"ctx=10 keeps 8", 10, Options{}, 8},
		{"custom headroom 0.5 on 100K", 100_000, Options{Headroom: 0.5}, 50_000},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := ComputeInputTokenBudget(0, tc.ctx, false, tc.opts)
			if got != tc.want {
				t.Errorf("got %d, want %d", got, tc.want)
			}
		})
	}
}

func TestComputeInputTokenBudget_AutoUnknownWindow(t *testing.T) {
	cases := []struct {
		name       string
		configured int
		opts       Options
		want       int
	}{
		{"zero configured falls back to default", 0, Options{}, DefaultBudget},
		{"custom default applied", 0, Options{Default: 1234}, 1234},
		{"non-zero configured overrides default", 3000, Options{}, 3000},
		{"non-zero configured overrides custom default", 3000, Options{Default: 1234}, 3000},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := ComputeInputTokenBudget(tc.configured, 0, false, tc.opts)
			if got != tc.want {
				t.Errorf("got %d, want %d", got, tc.want)
			}
		})
	}
}

func TestBudgetIsExplicit(t *testing.T) {
	cases := []struct {
		name string
		in   int
		want bool
	}{
		{"zero is not explicit", 0, false},
		{"negative is not explicit", -5, false},
		{"exact default is NOT explicit (#4121)", DefaultBudget, false},
		{"default+1 is explicit", DefaultBudget + 1, true},
		{"1 is explicit", 1, true},
		{"large value is explicit", 200_000, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := BudgetIsExplicit(tc.in, Options{})
			if got != tc.want {
				t.Errorf("BudgetIsExplicit(%d) = %v, want %v", tc.in, got, tc.want)
			}
		})
	}
}

func TestBudgetIsExplicit_CustomDefault(t *testing.T) {
	// When the caller overrides the default sentinel, the explicit check must
	// key off the override.
	if BudgetIsExplicit(100, Options{Default: 200}) != true {
		t.Error("100 should be explicit when default is 200")
	}
	if BudgetIsExplicit(200, Options{Default: 200}) != false {
		t.Error("200 should NOT be explicit when default is 200")
	}
}

func TestComputeInputTokenBudget_ZeroIsAuto(t *testing.T) {
	// Coercion note: Go int zero-values cannot carry nil, so the test is that
	// the zero value behaves the same as the Python ``int(configured or 0)``
	// coercion — a configured=0 is auto.
	got := ComputeInputTokenBudget(0, 100_000, false, Options{})
	want := 85_000
	if got != want {
		t.Errorf("zero configured should auto-scale: got %d, want %d", got, want)
	}
}

func TestOptionsResolve_FillsZeroValues(t *testing.T) {
	got := Options{}.resolve()
	if got.Default != DefaultBudget {
		t.Errorf("Default = %d, want %d", got.Default, DefaultBudget)
	}
	if got.Headroom != DefaultHeadroom {
		t.Errorf("Headroom = %v, want %v", got.Headroom, DefaultHeadroom)
	}
	if got.HardMax != DefaultHardMax {
		t.Errorf("HardMax = %d, want %d", got.HardMax, DefaultHardMax)
	}
}

func TestOptionsResolve_PreservesNonZero(t *testing.T) {
	got := Options{Default: 100, Headroom: 0.25, HardMax: 50}.resolve()
	if got.Default != 100 || got.Headroom != 0.25 || got.HardMax != 50 {
		t.Errorf("resolve overrode non-zero fields: %+v", got)
	}
}
