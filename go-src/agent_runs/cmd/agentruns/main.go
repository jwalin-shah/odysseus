// Command agentruns is a small demo of the agent_runs package: it starts a
// run, simulates five SSE events on a timer, subscribes a client, prints
// the replayed buffer, and stops the run.
package main

import (
	"context"
	"fmt"
	"os"
	"time"

	agentruns "github.com/odysseus/agent_runs/pkg/agentruns"
)

type timedSource struct {
	events []string
	delay  time.Duration
}

func (t *timedSource) Next(ctx context.Context, sink func(ev string)) error {
	for _, ev := range t.events {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(t.delay):
		}
		sink(ev)
	}
	return nil
}

func main() {
	mgr := agentruns.New()

	events := []string{
		"event: message\ndata: hello\n\n",
		"event: message\ndata: world\n\n",
		"event: message\ndata: from\n\n",
		"event: message\ndata: agent_runs\n\n",
		"event: message\ndata: demo\n\n",
	}

	run := mgr.Start("demo", &timedSource{events: events, delay: 40 * time.Millisecond})
	fmt.Printf("started run: status=%s\n", run.Status())

	// Give the drain a moment to publish some events.
	time.Sleep(120 * time.Millisecond)

	sub, err := mgr.Subscribe(context.Background(), "demo")
	if err != nil {
		fmt.Fprintf(os.Stderr, "subscribe: %v\n", err)
		os.Exit(1)
	}

	fmt.Println("=== events ===")
	for {
		ev, ok := sub.Next(context.Background())
		if !ok {
			break
		}
		fmt.Printf("[seq=%d] %s", ev.Seq, ev.Data)
	}

	fmt.Println("=== buffer snapshot ===")
	for _, ev := range run.Buffer() {
		fmt.Printf("%s", ev)
	}

	if mgr.Stop("demo") {
		fmt.Println("stopped run")
	}

	if st, ok := mgr.GetStatus("demo"); ok {
		fmt.Printf("final status: %s\n", st)
	}
}
