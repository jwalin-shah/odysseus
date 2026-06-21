// Binary research_utils is a small CLI that exercises the research_utils
// package. It reads text from stdin (or a --file flag), strips thinking
// patterns via StripThinking, and prints the cleaned text to stdout.
// With --check-quality it instead classifies the input via IsLowQuality
// and prints "true" or "false".
package main

import (
	"flag"
	"fmt"
	"io"
	"os"

	"odysseus/research_utils"
)

func main() {
	file := flag.String("file", "", "path to read input from (default: stdin)")
	checkQuality := flag.Bool("check-quality", false, "classify input with IsLowQuality instead of stripping thinking")
	flag.Parse()

	var data []byte
	var err error
	if *file != "" {
		data, err = os.ReadFile(*file)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read %s: %v\n", *file, err)
			os.Exit(1)
		}
	} else {
		data, err = io.ReadAll(os.Stdin)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read stdin: %v\n", err)
			os.Exit(1)
		}
	}
	input := string(data)

	if *checkQuality {
		fmt.Println(research_utils.IsLowQuality(input))
		return
	}

	text := input
	out := research_utils.StripThinking(&text)
	if out == nil {
		fmt.Fprintln(os.Stderr, "StripThinking returned nil on non-nil input")
		os.Exit(1)
	}
	fmt.Print(*out)
}
