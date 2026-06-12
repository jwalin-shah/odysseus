// ody-router — V3.1 Go port of v2/src/sys_router.py
//
// Same waterfall logic and CLI surface as the Python shim, but as a static
// Go binary. Reads quota state from SYS_QUOTA_STATE (default path matches
// the Python default) and emits a simulated "Routed to <model> successfully"
// line. API passthrough is intentionally out of scope for V3.1; this is the
// pure-router shell that the V3 Phases 2/3 build on.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
)

const defaultQuotaFile = "/Users/jwalinshah/projects/platform/systems/quota-core/data/quota-live.json"

// QuotaState mirrors the JSON shape written by the platform scraper at
// quota-core/data/quota-live.json. Unknown fields are ignored, missing
// fields default to the zero value (Python: .get(key, default)).
type QuotaState struct {
	Providers struct {
		CA struct {
			Quotas struct {
				WeeklyPctRemaining  float64 `json:"weekly_pct_remaining"`
				SessionPctRemaining float64 `json:"session_pct_remaining"`
			} `json:"quotas"`
		} `json:"ca"`
		CB struct {
			Quotas struct {
				WeeklyPctRemaining  float64 `json:"weekly_pct_remaining"`
				SessionPctRemaining float64 `json:"session_pct_remaining"`
			} `json:"quotas"`
		} `json:"cb"`
		Pioneer struct {
			Status  string  `json:"status"`
			UsedPct float64 `json:"used_pct"`
		} `json:"pioneer"`
	} `json:"providers"`
}

// quotaPath returns the JSON path the router should consult for live quota.
// Matches Python: Path(os.environ.get("SYS_QUOTA_STATE", DEFAULT_QUOTA_FILE)).
func quotaPath() string {
	if p := os.Getenv("SYS_QUOTA_STATE"); p != "" {
		return p
	}
	return defaultQuotaFile
}

// getBestModel implements the same waterfall as sys_router.py:get_best_model.
// On any read/parse failure it falls back to "codex" (free compute), matching
// the Python's warning-and-fallback behavior.
func getBestModel() string {
	// Best-effort ody-quota pre-flight; Python's try/except.
	_ = exec.Command("ody-quota", "check").Run()

	path := quotaPath()
	data, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Warning: %s not found. Falling back to free compute.\n", path)
		return "codex"
	}
	var qs QuotaState
	if err := json.Unmarshal(data, &qs); err != nil {
		fmt.Fprintf(os.Stderr, "Warning: Failed to parse %s. Falling back to free compute.\n", path)
		return "codex"
	}

	// Priority 1: Claude-A (Premium) — both weekly and session > 10.
	if qs.Providers.CA.Quotas.WeeklyPctRemaining > 10 &&
		qs.Providers.CA.Quotas.SessionPctRemaining > 10 {
		return "claude-a"
	}

	// Priority 2: Claude-B (Premium) — same thresholds.
	if qs.Providers.CB.Quotas.WeeklyPctRemaining > 10 &&
		qs.Providers.CB.Quotas.SessionPctRemaining > 10 {
		return "claude-b"
	}

	// Priority 3: Pioneer (Pro Legacy) — VERIFIED + used_pct < 90.
	if qs.Providers.Pioneer.Status == "VERIFIED" && qs.Providers.Pioneer.UsedPct < 90 {
		return "pioneer"
	}

	// Fallback: Free Compute (Codex).
	return "codex"
}

// parseFlags is a minimal stdlib-only flag parser. We only need --model <value>,
// matching the Python shim's argparse contract.
func parseFlags(args []string) string {
	model := "auto"
	for i := 0; i < len(args); i++ {
		if args[i] == "--model" && i+1 < len(args) {
			model = args[i+1]
			i++
			continue
		}
	}
	return model
}

func main() {
	model := parseFlags(os.Args[1:])

	// Drain stdin — the Python shim reads the prompt; we accept it but in
	// V3.1 (simulated) we don't echo it back. API passthrough is later.
	_, _ = io.ReadAll(os.Stdin)

	selected := model
	if selected == "auto" {
		selected = getBestModel()
	}

	// Mock routing for testing — matches sys_router.py:67-69.
	if selected == "dummy-mock" {
		fmt.Println("Mock MiniMax Response")
		return
	}

	// Exhausted model — exit 75 matches sys_router.py:71-73.
	if selected == "exhausted-model" {
		fmt.Fprintln(os.Stderr, "QUOTA EXHAUSTED: model exhausted")
		os.Exit(75)
	}

	// For every other model in V3.1 we emit the simulated-execution line,
	// matching sys_router.py:106-108 ("Real endpoint not configured yet").
	fmt.Printf("Routed to %s successfully (simulation).\n", selected)
}
