// Command generatedimages-demo demonstrates the wiring of the
// generatedimages package. It exercises the resolver against a tempdir
// containing one valid file and one file with a disallowed extension:
//
//   - valid filename      → returns the absolute path
//   - missing file        → returns *NotFoundError
//   - bad extension       → returns *FilenameError
//   - traversal attempt   → returns *FilenameError
//   - empty filename      → returns *FilenameError
//
// Each scenario is printed as a one-line summary plus the typed-error
// branch (filename vs not-found) so a reviewer can eyeball the
// surface without writing a test program.
package main

import (
	"fmt"
	"os"
	"path/filepath"

	contextgi "github.com/odysseus/generated_images/pkg/generatedimages"
)

func runScenario(label, dir, filename string) {
	fmt.Printf("[%s]\n", label)
	fmt.Printf("  filename = %q\n", filename)
	got, err := contextgi.Resolve(dir, filename)
	switch {
	case err == nil:
		fmt.Printf("  resolved = %q (ok)\n", got)
	case contextgi.IsFilename(err):
		fmt.Printf("  rejected (filename): %v\n", err)
	case contextgi.IsNotFound(err):
		fmt.Printf("  rejected (not-found): %v\n", err)
	default:
		fmt.Printf("  rejected (other): %v\n", err)
	}
	fmt.Println()
}

func main() {
	fmt.Println("== generatedimages demo ==")
	fmt.Println()

	dir, err := os.MkdirTemp("", "generatedimages-")
	if err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(2)
	}
	defer os.RemoveAll(dir)

	// Lay down one valid file plus one with a disallowed extension.
	for _, name := range []string{"abcdef12.png", "ignore.exe"} {
		if err := os.WriteFile(filepath.Join(dir, name), []byte("X"), 0o644); err != nil {
			fmt.Fprintf(os.Stderr, "write %s: %v\n", name, err)
			os.Exit(2)
		}
	}

	// Print canonical headers.
	fmt.Println("[image headers]")
	for k, v := range contextgi.ImageHeaders {
		fmt.Printf("  %s: %s\n", k, v)
	}
	fmt.Println()

	runScenario("happy path", dir, "abcdef12.png")
	runScenario("missing file", dir, "deadbeef.png")
	runScenario("bad extension", dir, "abcdef12.exe")
	runScenario("traversal attempt", dir, "../etc/passwd.png")
	runScenario("empty filename", dir, "")

	// Print the package's regex / extension surface for ops grep.
	fmt.Println("[allowed extensions]")
	fmt.Printf("  %v\n", contextgi.AllowedExtensions)
	fmt.Println()
}
