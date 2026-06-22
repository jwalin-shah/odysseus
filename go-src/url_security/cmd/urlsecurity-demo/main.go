// Package main is a small wiring demo for go-src/url_security. It runs
// Classify against a single --url flag and prints the verdict. No
// network is contacted beyond what Classify itself does (DNS for the
// hostname under test).
package main

import (
	"flag"
	"fmt"
	"os"

	contexturlsec "github.com/odysseus/url_security/pkg/urlsecurity"
)

func main() {
	urlFlag := flag.String("url", "", "URL to classify against the strict public-HTTP(S) policy")
	flag.Parse()

	if *urlFlag == "" {
		fmt.Fprintln(os.Stderr, "usage: urlsecurity-demo --url <URL>")
		os.Exit(2)
	}

	v := contexturlsec.Classify(*urlFlag)
	status := "REJECT"
	if v.Reason == "ok" {
		status = "ACCEPT"
	}
	fmt.Printf("VERDICT: %s\n", status)
	fmt.Printf("  reason:  %s\n", v.Reason)
	fmt.Printf("  url:     %s\n", v.URL)
	fmt.Printf("  ip:      %s\n", emptyAsNone(v.IP))
	fmt.Printf("  private: %t\n", v.Private)

	// Strict-path exit codes make it easy to use the demo in shell
	// pipelines. 0 = accepted, 1 = rejected.
	if v.Reason != "ok" {
		os.Exit(1)
	}
}

func emptyAsNone(s string) string {
	if s == "" {
		return "(none)"
	}
	return s
}
