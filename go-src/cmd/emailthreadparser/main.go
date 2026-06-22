// Command emailthreadparser demonstrates wiring of the emailthreadparser
// package by reading a body from a file (or stdin) and printing the
// resulting turn tree as JSON.
//
// Usage:
//
//	emailthreadparser [--text file] [--html file]
//
// At least one of --text or --html must be supplied. With both, the HTML
// body is preferred (mirroring ParseThread); the plaintext body is used
// as a fallback.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/odysseus/odysseus/emailthreadparser"
)

func main() {
	textPath := flag.String("text", "", "path to a plaintext email body (use - for stdin)")
	htmlPath := flag.String("html", "", "path to an HTML email body (use - for stdin)")
	showVersion := flag.Bool("version", false, "print ThreadParserVersion and exit")
	flag.Parse()

	if *showVersion {
		fmt.Println(emailthreadparser.ThreadParserVersion)
		return
	}

	if *textPath == "" && *htmlPath == "" {
		fmt.Fprintln(os.Stderr, "usage: emailthreadparser [--text file] [--html file]")
		os.Exit(2)
	}

	var bodyHTML, bodyText string
	if *htmlPath != "" {
		data, err := readInput(*htmlPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read html: %v\n", err)
			os.Exit(1)
		}
		bodyHTML = string(data)
	}
	if *textPath != "" {
		data, err := readInput(*textPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read text: %v\n", err)
			os.Exit(1)
		}
		bodyText = string(data)
	}

	turns := emailthreadparser.ParseThread(bodyHTML, bodyText)
	if turns == nil {
		fmt.Fprintln(os.Stderr, "no quoted material found (parser returned nil)")
		// Print an empty JSON array so downstream consumers can rely on
		// well-formed output even when no thread structure exists.
		fmt.Println("[]")
		return
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(turns); err != nil {
		fmt.Fprintf(os.Stderr, "encode: %v\n", err)
		os.Exit(1)
	}
}

// readInput loads a file (or stdin when path == "-").
func readInput(path string) ([]byte, error) {
	if path == "-" {
		return io.ReadAll(os.Stdin)
	}
	return os.ReadFile(path)
}
