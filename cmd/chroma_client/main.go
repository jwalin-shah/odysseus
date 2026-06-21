// Command chroma_client is a small CLI that exercises the chroma_client
// package: connect (using env config), ping heartbeat every 2s for 10s to
// demonstrate the singleton is reused, and optionally reset before connecting.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"odysseus/chroma_client"
)

func main() {
	reset := flag.Bool("reset", false, "Reset the cached client before connecting.")
	flag.Parse()

	if *reset {
		chroma_client.Reset()
	}

	ctx := context.Background()
	c, err := chroma_client.Get(ctx)
	if err != nil {
		fmt.Fprintln(os.Stderr, "chroma_client: connect failed:", err)
		os.Exit(1)
	}

	cfg, _ := chroma_client.ConfigFromEnv()
	fmt.Printf("Connected: %s:%d\n", cfg.Host, cfg.Port)

	// Five heartbeats at 2s intervals = ~10s total. Demonstrates singleton reuse.
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	timeout := time.After(10 * time.Second)
	for {
		select {
		case <-timeout:
			fmt.Println("done.")
			return
		case <-ticker.C:
			hctx, cancel := context.WithTimeout(ctx, cfg.ConnectTimeout)
			err := c.Heartbeat(hctx)
			cancel()
			if err != nil {
				fmt.Fprintln(os.Stderr, "heartbeat error:", err)
				continue
			}
			fmt.Printf("heartbeat ok (BaseURL=%s)\n", c.BaseURL)
		}
	}
}
