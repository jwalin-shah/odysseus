// Command embeddings exercises the embeddings package end-to-end against a
// real (or stubbed) HTTP endpoint, and prints a small diagnostic summary.
//
// Usage:
//
//	embeddings -url http://localhost:11434/v1/embeddings -model all-minilm:l6-v2
//	embeddings -persist path/to/embedding_endpoint.json
//	embeddings -use-fallback -dim 8
//
// Without any flags the binary uses GetEmbeddingClient (env-driven) and
// falls back to the registered local FastEmbed stub.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"os"
	"strings"

	"github.com/odysseus/odysseus/embeddings"
)

func main() {
	var (
		url         = flag.String("url", "", "HTTP embedding endpoint URL (overrides EMBEDDING_URL)")
		model       = flag.String("model", "", "Model name to request (overrides EMBEDDING_MODEL)")
		apiKey      = flag.String("api-key", "", "Optional bearer token (overrides EMBEDDING_API_KEY)")
		persist     = flag.String("persist", "", "Path to a persisted endpoint JSON (admin-panel style)")
		useFallback = flag.Bool("use-fallback", false, "Skip the HTTP branch and use the registered FastEmbed stub")
		stubDim     = flag.Int("dim", 8, "Embedding dimension for the built-in FastEmbed stub")
		probe       = flag.String("probe", "hello", "Text to embed for the smoke-test call")
		jsonOut     = flag.Bool("json", false, "Emit the embedding vector as JSON instead of the summary")
	)
	flag.Parse()

	if err := run(runOpts{
		url:         *url,
		model:       *model,
		apiKey:      *apiKey,
		persist:     *persist,
		useFallback: *useFallback,
		stubDim:     *stubDim,
		probe:       *probe,
		jsonOut:     *jsonOut,
	}); err != nil {
		log.Fatalf("embeddings: %v", err)
	}
}

type runOpts struct {
	url, model, apiKey, persist, probe string
	useFallback                        bool
	stubDim                            int
	jsonOut                            bool
}

func run(o runOpts) error {
	// Always register a hash-based stub for the FastEmbed fallback so the
	// binary is usable in environments without a real backend.
	embeddings.SetDefaultFastEmbed(stubEmbedder(o.stubDim))

	// Resolve the embedder. -use-fallback bypasses the HTTP branch even if
	// EMBEDDING_URL is set.
	var (
		emb    embeddings.Embedder
		err    error
		source string
	)
	if o.useFallback {
		emb = embeddings.NewFastEmbedClient("", embeddings.DefaultFastEmbedFor(o.stubDim))
		source = "fallback (cli flag)"
	} else {
		// Layer CLI flags on top of env so explicit args win.
		if o.url != "" {
			_ = os.Setenv(embeddings.EnvEmbeddingURL, o.url)
		}
		if o.model != "" {
			_ = os.Setenv(embeddings.EnvEmbeddingModel, o.model)
		}
		if o.apiKey != "" {
			_ = os.Setenv(embeddings.EnvEmbeddingAPIKey, o.apiKey)
		}
		emb, err = embeddings.GetEmbeddingClient(embeddings.EndpointConfig{
			PersistedFile: o.persist,
		})
		if err != nil {
			return err
		}
		source = classify(emb)
	}

	// Always print the resolved metadata so the binary is a useful probe.
	switch c := emb.(type) {
	case *embeddings.EmbeddingClient:
		fmt.Fprintf(os.Stderr, "backend: HTTP %s model=%s\n", c.URL, c.Model)
	case *embeddings.FastEmbedClient:
		fmt.Fprintf(os.Stderr, "backend: FastEmbed model=%s (source=%s)\n", c.Model, source)
	}

	vecs, err := emb.Encode([]string{o.probe}, true)
	if err != nil {
		return fmt.Errorf("encode %q: %w", o.probe, err)
	}
	if len(vecs) == 0 {
		return fmt.Errorf("encode %q: empty result", o.probe)
	}

	dim, err := emb.GetSentenceEmbeddingDimension()
	if err != nil {
		return fmt.Errorf("dimension: %w", err)
	}

	if o.jsonOut {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(map[string]any{
			"probe":      o.probe,
			"dimension":  dim,
			"normalized": true,
			"embedding":  vecs[0],
		})
	}

	fmt.Printf("probe=%q dim=%d vector=", o.probe, dim)
	printVector(vecs[0])
	fmt.Println()
	return nil
}

// classify returns a short human-readable description of which backend the
// factory handed back, used only for the binary's stderr banner.
func classify(emb embeddings.Embedder) string {
	switch emb.(type) {
	case *embeddings.EmbeddingClient:
		return "http"
	case *embeddings.FastEmbedClient:
		return "fastembed"
	default:
		return fmt.Sprintf("%T", emb)
	}
}

// printVector prints up to eight vector components with an ellipsis when
// truncated, so the demo output stays single-line and copy-pasteable.
func printVector(v []float32) {
	const max = 8
	parts := make([]string, 0, max+1)
	for i := 0; i < len(v) && i < max; i++ {
		parts = append(parts, fmt.Sprintf("%.4f", v[i]))
	}
	if len(v) > max {
		parts = append(parts, "...")
	}
	fmt.Print("[" + strings.Join(parts, " ") + "]")
}

// stubEmbedder returns a deterministic EmbedderFunc that produces
// unit-norm-ish vectors suitable for smoke-testing.
func stubEmbedder(dim int) embeddings.EmbedderFunc {
	return func(texts []string) (embeddings.Encoding, error) {
		out := make(embeddings.Encoding, len(texts))
		for i, t := range texts {
			row := make([]float32, dim)
			for j := 0; j < dim; j++ {
				// Avoid zeros entirely so L2 normalisation has signal.
				row[j] = float32(((len(t)+i+j)%7)+1) / 10.0
			}
			out[i] = row
		}
		return out, nil
	}
}

// Defensive: keep io referenced for future streaming work.
var _ = io.Discard
