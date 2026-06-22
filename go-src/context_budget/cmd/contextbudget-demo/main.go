// Command contextbudget-demo walks several representative scenarios
// through ComputeInputTokenBudget and BudgetIsExplicit and prints one
// line per scenario.
//
// It exercises the branches of the Python source:
//
//  1. Explicit user budget honoured and clamped to the window.
//  2. Auto budget scaling to the window with the default headroom.
//  3. Auto budget hitting the hard-max ceiling on a very long window.
//  4. Unknown window falling back to the conservative default.
//  5. A custom headroom (WithHeadroom) shrinking the auto budget.
//
// Flags:
//
//	--configured <int>        configured value (default 0)
//	--context-length <int>    model context window (default 0)
//	--explicit <bool>         explicit flag (default false)
//	--print-all               print a small matrix of scenarios and exit
//	--help                    show usage and exit
//	--list-tests              print the names of every demo scenario and exit
package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/odysseus/context_budget/pkg/contextbudget"
)

const usage = `contextbudget-demo — exercise the contextbudget package.

USAGE
  contextbudget-demo [options]

OPTIONS
  --configured <int>        configured value read from settings (default 0)
  --context-length <int>    model context window, 0 if unknown (default 0)
  --explicit <bool>         whether the user set a NON-default budget (default false)
  --print-all               print a small matrix of scenarios, then exit
  --help                    show this help and exit
  --list-tests              print the names of every demo scenario, then exit

DESCRIPTION
  Walks the public surface of github.com/odysseus/context_budget/pkg/contextbudget
  and prints one line per scenario. With no flags, runs a single
  ComputeInputTokenBudget call using --configured / --context-length /
  --explicit, then prints a few BudgetIsExplicit probes. With --print-all,
  runs a matrix of (configured, contextLength, explicit) triples.
`

func main() {
	help := flag.Bool("help", false, "show help and exit")
	listTests := flag.Bool("list-tests", false, "print scenario names, then exit")
	printAll := flag.Bool("print-all", false, "print a matrix of scenarios and exit")
	configured := flag.Int("configured", 0, "configured value read from settings")
	contextLength := flag.Int("context-length", 0, "model context window (0 if unknown)")
	explicit := flag.Bool("explicit", false, "explicit flag (true if user set a NON-default budget)")
	flag.Usage = func() { fmt.Fprint(os.Stderr, usage) }
	flag.Parse()

	if *help {
		fmt.Print(usage)
		return
	}
	if *listTests {
		fmt.Println("scenarios:")
		fmt.Println("  single: configured / contextLength / explicit → ComputeInputTokenBudget")
		fmt.Println("  explicit_clamped: 4000 / 128000 / true")
		fmt.Println("  auto_scales_128k:  6000 / 128000 / false")
		fmt.Println("  auto_hits_ceiling: 6000 / 2_000_000 / false")
		fmt.Println("  unknown_window:    0 / 0 / false")
		fmt.Println("  custom_headroom:   0 / 4000 / false (headroom 0.5)")
		fmt.Println("  budget_is_explicit: zero / default / one / just-above / negative")
		fmt.Println("  budget_is_explicit_with_default: match / mismatch / below")
		return
	}

	fmt.Println("== context_budget demo ==")
	fmt.Println()

	if *printAll {
		runPrintAll()
		return
	}

	// Single-call path — run the user's chosen triple and a few
	// BudgetIsExplicit probes alongside it.
	got := contextbudget.ComputeInputTokenBudget(
		contextbudget.DefaultOptions().With(*configured, *contextLength, *explicit),
	)
	fmt.Printf("[single] configured=%d contextLength=%d explicit=%v -> %d\n",
		*configured, *contextLength, *explicit, got)
	fmt.Println()
	fmt.Println("[budget_is_explicit]")
	fmt.Printf("  configured=0     -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(0, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=6000  -> explicit=%v (default = auto sentinel)\n",
		contextbudget.BudgetIsExplicit(contextbudget.DefaultBudget, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=1     -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(1, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=6001  -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(6001, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=-1    -> explicit=%v (defensive coercion)\n",
		contextbudget.BudgetIsExplicit(-1, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=6000 (WithDefault(6000)) -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(6000, contextbudget.DefaultOptions().WithDefault(6000)))
	fmt.Printf("  configured=6000 (WithDefault(5000)) -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(6000, contextbudget.DefaultOptions().WithDefault(5000)))
}

// runPrintAll walks a small matrix of representative scenarios,
// mirroring the branches of the Python source.
func runPrintAll() {
	scenarios := []struct {
		label         string
		configured    int
		contextLength int
		explicit      bool
		opts          []func(contextbudget.Options) contextbudget.Options
	}{
		{
			label:         "explicit user budget clamped to window",
			configured:    4000,
			contextLength: 128_000,
			explicit:      true,
		},
		{
			label:         "auto budget scales to 128k window",
			configured:    6000,
			contextLength: 128_000,
			explicit:      false,
		},
		{
			label:         "auto budget hits hard-max ceiling on 2M window",
			configured:    6000,
			contextLength: 2_000_000,
			explicit:      false,
		},
		{
			label:         "unknown window falls back to default",
			configured:    0,
			contextLength: 0,
			explicit:      false,
		},
		{
			label:         "explicit user budget returned as-is when window unknown",
			configured:    4000,
			contextLength: 0,
			explicit:      true,
		},
		{
			label:         "explicit zero configured falls through to auto",
			configured:    0,
			contextLength: 128_000,
			explicit:      true,
		},
		{
			label:         "custom headroom 0.5 on 4k window",
			configured:    0,
			contextLength: 4000,
			explicit:      false,
			opts:          []func(contextbudget.Options) contextbudget.Options{func(o contextbudget.Options) contextbudget.Options { return o.WithHeadroom(0.5) }},
		},
		{
			label:         "explicit user budget bypasses small hard max",
			configured:    180_000,
			contextLength: 0,
			explicit:      true,
			opts:          []func(contextbudget.Options) contextbudget.Options{func(o contextbudget.Options) contextbudget.Options { return o.WithHardMax(100) }},
		},
	}

	for _, s := range scenarios {
		opts := contextbudget.DefaultOptions().With(s.configured, s.contextLength, s.explicit)
		for _, fn := range s.opts {
			opts = fn(opts)
		}
		got := contextbudget.ComputeInputTokenBudget(opts)
		fmt.Printf("[%s] configured=%d contextLength=%d explicit=%v -> %d\n",
			s.label, s.configured, s.contextLength, s.explicit, got)
	}

	fmt.Println()
	fmt.Println("[budget_is_explicit]")
	fmt.Printf("  configured=0          -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(0, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=6000       -> explicit=%v (default = auto sentinel)\n",
		contextbudget.BudgetIsExplicit(contextbudget.DefaultBudget, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=1          -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(1, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=6001       -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(6001, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=-1         -> explicit=%v (defensive coercion)\n",
		contextbudget.BudgetIsExplicit(-1, contextbudget.DefaultOptions()))
	fmt.Printf("  configured=6000 (WithDefault(6000)) -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(6000, contextbudget.DefaultOptions().WithDefault(6000)))
	fmt.Printf("  configured=6000 (WithDefault(5000)) -> explicit=%v\n",
		contextbudget.BudgetIsExplicit(6000, contextbudget.DefaultOptions().WithDefault(5000)))
}
