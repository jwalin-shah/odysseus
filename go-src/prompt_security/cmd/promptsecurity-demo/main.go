// Command promptsecurity-demo renders an untrusted-context message and prints
// it so a human reviewer can eyeball the sandbox framing without writing a
// test program.
//
// Usage:
//
//	promptsecurity-demo --label "email" --content "Hello, world!"
//	promptsecurity-demo --label "web result" --content "answer is 42"
//	promptsecurity-demo --label "doc"          (empty body)
//	promptsecurity-demo --help
//
// The demo renders the same template that the Python helper produces and
// also prints the JSON shape that would be sent to an LLM provider. Exit 0
// on success, 2 on bad usage.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	contextpromptsecurity "github.com/odysseus/prompt_security/pkg/promptsecurity"
)

func main() {
	var (
		label   string
		content string
		asJSON  bool
		showRaw bool
	)
	flag.StringVar(&label, "label", "", "source label (e.g. \"email\", \"web result\")")
	flag.StringVar(&content, "content", "", "untrusted body text (empty string allowed)")
	flag.BoolVar(&asJSON, "json", false, "also print the message as JSON")
	flag.BoolVar(&showRaw, "show-markers", false, "render GUARD_OPEN/GUARD_CLOSE on their own lines for inspection")
	flag.Parse()

	if label == "" {
		fmt.Fprintln(os.Stderr, "--label is required")
		flag.Usage()
		os.Exit(2)
	}

	msg := contextpromptsecurity.UntrustedContextMessage(label, content)

	fmt.Println("== promptsecurity demo ==")
	fmt.Printf("label:    %q\n", label)
	fmt.Printf("role:     %s\n", msg.Role)
	fmt.Printf("trusted:  %v\n", msg.Metadata.Trusted)
	fmt.Printf("source:   %q\n", msg.Metadata.Source)
	fmt.Println("--- content ---")
	if showRaw {
		// Replace the guard markers with newlines so a human can see the
		// sandbox framing clearly in the terminal. Production callers
		// should NOT do this — the markers MUST be intact on the wire.
		rendered := msg.Content
		fmt.Println(rendered)
		fmt.Println("--- markers highlighted ---")
		fmt.Printf("GUARD_OPEN  at byte %d\n", indexOf(msg.Content, contextpromptsecurity.GuardOpen))
		fmt.Printf("GUARD_CLOSE at byte %d\n", indexOf(msg.Content, contextpromptsecurity.GuardClose))
	} else {
		fmt.Println(msg.Content)
	}

	if asJSON {
		fmt.Println("--- json ---")
		b, err := json.MarshalIndent(msg, "", "  ")
		if err != nil {
			fmt.Fprintf(os.Stderr, "marshal: %v\n", err)
			os.Exit(1)
		}
		fmt.Println(string(b))
	}
}

func indexOf(s, sub string) int {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return i
		}
	}
	return -1
}
