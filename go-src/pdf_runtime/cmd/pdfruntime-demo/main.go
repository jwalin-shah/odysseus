// Command pdfruntime-demo demonstrates the wiring of the pdfruntime
// package. It exercises three Loader scenarios:
//
//   - successful static load   → prints the loaded handle
//   - failing load             → prints MissingMessage and exits 3
//   - nil Loader               → prints an explanatory message
//
// The demo intentionally does NOT depend on PyMuPDF — the goal is to
// exercise the user-facing setup-hint path the same way the Python
// source does in tests, where `import fitz` failure surfaces as a
// RuntimeError with PDF_VIEWER_PYMUPDF_MISSING.
package main

import (
	"errors"
	"fmt"
	"os"

	contextpdf "github.com/odysseus/pdf_runtime/pkg/pdfruntime"
)

func runScenario(label string, loader contextpdf.Loader) int {
	fmt.Printf("[%s]\n", label)
	if loader == nil {
		fmt.Println("  no loader supplied (would surface a 501 in a real handler)")
		fmt.Println()
		return 0
	}
	v, err := loader.Load()
	if err == nil {
		fmt.Printf("  loaded: %v\n", v)
		fmt.Println()
		return 0
	}
	if errors.Is(err, contextpdf.ErrMissing) {
		fmt.Printf("  ERR_MISSING: %s\n", err.Error())
		fmt.Println()
		// Caller is expected to return 424 / 501 — exit non-zero so CI
		// smoke tests catch the missing-dependency path.
		return 3
	}
	fmt.Printf("  ERR_OTHER: %v\n", err)
	fmt.Println()
	return 4
}

func main() {
	fmt.Println("== pdfruntime demo ==")
	fmt.Println()

	rc := 0
	rc |= runScenario("static loader (success)",
		contextpdf.StaticLoader{Value: "fitz-handle"})
	rc |= runScenario("failing loader (PyMuPDF absent)",
		contextpdf.FailingLoader{})
	rc |= runScenario("nil loader (would surface 501)",
		nil)

	if rc != 0 {
		os.Exit(rc)
	}
}
