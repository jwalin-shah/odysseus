// Command document_processor is a small CLI front-end for the
// document_processor Go package.
//
// Usage:
//
//	document_processor <path>
//
// The binary only handles text files (see document_processor.IsTextFile).
// PDFs, Office documents, and images are out of scope for this port —
// when given a non-text path, the binary prints a clear refusal to stderr
// and exits with a non-zero status so callers can branch on the error.
package main

import (
	"errors"
	"fmt"
	"io"
	"os"

	"odysseus/document_processor"
)

func main() {
	if err := run(os.Args[1:], os.Stdout, os.Stderr); err != nil {
		fmt.Fprintln(os.Stderr, "document_processor:", err)
		os.Exit(1)
	}
}

func run(args []string, stdout, stderr io.Writer) error {
	if len(args) != 1 {
		return fmt.Errorf("usage: %s <path>", os.Args[0])
	}
	path := args[0]
	if !document_processor.IsTextFile(path) {
		return fmt.Errorf("%w: %s — only text/code/log extensions are supported by this port", document_processor.ErrNotTextFile, path)
	}
	out, err := document_processor.ProcessTextFile(path)
	if err != nil {
		// ProcessTextFile never returns ErrNotTextFile here (we just
		// checked), so any error at this point is a read failure.
		if errors.Is(err, document_processor.ErrNotTextFile) {
			return err
		}
		return fmt.Errorf("process %s: %w", path, err)
	}
	fmt.Fprintln(stdout, out)
	return nil
}
