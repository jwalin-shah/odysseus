// Command email_thread_parser is a small CLI that exercises the
// email_thread_parser package: reads a plaintext email body from stdin,
// runs ParsePlaintext, and prints the resulting turns as JSON.
//
// Usage:
//
//	echo "..." | go run ./cmd/email_thread_parser
//	go run ./cmd/email_thread_parser -mode meta < input.txt
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"

	"odysseus/email_thread_parser"
)

func main() {
	mode := flag.String("mode", "thread", "thread (full turns) or meta (extract quote meta only)")
	flag.Parse()

	raw, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintln(os.Stderr, "email_thread_parser: read stdin:", err)
		os.Exit(1)
	}
	text := string(raw)

	switch *mode {
	case "meta":
		meta := email_thread_parser.ExtractQuoteMeta(text)
		out := map[string]any{"meta": meta}
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(out); err != nil {
			fmt.Fprintln(os.Stderr, "email_thread_parser: encode:", err)
			os.Exit(1)
		}
	case "thread":
		textPtr := text
		turns := email_thread_parser.ParseThread(nil, &textPtr)
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		if err := enc.Encode(turns); err != nil {
			fmt.Fprintln(os.Stderr, "email_thread_parser: encode:", err)
			os.Exit(1)
		}
	default:
		fmt.Fprintf(os.Stderr, "email_thread_parser: unknown mode %q (want thread or meta)\n", *mode)
		os.Exit(2)
	}
}
