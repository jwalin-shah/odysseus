// Command readiness-demo runs a single Check from the readiness
// package and prints the resulting JSON report. It is meant as a
// human-reviewable smoke test for the wave9 port of
// src/readiness.py.
//
// Usage:
//
//	readiness-demo --data-dir /tmp/ready-demo --database-url sqlite:///:memory: --version 0.0.0-demo
//	readiness-demo --help
//	readiness-demo --list-tests
package main

import (
	"context"
	"flag"
	"fmt"
	"os"

	"github.com/odysseus/readiness/pkg/readiness"
)

const usage = `readiness-demo — exercise the readiness package against an
injected Probe.

USAGE
  readiness-demo [options]

OPTIONS
  --help               show this help and exit
  --list-tests         print the names of every demo scenario, then exit
  --data-dir <path>    directory the data_dir check probes (default /tmp)
  --database-url <str> database URL the local_first heuristic inspects
                       (default sqlite:///:memory:)
  --version <str>      version string recorded on the report
                       (default 0.0.0-demo)

DESCRIPTION
  Runs readiness.Check with a stub Probe that always succeeds and
  prints the resulting Report as JSON. The demo CLI is stdlib-only and
  never opens a real database; the local_first detection is purely
  string-based, so any URL string is a valid input.
`

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "readiness-demo:", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	for _, a := range args {
		if a == "-h" || a == "--help" || a == "-help" {
			fmt.Print(usage)
			return nil
		}
		if a == "--list-tests" {
			printScenarios()
			return nil
		}
	}

	fs := flag.NewFlagSet("readiness-demo", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	dataDir := fs.String("data-dir", "/tmp", "Directory the data_dir check probes (created if missing).")
	dbURL := fs.String("database-url", "sqlite:///:memory:", "Database URL for the local_first heuristic.")
	version := fs.String("version", "0.0.0-demo", "Version string recorded on the report.")
	if err := fs.Parse(args); err != nil {
		return err
	}

	probe := readiness.ProbeFunc(func(ctx context.Context) error {
		return nil // stand-in for *sql.DB.PingContext
	})

	rep, err := readiness.Check(context.Background(), readiness.Options{
		DataDir:       *dataDir,
		DatabaseURL:   *dbURL,
		Version:       *version,
		DatabaseProbe: probe,
	})
	if err != nil {
		return err
	}
	fmt.Println(rep.String())
	return nil
}

// printScenarios enumerates every demo scenario the binary knows
// about. --list-tests is a wave9 standing rule so reviewers can scan
// the CLI surface without running it.
func printScenarios() {
	fmt.Println("scenarios:")
	fmt.Println("  --help / -h                       print usage on stdout and exit 0")
	fmt.Println("  --list-tests                      print this list and exit 0")
	fmt.Println("  default (--data-dir /tmp, sqlite  run readiness.Check and print the JSON report")
	fmt.Println("  --database-url postgresql://...   local_first is reported as false")
	fmt.Println("  --database-url ...localhost...    local_first is reported as true")
	fmt.Println("  --data-dir <empty>                data_dir check fails (sentinel error)")
}
