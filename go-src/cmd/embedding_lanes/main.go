// Command embedding_lanes is the Go port's binary entry point for the
// embedding_lanes package. It demonstrates the lane helpers end-to-end
// without needing a live Chroma or FastEmbed process: a built-in fake
// chroma + fake client is used unless the user supplies --chroma and
// --url flags.
//
// Usage:
//
//	embedding_lanes --base docs
//	embedding_lanes -base memory -dim 384 -model BAAI/bge-small-en
//
// The binary prints the resulting lane list as JSON, one lane per line.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/odysseus/odysseus/embedding_lanes"
)

// The package name is `embeddinglanes` (one word), matching Go's
// idiomatic lowercased-without-underscores style. We alias the import
// to the more readable `el` symbol for the rest of the file.

// fakeClient is a small deterministic client used when no real
// embedding backend is reachable. See embedding_lanes_test.go for the
// reference test implementation.
type fakeClient struct {
	dim   int
	model string
	url   string
}

func (f *fakeClient) Encode(texts []string) any {
	out := make([][]float64, len(texts))
	for i, t := range texts {
		v := make([]float64, f.dim)
		sum := 0
		for _, r := range t {
			sum += int(r)
		}
		for j := 0; j < f.dim; j++ {
			v[j] = float64(sum+j) / 1000.0
		}
		out[i] = v
	}
	return out
}
func (f *fakeClient) Dimension() int { return f.dim }
func (f *fakeClient) Model() string  { return f.model }
func (f *fakeClient) URL() string    { return f.url }

// inMemoryChroma is a minimal ChromaClient implementation backed by a
// map. It mirrors the behaviour of the Python chromadb client used in
// tests: GetCollection errors on miss; GetOrCreateCollection succeeds
// always.
type inMemoryChroma struct {
	cols map[string]inMemCollection
}

type inMemCollection struct {
	md   map[string]any
	rows map[string]inMemRow
}

type inMemRow struct {
	doc  string
	meta map[string]any
	emb  []float64
}

func newInMemoryChroma() *inMemoryChroma {
	return &inMemoryChroma{cols: map[string]inMemCollection{}}
}

func (c *inMemoryChroma) GetCollection(name string) (embeddinglanes.ChromaCollection, error) {
	if _, ok := c.cols[name]; !ok {
		return nil, fmt.Errorf("not found: %s", name)
	}
	return c.makeAdapter(name), nil
}

func (c *inMemoryChroma) GetOrCreateCollection(name string, metadata map[string]any) (embeddinglanes.ChromaCollection, error) {
	if _, ok := c.cols[name]; !ok {
		c.cols[name] = inMemCollection{md: copyMap(metadata), rows: map[string]inMemRow{}}
	} else {
		entry := c.cols[name]
		entry.md = copyMap(metadata)
		c.cols[name] = entry
	}
	return c.makeAdapter(name), nil
}

func (c *inMemoryChroma) DeleteCollection(name string) error {
	delete(c.cols, name)
	return nil
}

func (c *inMemoryChroma) makeAdapter(name string) embeddinglanes.ChromaCollection {
	entry := c.cols[name]
	col := &inMemAdapter{name: name, md: entry.md, rows: map[string]inMemRow{}}
	for k, v := range entry.rows {
		col.rows[k] = v
	}
	return col
}

type inMemAdapter struct {
	name string
	md   map[string]any
	rows map[string]inMemRow
}

func (a *inMemAdapter) Metadata() map[string]any { return copyMap(a.md) }
func (a *inMemAdapter) Count() (int, error)      { return len(a.rows), nil }
func (a *inMemAdapter) Get(args embeddinglanes.ChromaGetArgs) (embeddinglanes.ChromaGetResult, error) {
	res := embeddinglanes.ChromaGetResult{
		IDs:        []string{},
		Documents:  []string{},
		Metadatas:  []map[string]any{},
		Embeddings: [][]float64{},
	}
	if len(args.IDs) == 0 {
		for id, row := range a.rows {
			res.IDs = append(res.IDs, id)
			res.Documents = append(res.Documents, row.doc)
			res.Metadatas = append(res.Metadatas, copyMap(row.meta))
			res.Embeddings = append(res.Embeddings, append([]float64{}, row.emb...))
		}
		return res, nil
	}
	for _, id := range args.IDs {
		row, ok := a.rows[id]
		if !ok {
			continue
		}
		res.IDs = append(res.IDs, id)
		res.Documents = append(res.Documents, row.doc)
		res.Metadatas = append(res.Metadatas, copyMap(row.meta))
		res.Embeddings = append(res.Embeddings, append([]float64{}, row.emb...))
	}
	return res, nil
}

func (a *inMemAdapter) Add(args embeddinglanes.ChromaAddArgs) error {
	for i, id := range args.IDs {
		var doc string
		if i < len(args.Documents) {
			doc = args.Documents[i]
		}
		var md map[string]any
		if i < len(args.Metadatas) {
			md = copyMap(args.Metadatas[i])
		}
		var emb []float64
		if i < len(args.Embeddings) {
			emb = append([]float64{}, args.Embeddings[i]...)
		}
		a.rows[id] = inMemRow{doc: doc, meta: md, emb: emb}
	}
	return nil
}

func (a *inMemAdapter) Query(args embeddinglanes.ChromaQueryArgs) (embeddinglanes.ChromaQueryResult, error) {
	n := args.NResults
	if n <= 0 {
		n = len(a.rows)
	}
	ids := []string{}
	docs := []string{}
	metas := []map[string]any{}
	for id, row := range a.rows {
		if len(ids) >= n {
			break
		}
		ids = append(ids, id)
		docs = append(docs, row.doc)
		metas = append(metas, copyMap(row.meta))
	}
	return embeddinglanes.ChromaQueryResult{
		IDs:       [][]string{ids},
		Documents: [][]string{docs},
		Metadatas: [][]map[string]any{metas},
	}, nil
}

func copyMap(in map[string]any) map[string]any {
	if in == nil {
		return nil
	}
	out := make(map[string]any, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}

func main() {
	baseName := flag.String("base", "docs", "base collection name (suffix _fastembed/_custom appended per lane)")
	dim := flag.Int("dim", 384, "embedding dimensionality for the in-memory demo client")
	model := flag.String("model", "BAAI/bge-small-en", "embedding model identifier (recorded into the lane metadata)")
	url := flag.String("url", "", "custom-lane URL (empty disables the custom lane)")
	customDim := flag.Int("custom-dim", 0, "custom lane dimensionality (defaults to --dim)")
	customModel := flag.String("custom-model", "", "custom lane model identifier (defaults to --model)")
	query := flag.String("query", "", "if set, run QueryLanes and print the merged, deduped results")
	queryLimit := flag.Int("query-limit", 3, "max results to keep from QueryLanes")
	flag.Parse()

	cDim := *customDim
	if cDim <= 0 {
		cDim = *dim
	}
	cModel := *customModel
	if cModel == "" {
		cModel = *model
	}

	chroma := newInMemoryChroma()
	builders := embeddinglanes.ClientBuilders{
		FastEmbedBuilder: func() (embeddinglanes.EmbeddingClient, error) {
			return &fakeClient{dim: *dim, model: *model}, nil
		},
	}
	if *url != "" {
		builders.CustomBuilder = func() (embeddinglanes.EmbeddingClient, error) {
			return &fakeClient{dim: cDim, model: cModel, url: *url}, nil
		}
	}

	lanes := embeddinglanes.BuildLanes(chroma, *baseName, builders)

	fmt.Fprintf(os.Stderr, "built %d lane(s) for base=%q\n", len(lanes), *baseName)
	for _, l := range lanes {
		b, err := json.Marshal(l.Stats())
		if err != nil {
			fmt.Fprintf(os.Stderr, "marshal stats: %v\n", err)
			continue
		}
		fmt.Println(string(b))
	}

	if *query != "" {
		out, err := embeddinglanes.QueryLanes(
			lanes,
			*query,
			func(*embeddinglanes.EmbeddingLane) int { return *queryLimit },
			[]string{"documents"},
			nil,
			false,
		)
		if err != nil {
			fmt.Fprintf(os.Stderr, "query failed: %v\n", err)
			os.Exit(1)
		}
		merged := []map[string]any{}
		for _, r := range out {
			ids := r.Results.IDs
			if len(ids) == 0 {
				continue
			}
			for i, id := range ids[0] {
				row := map[string]any{
					"id":    id,
					"lane":  r.Lane.Name,
					"count": i,
				}
				merged = append(merged, row)
			}
		}
		deduped := embeddinglanes.DedupeResults(merged, "id", *queryLimit)
		b, _ := json.MarshalIndent(deduped, "", "  ")
		fmt.Fprintln(os.Stderr, "--- query results ---")
		fmt.Println(string(b))
	}
}
