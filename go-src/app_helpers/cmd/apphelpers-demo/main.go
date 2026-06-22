// Command apphelpers-demo demonstrates the wiring of the apphelpers
// package. It exercises the four public helpers against a tempdir:
//
//   - ReadIfExists: write a file, read it back; then probe a missing path.
//   - FileToDataURL: encode a small payload and print the data URL.
//   - AbsJoin: join a sub-path under a known base.
//   - InsideBaseDir: confirm a nested path is inside, and a sibling is not.
//
// All scenarios are printed as one-line summaries so a human reviewer can
// eyeball each helper without writing a test program.
package main

import (
	"fmt"
	"os"
	"path/filepath"

	contextah "github.com/odysseus/app_helpers/pkg/apphelpers"
)

func main() {
	fmt.Println("== apphelpers demo ==")
	fmt.Println()

	base := filepath.Join(os.TempDir(), fmt.Sprintf("apphelpers-%d", os.Getpid()))
	sub := filepath.Join(base, "sub")
	if err := os.Mkdir(sub, 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(2)
	}

	// 1. ReadIfExists: write + read.
	payload := filepath.Join(base, "notes.txt")
	if err := os.WriteFile(payload, []byte("  hello world\n"), 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(2)
	}
	got := contextah.ReadIfExists(payload)
	fmt.Printf("[read_if_exists]\n  %s -> %q\n", payload, got)
	missing := filepath.Join(base, "nope.txt")
	fmt.Printf("  %s -> %q\n", missing, contextah.ReadIfExists(missing))
	fmt.Println()

	// 2. FileToDataURL.
	dataURL, err := contextah.FileToDataURL(payload, "text/plain")
	if err != nil {
		fmt.Fprintf(os.Stderr, "file_to_data_url: %v\n", err)
		os.Exit(2)
	}
	fmt.Printf("[file_to_data_url]\n  %s\n  -> %q\n\n", payload, dataURL)

	// 3. AbsJoin.
	joined := contextah.AbsJoin(base, "sub/file.txt")
	fmt.Printf("[abs_join]\n  %q + %q -> %q\n\n", base, "sub/file.txt", joined)

	// 4. InsideBaseDir: nested path inside, sibling outside.
	parent := filepath.Dir(base)
	sibling := filepath.Join(parent, "sibling-outside")
	if err := os.Mkdir(sibling, 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir sibling: %v\n", err)
		os.Exit(2)
	}
	fmt.Printf("[inside_base_dir]\n")
	fmt.Printf("  base=%q\n", base)
	fmt.Printf("  nested (%q)        inside=%v (want true)\n", sub, contextah.InsideBaseDir(base, sub))
	fmt.Printf("  sibling (%q)       inside=%v (want false)\n", sibling, contextah.InsideBaseDir(base, sibling))
	fmt.Printf("  missing            inside=%v (want false)\n", contextah.InsideBaseDir(base, filepath.Join(base, "nope")))
	fmt.Println()
}
