// Command ratelimiter-demo exercises the rate_limiter package end-to-end
// from the command line.
//
// Usage:
//
//	ratelimiter-demo --key 203.0.113.5 --max 5 --window 1m
//	ratelimiter-demo --key 203.0.113.5 --key 203.0.113.5 --max 5 --window 1m
//
// Each --key flag counts as one simulated request. The first N requests
// (where N = --max) are admitted; subsequent requests within --window
// are rate-limited. The exit code reflects the result of the LAST
// request: 0 when admitted, 1 when rate-limited.
//
// This is the smoke-test binary that mirrors how the Python module is
// used by the Odysseus server: construct a limiter, call check() on
// each request, and branch on the boolean result.
package main

import (
	"flag"
	"fmt"
	"os"
	"time"

	contextlimiter "github.com/odysseus/rate_limiter/pkg/ratelimiter"
)

func main() {
	var (
		maxKeys multiFlag
		window  time.Duration
		max     int
		showAll bool
	)
	flag.Var(&maxKeys, "key", "key to charge a request against (may be repeated)")
	flag.DurationVar(&window, "window", time.Minute, "sliding-window size, e.g. 30s, 1m")
	flag.IntVar(&max, "max", 5, "max requests permitted per key per window")
	flag.BoolVar(&showAll, "v", false, "print the full allow/reject log instead of just the final result")
	flag.Parse()

	if len(maxKeys) == 0 {
		fmt.Fprintln(os.Stderr, "--key is required (pass at least one)")
		flag.Usage()
		os.Exit(2)
	}
	if max <= 0 {
		fmt.Fprintln(os.Stderr, "--max must be > 0")
		os.Exit(2)
	}
	if window <= 0 {
		fmt.Fprintln(os.Stderr, "--window must be > 0")
		os.Exit(2)
	}

	limiter := contextlimiter.NewLimiter(max, window)

	var (
		admitted int
		rejected int
		lastOK   bool
	)
	for i, k := range maxKeys {
		lastOK = limiter.Allow(k)
		if lastOK {
			admitted++
		} else {
			rejected++
		}
		if showAll {
			status := "admit"
			if !lastOK {
				status = "REJECT"
			}
			fmt.Printf("[%d] key=%s -> %s\n", i+1, k, status)
		}
	}

	stats := limiter.Stats()
	fmt.Printf("key=%s max=%d window=%s admitted=%d rejected=%d last=%s keys_tracked=%d\n",
		maxKeys[len(maxKeys)-1], max, window, admitted, rejected,
		boolWord(lastOK), stats.Keys,
	)

	if lastOK {
		os.Exit(0)
	}
	os.Exit(1)
}

func boolWord(b bool) string {
	if b {
		return "admit"
	}
	return "REJECT"
}

// multiFlag collects repeated --key values into a single slice. Stdlib
// flag has no built-in for this; the only alternative is a comma-
// separated string, which would prevent keys containing commas.
type multiFlag []string

func (m *multiFlag) String() string {
	return fmt.Sprintf("%v", []string(*m))
}

func (m *multiFlag) Set(v string) error {
	*m = append(*m, v)
	return nil
}
