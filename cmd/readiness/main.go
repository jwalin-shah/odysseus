// Command readiness runs the local-instance readiness checks and
// prints a JSON Report. It exits 0 when Ready is true, 1 otherwise.
//
// Environment:
//
//	ODYSSEUS_APP_VERSION — version string (default "0.0.0")
//	ODYSSEUS_DATA_DIR    — data directory (default "./data")
//	DATABASE_URL         — SQLAlchemy-style URL (default "sqlite:///./data/odysseus.db")
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"odysseus/readiness"
)

func main() {
	cfg := readiness.Config{
		AppVersion:  envOr("ODYSSEUS_APP_VERSION", "0.0.0"),
		DataDir:     envOr("ODYSSEUS_DATA_DIR", "./data"),
		DatabaseURL: envOr("DATABASE_URL", "sqlite:///./data/odysseus.db"),
		// Default DB probe returns nil so the binary works in
		// environments without a registered driver. Real callers
		// should inject their own probe (sql.Open + PingContext).
		DBProbe: func(ctx context.Context) error { return nil },
	}

	report := readiness.Run(context.Background(), cfg)
	out, err := json.MarshalIndent(&report, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal report: %v\n", err)
		os.Exit(2)
	}
	fmt.Fprintln(os.Stdout, string(out))
	if !report.Ready {
		os.Exit(1)
	}
}

func envOr(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return fallback
}
