// Command reminder_personas prints the system prompt that would be sent
// to the model for a given reminder-synthesis persona id. It exists so
// operators can sanity-check the voice the synthesis route will use
// without booting the FastAPI server.
//
// Usage:
//
//	reminder_personas                       # uses "socrates"
//	reminder_personas <persona_id>          # print the resulting prompt
//	reminder_personas --list                # print all known persona IDs
//
// Unknown ids fall back to reminder_personas.DefaultSynthesisTone to
// match Python semantics; the CLI always exits 0 unless it is invoked
// with a malformed arg list (e.g. more than one positional argument).
package main

import (
	"fmt"
	"os"
	"sort"

	"odysseus/reminder_personas"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "reminder_personas:", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	// --list must come first and cannot be combined with a positional
	// argument; that mirrors the rest of the cmd/* CLI surface.
	if len(args) == 1 && args[0] == "--list" {
		return listPersonas()
	}
	if len(args) > 1 {
		return fmt.Errorf("expected at most one persona id argument, got %d", len(args))
	}
	id := "socrates"
	if len(args) == 1 {
		id = args[0]
	}
	fmt.Println(reminder_personas.SynthesisSystemPrompt(id))
	return nil
}

func listPersonas() error {
	// Go map iteration is randomized; sort so the CLI output is
	// deterministic for scripts and human eyeballs.
	ids := make([]string, 0, len(reminder_personas.Personas))
	for id := range reminder_personas.Personas {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		fmt.Println(id)
	}
	return nil
}
