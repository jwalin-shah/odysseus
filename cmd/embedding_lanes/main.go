// Command embedding_lanes is a small CLI that prints the fingerprint and
// metadata that the embedding_lanes Go package would write for a given
// base_name + configured embedding client. It exists for parity with the
// Python embedding_lanes module while a real chromadb-go surface is being
// ported separately.
//
// When EMBEDDING_URL is set, the binary uses the odysseus/embeddings HTTP
// client to probe the dimension; otherwise it falls back to a stub fastembed
// client so the CLI is useful without an external endpoint. The chroma
// collection is NOT touched from this CLI — operators should run the
// build_embedding_lanes code from their own server boot path.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"odysseus/embedding_lanes"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "embedding_lanes:", err)
		os.Exit(1)
	}
}

func run() error {
	var (
		baseName = flag.String("base", "memory", "Base name for the lane collection (e.g. memory, rag).")
		laneName = flag.String("lane", embedding_lanes.LANE_CUSTOM, "Lane name to inspect (custom or fastembed).")
		model    = flag.String("model", "all-minilm:l6-v2", "Embedding model to assume for the fingerprint.")
		dim      = flag.Int("dimension", 0, "Override the embedding dimension (default: probe via the HTTP client).")
		timeout  = flag.Duration("timeout", 5*time.Second, "HTTP probe timeout for dimension discovery.")
	)
	flag.Parse()

	url := os.Getenv("EMBEDDING_URL")
	kind := "stub"
	dimension := *dim
	if dimension <= 0 {
		if url == "" {
			dimension = 384 // sensible default for the all-MiniLM-L6-v2 family
		} else {
			ctx, cancel := context.WithTimeout(context.Background(), *timeout)
			defer cancel()
			d, err := probeDimension(ctx, url)
			if err != nil {
				return fmt.Errorf("probe dimension: %w", err)
			}
			dimension = d
			kind = "http"
		}
	}

	fp := embedding_lanes.Fingerprint(*laneName, url, *model, dimension)
	meta := embedding_lanes.Metadata(*laneName, url, *model, dimension, fp)
	name := embedding_lanes.CollectionName(*baseName, *laneName)

	fmt.Printf("base:          %s\n", *baseName)
	fmt.Printf("lane:          %s\n", *laneName)
	fmt.Printf("collection:    %s\n", name)
	fmt.Printf("model:         %s\n", *model)
	fmt.Printf("url:           %q\n", url)
	fmt.Printf("dimension:     %d\n", dimension)
	fmt.Printf("fingerprint:   %s\n", fp)
	fmt.Printf("client_kind:   %s\n", kind)

	out, err := json.MarshalIndent(meta, "", "  ")
	if err != nil {
		return fmt.Errorf("render metadata: %w", err)
	}
	fmt.Println("metadata:")
	fmt.Println(string(out))
	return nil
}

// probeDimension hits an OpenAI-compatible /v1/embeddings endpoint with a
// single short string and reads the dimension out of the response. We do
// this without importing odysseus/embeddings so the binary stays a thin
// inspection tool; the server boot path imports embeddings directly.
func probeDimension(ctx context.Context, url string) (int, error) {
	model := os.Getenv("EMBEDDING_MODEL")
	body, err := json.Marshal(map[string]any{
		"input": []string{"hello"},
		"model": model,
	})
	if err != nil {
		return 0, fmt.Errorf("marshal request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return 0, fmt.Errorf("build request: %w", err)
	}
	if key := os.Getenv("EMBEDDING_API_KEY"); key != "" {
		req.Header.Set("Authorization", "Bearer "+key)
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("http: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		_, _ = io.Copy(io.Discard, resp.Body)
		return 0, fmt.Errorf("unexpected status %d", resp.StatusCode)
	}
	var payload struct {
		Data []struct {
			Embedding []float64 `json:"embedding"`
		} `json:"data"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return 0, fmt.Errorf("decode: %w", err)
	}
	if len(payload.Data) == 0 || len(payload.Data[0].Embedding) == 0 {
		return 0, fmt.Errorf("empty embedding in response")
	}
	d := len(payload.Data[0].Embedding)
	if d <= 0 {
		return 0, fmt.Errorf("non-positive dimension %d", d)
	}
	return d, nil
}
