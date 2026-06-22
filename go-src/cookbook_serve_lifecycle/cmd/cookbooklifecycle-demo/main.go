// Command cookbooklifecycle-demo runs a single tick of the cookbook serve
// lifecycle. It is the Go replacement for the asyncio loop in
// src/cookbook_serve_lifecycle.py, trimmed down to the same minimum: read
// state, kill expired tmux sessions, patch the state file, exit. Long-running
// loops live in higher-level supervisors (e.g. the cockpit).
package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jwalin-shah/odysseus/cookbook_serve_lifecycle/pkg/cookbookserve"
)

func main() {
	stateFile := flag.String("state", envOr("ODY_COOKBOOK_STATE_FILE", "./cookbook_state.json"),
		"path to the cookbook state JSON file")
	loopMode := flag.Bool("loop", false,
		"run the forever loop instead of a single tick (Ctrl-C to stop)")
	tickInterval := flag.Duration("tick", cookbookserve.DefaultTickInterval,
		"override the default tick interval (loop mode only)")
	initialSleep := flag.Duration("initial-sleep", cookbookserve.DefaultInitialSleep,
		"override the initial startup sleep (loop mode only)")
	flag.Parse()

	logger := log.New(os.Stderr, "cookbooklifecycle-demo: ", log.LstdFlags)

	ctx, cancel := signal.NotifyContext(context.Background(),
		os.Interrupt, syscall.SIGTERM)
	defer cancel()

	lc := cookbookserve.NewLifecycle()
	lc.StateFilePath = *stateFile
	lc.Client = cookbookserve.NewHTTPClient()
	lc.Logger = logger

	if *loopMode {
		lc.TickInterval = *tickInterval
		lc.InitialSleep = *initialSleep
		logger.Printf("entering forever loop (tick=%s initial-sleep=%s)",
			lc.TickInterval, lc.InitialSleep)
		if err := lc.Run(ctx); err != nil && err != context.Canceled {
			logger.Fatalf("loop exited: %v", err)
		}
		fmt.Println("cookbooklifecycle-demo: loop cancelled, exiting")
		return
	}

	// Snapshot the candidate list up front so we can print a stable
	// "stopped=N" count after the tick rewrites the state file.
	before, err := cookbookserve.ReadStateFile(*stateFile)
	if err != nil && !os.IsNotExist(err) {
		logger.Fatalf("read state: %v", err)
	}
	now := time.Now().UnixMilli()
	candidates := cookbookserve.FindTasksToStop(before, now)

	if err := lc.Tick(ctx); err != nil {
		logger.Fatalf("tick failed: %v", err)
	}
	fmt.Printf("cookbooklifecycle-demo: tick complete (stopped=%d)\n", len(candidates))
}

// envOr returns the value of name from the environment, falling back to
// defaultVal when unset or empty.
func envOr(name, defaultVal string) string {
	if v := os.Getenv(name); v != "" {
		return v
	}
	return defaultVal
}
