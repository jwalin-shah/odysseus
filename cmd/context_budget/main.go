// Command context_budget is a small CLI for exercising the context_budget
// package. It computes the effective soft input-token budget for the agent
// loop, or checks whether a configured value is a deliberate explicit cap.
//
// Usage:
//
//	context_budget --configured N --context-length N [--explicit] \
//	    [--default N] [--headroom F] [--hard-max N]
//	context_budget --is-explicit N [--default N]
package main

import (
	"flag"
	"fmt"
	"os"
	"strconv"

	"odysseus/context_budget"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "context_budget:", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	fs := flag.NewFlagSet("context_budget", flag.ContinueOnError)
	configured := fs.Int("configured", 0, "configured agent_input_token_budget from settings")
	contextLength := fs.Int("context-length", 0, "discovered model context window (0 = unknown)")
	explicit := fs.Bool("explicit", false, "user set a NON-default budget (see #4121 / #1230)")
	def := fs.Int("default", 0, "override DefaultBudget (keyword arg)")
	headroom := fs.Float64("headroom", 0, "override DefaultHeadroom (keyword arg)")
	hardMax := fs.Int("hard-max", 0, "override DefaultHardMax (keyword arg)")
	isExplicit := fs.Bool("is-explicit", false, "print BudgetIsExplicit(configured) instead of computing")

	if err := fs.Parse(args); err != nil {
		return err
	}

	opts := context_budget.Options{
		Default:  *def,
		Headroom: *headroom,
		HardMax:  *hardMax,
	}

	if *isExplicit {
		// --is-explicit takes its own operand so it can be used without the
		// other flags; the configured flag may have already consumed a value
		// from --configured, so also accept a positional argument as the
		// value to test.
		if fs.NArg() > 0 {
			n, err := strconv.Atoi(fs.Arg(0))
			if err != nil {
				return fmt.Errorf("--is-explicit positional value: %w", err)
			}
			*configured = n
		}
		fmt.Println(context_budget.BudgetIsExplicit(*configured, opts))
		return nil
	}

	budget := context_budget.ComputeInputTokenBudget(*configured, *contextLength, *explicit, opts)
	fmt.Println(budget)
	return nil
}
