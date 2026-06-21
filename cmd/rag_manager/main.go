// Command rag_manager is a CLI front-end for the rag_manager Go package.
//
// It exercises the Manager against the bundled stub VectorRAG, prints the
// configured persist directory, calls GetStats, reads file paths from
// stdin (one per line) and indexes each one, then prints the final stats.
//
// This binary exists for parity with the Python rag_manager.py module
// while the real VectorRAG implementation has not yet been ported.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"

	"odysseus/rag_manager"
)

func main() {
	if err := run(os.Args[1:], os.Stdin, os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, "rag_manager:", err)
		os.Exit(1)
	}
}

func run(args []string, stdin io.Reader, stdout io.Writer) error {
	persistDir := "./chroma"
	for _, a := range args {
		if a == "--persist-dir" {
			// flag-only; the actual directory comes from the next arg.
			continue
		}
		if strings.HasPrefix(a, "--persist-dir=") {
			persistDir = strings.TrimPrefix(a, "--persist-dir=")
		} else if persistDir == "./chroma" && a != "" {
			persistDir = a
		}
	}

	fmt.Fprintf(stdout, "persist_directory: %s\n", persistDir)

	mgr := rag_manager.NewDefault(persistDir)
	ctx := context.Background()

	initial := mgr.GetStats()
	if err := printJSON(stdout, "initial_stats", initial); err != nil {
		return err
	}

	scanner := bufio.NewScanner(stdin)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		if _, err := mgr.IndexPersonalDocuments(ctx, line, nil, ""); err != nil {
			return fmt.Errorf("index %q: %w", line, err)
		}
	}
	if err := scanner.Err(); err != nil {
		return fmt.Errorf("read stdin: %w", err)
	}

	final := mgr.GetStats()
	return printJSON(stdout, "final_stats", final)
}

func printJSON(w io.Writer, label string, v any) error {
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	if _, err := fmt.Fprintf(w, "%s: ", label); err != nil {
		return err
	}
	if err := enc.Encode(v); err != nil {
		return err
	}
	return nil
}
