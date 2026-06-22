// Command assistantlog-demo exercises the assistantlog package end-to-end.
//
// It mirrors the Python module's legacy no-op semantics: calling
// LogToAssistant is a debug-level shim that does not create a session
// or post to a chat thread. The CLI is the wave-9 reference shape:
//
//	--help        print usage on stdout and exit 0
//	--list-tests  print every test name in pkg/assistantlog and exit 0
//	(default)     call LogToAssistant with the supplied --owner / --content
//	              / --category / --role and print the resolved Result
//
// The CLI deliberately does NOT print the content body — matching the
// Python source's "log_to_assistant ignored legacy activity" debug line,
// which omits the content. The category is surfaced because callers
// legitimately want to know which category the shim resolved.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"

	alog "github.com/odysseus/assistant_log/pkg/assistantlog"
)

// usage is the canonical --help text. Kept as a const so --list-tests
// can stay short and --help can be matched against the wave-9 reference
// port.
const usage = `assistantlog-demo — exercise the assistantlog package.

USAGE
  assistantlog-demo [options]

OPTIONS
  --help              show this help and exit
  --list-tests        print the names of every test in pkg/assistantlog, then exit
  --owner <string>    owner passed to LogToAssistant  (default "demo-owner")
  --role <string>     role passed to LogToAssistant   (default "assistant")
  --category <string> explicit category override      (default "")
  --content <string>  content passed to LogToAssistant
                      (default "**[Download]** demo activity entry")

DESCRIPTION
  Walks the public surface of github.com/odysseus/assistant_log/pkg/assistantlog.
  The Python source is a legacy no-op (it logs at DEBUG and returns) and
  this CLI surfaces the same shim behaviour: every LogToAssistant call
  reports Logged=false with Reason="legacy no-op".
`

// testNames is the hard-coded list of every Test* function in
// pkg/assistantlog/helpers_test.go. We hard-code it (rather than shelling
// out to `go test -list`) so --list-tests is reproducible and does not
// require a Go toolchain at runtime — the wave-9 standing rule allows
// either approach.
var testNames = []string{
	"TestParseLegacyTag",
	"TestParseLegacyTag/plain_download_tag",
	"TestParseLegacyTag/leading_whitespace",
	"TestParseLegacyTag/trailing_whitespace_after_tag",
	"TestParseLegacyTag/category_with_spaces",
	"TestParseLegacyTag/category_at_max_length_(40)",
	"TestParseLegacyTag/no_tag",
	"TestParseLegacyTag/empty_string",
	"TestParseLegacyTag/tag_too_long_(>40)_is_rejected",
	"TestParseLegacyTag/missing_closing_bracket",
	"TestParseLegacyTag/missing_asterisks",
	"TestParseLegacyTag/single_asterisk_is_not_enough",
	"TestParseLegacyTag/tag_with_embedded_close-bracket_is_rejected",
	"TestLogToAssistantNoOp",
	"TestLogToAssistantNoOp/empty",
	"TestLogToAssistantNoOp/only_owner",
	"TestLogToAssistantNoOp/only_content",
	"TestLogToAssistantNoOp/explicit_category",
	"TestLogToAssistantNoOp/legacy_tag_category",
	"TestLogToAssistantNoOp/full_options",
	"TestLogToAssistantCategoryResolution",
	"TestLogToAssistantCategoryResolution/explicit_category_wins",
	"TestLogToAssistantCategoryResolution/legacy_tag_when_no_explicit_category",
	"TestLogToAssistantCategoryResolution/empty_when_neither",
	"TestLogToAssistantDebugLogEmitted",
	"TestLogToAssistantDefaultRole",
	"TestLogToAssistantNilLogger",
	"TestSetSessionManagerIsNoOp",
	"TestSetSessionManagerNilResetsDefault",
}

func main() {
	if err := run(os.Args[1:], os.Stdout, os.Stderr); err != nil {
		fmt.Fprintln(os.Stderr, "assistantlog-demo:", err)
		os.Exit(1)
	}
}

func run(args []string, stdout, stderr *os.File) error {
	// Intercept --help / -h before flag.Parse — flag.ContinueOnError
	// would otherwise print an error for the bare -h. Matches the
	// wave-9 standing rule that --help exits 0 on stdout.
	for _, a := range args {
		if a == "-h" || a == "--help" || a == "-help" {
			fmt.Fprint(stdout, usage)
			return nil
		}
		if a == "--list-tests" {
			fmt.Fprintln(stdout, "tests:")
			for _, n := range testNames {
				fmt.Fprintf(stdout, "  %s\n", n)
			}
			return nil
		}
	}

	fs := flag.NewFlagSet("assistantlog-demo", flag.ContinueOnError)
	fs.SetOutput(stderr)
	owner := fs.String("owner", "demo-owner", "Owner passed to LogToAssistant.")
	content := fs.String("content", "**[Download]** demo activity entry",
		"Content passed to LogToAssistant. The legacy **[Category]** prefix is parsed automatically.")
	role := fs.String("role", alog.DefaultRole,
		"Role passed to LogToAssistant. Empty string falls back to DefaultRole.")
	category := fs.String("category", "",
		"Explicit category override. When empty, the legacy **[Category]** prefix wins.")
	if err := fs.Parse(args); err != nil {
		return err
	}

	res := alog.LogToAssistant(context.Background(), alog.LogOptions{
		Owner:    *owner,
		Content:  *content,
		Role:     *role,
		Category: *category,
	}, nil)

	fmt.Fprintf(stdout, "logged=%t reason=%q category=%q owner=%q role=%q\n",
		res.Logged,
		res.Reason,
		res.Category,
		*owner,
		effectiveRole(*role),
	)
	return nil
}

// effectiveRole mirrors the package's empty-defaults-to-"assistant"
// rule so the CLI's printed role matches what LogToAssistant actually
// used. Saves a reader from having to look up DefaultRole to interpret
// the output.
func effectiveRole(r string) string {
	if r == "" {
		return alog.DefaultRole
	}
	return r
}
