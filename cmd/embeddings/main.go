// Command embeddings is a small CLI front-end for the embeddings package.
//
// It prints the effective Config (resolved from env), probes the HTTP
// endpoint once to discover the embedding dimension, and on --encode reads
// JSON {"texts": [...]} from stdin and prints the resulting vectors as
// JSON. With --fastembed it tries to construct the (stubbed) FastEmbed
// client so operators can see the Go-port error message in context.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"time"

	"odysseus/embeddings"
)

func main() {
	if err := run(os.Args[1:], os.Stdin, os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, "embeddings:", err)
		os.Exit(1)
	}
}

func run(args []string, stdin io.Reader, stdout io.Writer) error {
	fs := flag.NewFlagSet("embeddings", flag.ContinueOnError)
	probe := fs.Bool("probe", false, "Probe the HTTP endpoint and print the embedding dimension.")
	encode := fs.Bool("encode", false, "Read {\"texts\":[...]} from stdin and print encoded vectors.")
	fastembed := fs.Bool("fastembed", false, "Try to construct a FastEmbedClient (will error in Go port).")
	reset := fs.Bool("reset-latch", false, "Reset the HTTP-down latch before any action.")
	timeout := fs.Duration("timeout", 15*time.Second, "HTTP probe / encode timeout.")
	if err := fs.Parse(args); err != nil {
		return err
	}

	if *reset {
		embeddings.ResetHTTPEmbedState()
	}

	cfg := embeddings.ConfigFromEnv()
	fmt.Fprintf(stdout, "url             = %s\n", cfg.URL)
	fmt.Fprintf(stdout, "model           = %s\n", cfg.Model)
	if cfg.APIKey != "" {
		fmt.Fprintf(stdout, "api_key         = %s (set)\n", maskKey(cfg.APIKey))
	} else {
		fmt.Fprintf(stdout, "api_key         = (unset)\n")
	}
	fmt.Fprintf(stdout, "connect_timeout = %s\n", cfg.ConnectTimeout)
	fmt.Fprintf(stdout, "read_timeout    = %s\n", cfg.ReadTimeout)
	fmt.Fprintf(stdout, "latch_down      = %v\n", embeddings.IsHTTPDown())

	if path := os.Getenv(embeddings.EnvEmbeddingPersist); path != "" {
		if ep, err := embeddings.LoadPersistedEndpoint(path); err == nil && ep.URL != "" {
			fmt.Fprintf(stdout, "persisted.url   = %s\n", ep.URL)
			if ep.Model != "" {
				fmt.Fprintf(stdout, "persisted.model = %s\n", ep.Model)
			}
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()

	if *fastembed {
		fe, err := embeddings.NewFastEmbedClient("")
		if err != nil {
			fmt.Fprintf(stdout, "fastembed       = unavailable (%v)\n", err)
		} else {
			fmt.Fprintf(stdout, "fastembed       = model=%s url=%s\n", fe.Model(), fe.URL())
		}
	}

	if *probe {
		c := embeddings.NewEmbeddingClient(cfg)
		d, err := c.Dimension(ctx)
		if err != nil {
			fmt.Fprintf(stdout, "probe           = error: %v\n", err)
		} else {
			fmt.Fprintf(stdout, "probe           = dim=%d\n", d)
		}
	}

	if *encode {
		var payload struct {
			Texts     []string `json:"texts"`
			Normalize *bool    `json:"normalize"`
		}
		raw, err := io.ReadAll(stdin)
		if err != nil {
			return fmt.Errorf("read stdin: %w", err)
		}
		if len(raw) > 0 {
			if err := json.Unmarshal(raw, &payload); err != nil {
				return fmt.Errorf("parse stdin: %w", err)
			}
		}
		normalize := true
		if payload.Normalize != nil {
			normalize = *payload.Normalize
		}
		c := embeddings.NewEmbeddingClient(cfg)
		vecs, err := c.Encode(ctx, payload.Texts, normalize)
		if err != nil {
			return fmt.Errorf("encode: %w", err)
		}
		dim := 0
		if len(vecs) > 0 {
			dim = len(vecs[0])
		}
		enc := json.NewEncoder(stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(map[string]any{
			"count":     len(vecs),
			"dim":       dim,
			"normalize": normalize,
			"vectors":   vecs,
		})
	}

	return nil
}

// maskKey keeps the operator's sanity while not echoing a full bearer
// token to a terminal / log scraper.
func maskKey(k string) string {
	if len(k) <= 6 {
		return "***"
	}
	return k[:3] + "***" + k[len(k)-3:]
}
