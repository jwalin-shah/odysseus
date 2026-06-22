// Command markitdown_runtime is a small CLI that prints whether a path is
// one of the formats routed through markitdown and, for .docx inputs,
// emits the bundled pure-Go extractor's output. It exists so operators
// can sanity-check format detection and the native fallback without
// booting the full Python stack.
package main

import (
	"flag"
	"fmt"
	"os"
	"strings"

	"odysseus/markitdown_runtime"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "markitdown_runtime:", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	fs := flag.NewFlagSet("markitdown_runtime", flag.ContinueOnError)
	formatOnly := fs.Bool("format-only", false, "print only whether the path is a markitdown format and exit")
	if err := fs.Parse(args); err != nil {
		return err
	}
	rest := fs.Args()
	if len(rest) != 1 {
		return fmt.Errorf("usage: markitdown_runtime [--format-only] <path>")
	}
	path := rest[0]

	if *formatOnly {
		if markitdown_runtime.IsMarkitdownFormat(path) {
			fmt.Printf("%s: markitdown format\n", path)
		} else {
			fmt.Printf("%s: not a markitdown format\n", path)
		}
		return nil
	}

	text, err := markitdown_runtime.Convert(path)
	if err != nil {
		return err
	}
	if text == "" {
		fmt.Fprintf(os.Stderr, "markitdown_runtime: no markdown text extracted for %s\n", path)
		return nil
	}
	if !strings.HasSuffix(text, "\n") {
		text += "\n"
	}
	fmt.Print(text)
	return nil
}
