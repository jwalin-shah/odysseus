// Command tls_overrides is a small CLI that prints the effective
// LLM-provider trust override state. It is the Go analogue of the
// "operator can sanity-check LLM_CA_BUNDLE without booting FastAPI"
// intent behind src/tls_overrides.py.
//
// Output:
//
//   - LLM_CA_BUNDLE unset / blank           → "no extension (using system default)"
//   - LLM_CA_BUNDLE points at a valid PEM   → "loaded: <path>"
//   - LLM_CA_BUNDLE points at a bad PEM     → "no extension (using system default): <reason>"
//     and exits non-zero so CI can detect the misconfiguration.
package main

import (
	"fmt"
	"os"

	"odysseus/tls_overrides"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "tls_overrides:", err)
		os.Exit(1)
	}
}

func run() error {
	// The env var is read once via the package-level cache; we use
	// Build directly so the operator sees the same path resolution the
	// production HTTP client uses.
	bundlePath, ok := os.LookupEnv(tls_overrides.EnvCABundle)
	if !ok || bundlePath == "" {
		fmt.Println("no extension (using system default)")
		return nil
	}

	cfg, err := tls_overrides.Build(bundlePath)
	if err != nil {
		// Build returns a usable default config even on error, but the
		// operator explicitly pointed at something broken. Surface it
		// and exit non-zero so this can be wired into health checks.
		fmt.Printf("no extension (using system default): %v\n", err)
		return err
	}
	if cfg.RootCAs == nil {
		fmt.Println("no extension (using system default)")
		return nil
	}
	fmt.Printf("loaded: %s\n", bundlePath)
	return nil
}
