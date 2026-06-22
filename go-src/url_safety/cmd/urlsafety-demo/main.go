// Command urlsafety-demo classifies a single URL passed via --url.
//
// Usage:
//
//	urlsafety-demo --url https://example.com
//	urlsafety-demo --url http://169.254.169.254/latest/meta-data/ --block-private
//
// It prints a one-line summary suitable for CI smoke checks: ok / not-ok,
// the reason, and the resolved IP list (if any). Exits 0 on OK, 1 on
// rejection.
package main

import (
	"flag"
	"fmt"
	"os"

	contexturlsafety "github.com/odysseus/url_safety/pkg/urlsafety"
)

func main() {
	var (
		rawURL       string
		blockPrivate bool
		resolverHost string // optional override used by the test fixtures
	)
	flag.StringVar(&rawURL, "url", "", "URL to classify (required)")
	flag.BoolVar(&blockPrivate, "block-private", false, "reject private/loopback ranges in addition to link-local")
	flag.StringVar(&resolverHost, "resolver", "", "if set, return only this IP from the injected resolver (demo aid)")
	flag.Parse()

	if rawURL == "" {
		fmt.Fprintln(os.Stderr, "--url is required")
		os.Exit(2)
	}

	var resolver contexturlsafety.Resolver
	if resolverHost != "" {
		resolver = func(string) ([]string, error) {
			return []string{resolverHost}, nil
		}
	}

	res := contexturlsafety.Check(rawURL, blockPrivate, resolver)

	fmt.Printf("url:           %s\n", rawURL)
	fmt.Printf("ok:            %t\n", res.OK)
	fmt.Printf("reason:        %s\n", res.Reason)
	fmt.Printf("scheme:        %s\n", res.Scheme)
	fmt.Printf("host:          %s\n", res.Host)
	if len(res.IPs) > 0 {
		fmt.Printf("resolved_ips:  %v\n", res.IPs)
	}

	if res.OK {
		os.Exit(0)
	}
	os.Exit(1)
}
