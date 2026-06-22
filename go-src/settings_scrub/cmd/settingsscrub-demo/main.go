// Command settingsscrub-demo is a small CLI that exercises the
// settingsscrub package end-to-end. It accepts a JSON document via --json
// or a key/value pair via --secret, runs it through ScrubSettings, and
// prints the redacted output. It is the Go equivalent of the manual
// smoke test the Python source's docstring describes ("load-bearing when
// the app is reachable over a Cloudflare tunnel / reverse proxy").
//
// Usage:
//
//	settingsscrub-demo --json '{"openai_api_key":"K","theme":"dark"}'
//	settingsscrub-demo --secret openai_api_key=sk-12345
//	settingsscrub-demo --json @-              # read JSON from stdin
//	settingsscrub-demo --help
//
// Exit codes:
//
//	0 - input parsed, scrub ran, output printed
//	2 - missing or invalid arguments (--help exits 0)
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	contextscrub "github.com/odysseus/settings_scrub/pkg/settingsscrub"
)

// pretty marshals v in a stable, human-readable form. We hand-roll a tiny
// pretty printer to avoid pulling encoding/json's MarshalIndent (which is
// fine, but indents with two spaces and would be slightly inconsistent with
// the rest of the demo output). In practice MarshalIndent is the right
// choice — kept inline to keep the demo self-contained.
func pretty(v map[string]any) (string, error) {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return "", err
	}
	return string(b), nil
}

func readStdin() ([]byte, error) {
	return io.ReadAll(os.Stdin)
}

func main() {
	var (
		jsonFlag = flag.String("json", "", "JSON document to scrub (use @- for stdin)")
		keyFlag  = flag.String("secret", "", "single key=value pair to add to an otherwise empty settings object")
		probeKey = flag.String("probe", "", "optional key name; if set, the demo also prints is_secret_key(<key>) so reviewers can eyeball the matcher")
	)
	flag.Usage = func() {
		fmt.Fprintln(os.Stderr, "settingsscrub-demo — exercise the secret scrubber end-to-end.")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "Usage:")
		fmt.Fprintln(os.Stderr, "  settingsscrub-demo --json '{\"openai_api_key\":\"K\",\"theme\":\"dark\"}'")
		fmt.Fprintln(os.Stderr, "  settingsscrub-demo --secret openai_api_key=sk-12345")
		fmt.Fprintln(os.Stderr, "  settingsscrub-demo --json @-                # read JSON from stdin")
		fmt.Fprintln(os.Stderr, "  settingsscrub-demo --probe apiKey          # check the matcher only")
		fmt.Fprintln(os.Stderr, "")
		flag.PrintDefaults()
	}
	flag.Parse()

	if *jsonFlag == "" && *keyFlag == "" && *probeKey == "" {
		flag.Usage()
		os.Exit(2)
	}

	if *probeKey != "" {
		fmt.Printf("is_secret_key(%q) = %v\n", *probeKey, contextscrub.IsSecretKey(*probeKey))
	}

	var input map[string]any
	if *jsonFlag != "" {
		body := []byte(*jsonFlag)
		if *jsonFlag == "@-" {
			b, err := readStdin()
			if err != nil {
				fmt.Fprintf(os.Stderr, "read stdin: %v\n", err)
				os.Exit(1)
			}
			body = b
		}
		input = contextscrub.JSONScrubSettings(body)
	} else if *keyFlag != "" {
		// Build a single-key map from "key=value".
		idx := strings.IndexByte(*keyFlag, '=')
		if idx <= 0 {
			fmt.Fprintf(os.Stderr, "--secret expects key=value (got %q)\n", *keyFlag)
			os.Exit(2)
		}
		k := (*keyFlag)[:idx]
		v := (*keyFlag)[idx+1:]
		input = contextscrub.ScrubSettings(map[string]any{k: v})
	}

	fmt.Printf("input settings:  %s\n", mustPretty(input))
	// Scrub a second time to demonstrate idempotency (scrubbing an already
	// scrubbed map leaves it unchanged — the redacted values are empty
	// strings, which the matcher preserves).
	out := contextscrub.ScrubSettings(input)
	fmt.Printf("scrubbed output: %s\n", mustPretty(out))
	fmt.Printf("idempotent:      %v\n", sameJSON(input, out))
}

func mustPretty(v map[string]any) string {
	s, err := pretty(v)
	if err != nil {
		return fmt.Sprintf("<marshal error: %v>", err)
	}
	return s
}

func sameJSON(a, b map[string]any) bool {
	ab, _ := json.Marshal(a)
	bb, _ := json.Marshal(b)
	return string(ab) == string(bb)
}
