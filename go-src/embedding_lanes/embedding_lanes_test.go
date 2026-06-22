// Tests for the embeddinglanes package. These exercise the pure
// helpers (collection name, fingerprint, dedupe) plus the lane-lifecycle
// code paths (re-embed on drift, legacy migration, query fan-out) using
// small in-memory fakes for the Chroma + embedding-client surfaces.
package embeddinglanes

import (
	"errors"
	"fmt"
	"reflect"
	"strings"
	"sync"
	"testing"
)

// ---------------------------------------------------------------------------
// Fake embedding client + chroma collection used across the tests.
// ---------------------------------------------------------------------------

// fakeClient is a deterministic EmbeddingClient: every text becomes a
// fixed-length vector derived from its rune sum.
type fakeClient struct {
	dim       int
	model     string
	url       string
	encodeErr error
}

func (f *fakeClient) Encode(texts []string) any {
	if f.encodeErr != nil {
		return f.encodeErr
	}
	out := make([][]float64, len(texts))
	for i, t := range texts {
		v := make([]float64, f.dim)
		// Spread the rune sum across the vector so different texts give
		// different vectors without needing randomness.
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

// fakeCollection stores rows + metadata in memory. It implements
// ChromaCollection and also exposes Metadata() so that
// readCollectionMetadata can recover the metadata.
type fakeCollection struct {
	mu        sync.Mutex
	name      string
	metadata  map[string]any
	rows      map[string]fakeRow // keyed by id
	countHook func() (int, error)
}

type fakeRow struct {
	doc       string
	metadata  map[string]any
	embedding []float64
}

func newFakeCollection(name string, metadata map[string]any) *fakeCollection {
	return &fakeCollection{
		name:     name,
		metadata: cloneMap(metadata),
		rows:     map[string]fakeRow{},
	}
}

func (c *fakeCollection) Metadata() map[string]any {
	c.mu.Lock()
	defer c.mu.Unlock()
	return cloneMap(c.metadata)
}

func (c *fakeCollection) Count() (int, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.countHook != nil {
		return c.countHook()
	}
	return len(c.rows), nil
}

func (c *fakeCollection) Get(args ChromaGetArgs) (ChromaGetResult, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	res := ChromaGetResult{IDs: []string{}, Documents: []string{}, Metadatas: []map[string]any{}, Embeddings: [][]float64{}}
	if len(args.IDs) == 0 {
		for id, row := range c.rows {
			res.IDs = append(res.IDs, id)
			res.Documents = append(res.Documents, row.doc)
			res.Metadatas = append(res.Metadatas, cloneMap(row.metadata))
			res.Embeddings = append(res.Embeddings, append([]float64{}, row.embedding...))
		}
		return res, nil
	}
	for _, id := range args.IDs {
		row, ok := c.rows[id]
		if !ok {
			continue
		}
		res.IDs = append(res.IDs, id)
		res.Documents = append(res.Documents, row.doc)
		res.Metadatas = append(res.Metadatas, cloneMap(row.metadata))
		res.Embeddings = append(res.Embeddings, append([]float64{}, row.embedding...))
	}
	return res, nil
}

func (c *fakeCollection) Add(args ChromaAddArgs) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	for i, id := range args.IDs {
		var doc string
		if i < len(args.Documents) {
			doc = args.Documents[i]
		}
		var md map[string]any
		if i < len(args.Metadatas) {
			md = cloneMap(args.Metadatas[i])
		}
		var emb []float64
		if i < len(args.Embeddings) {
			emb = append([]float64{}, args.Embeddings[i]...)
		}
		c.rows[id] = fakeRow{doc: doc, metadata: md, embedding: emb}
	}
	return nil
}

func (c *fakeCollection) Query(args ChromaQueryArgs) (ChromaQueryResult, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	n := args.NResults
	if n <= 0 {
		n = len(c.rows)
	}
	ids := make([]string, 0, n)
	docs := make([]string, 0, n)
	metas := make([]map[string]any, 0, n)
	for id, row := range c.rows {
		if len(ids) >= n {
			break
		}
		ids = append(ids, id)
		docs = append(docs, row.doc)
		metas = append(metas, cloneMap(row.metadata))
	}
	return ChromaQueryResult{
		IDs:       [][]string{ids},
		Documents: [][]string{docs},
		Metadatas: [][]map[string]any{metas},
	}, nil
}

// fakeChroma stores collections in a map keyed by name. Its
// GetOrCreateCollection and DeleteCollection behaviour match chromadb:
// GetCollection fails if the name is missing; DeleteCollection is a
// no-op if the name is missing.
type fakeChroma struct {
	mu          sync.Mutex
	cols        map[string]*fakeCollection
	createHooks []func(name string, md map[string]any)
}

func newFakeChroma() *fakeChroma {
	return &fakeChroma{cols: map[string]*fakeCollection{}}
}

func (c *fakeChroma) GetCollection(name string) (ChromaCollection, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	col, ok := c.cols[name]
	if !ok {
		return nil, errors.New("not found: " + name)
	}
	return col, nil
}

func (c *fakeChroma) GetOrCreateCollection(name string, metadata map[string]any) (ChromaCollection, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for _, h := range c.createHooks {
		h(name, metadata)
	}
	if col, ok := c.cols[name]; ok {
		col.mu.Lock()
		col.metadata = cloneMap(metadata)
		col.mu.Unlock()
		return col, nil
	}
	col := newFakeCollection(name, metadata)
	c.cols[name] = col
	return col, nil
}

func (c *fakeChroma) DeleteCollection(name string) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.cols, name)
	return nil
}

func (c *fakeChroma) snapshot(name string) *fakeCollection {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.cols[name]
}

func cloneMap(in map[string]any) map[string]any {
	if in == nil {
		return nil
	}
	out := make(map[string]any, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}

// ---------------------------------------------------------------------------
// Pure helpers.
// ---------------------------------------------------------------------------

func TestCollectionName(t *testing.T) {
	tests := []struct {
		base, lane, want string
	}{
		{"docs", LaneFastEmbed, "docs_fastembed"},
		{"docs", LaneCustom, "docs_custom"},
		{"memory", "weird lane", "memory_weird lane"},
	}
	for _, tc := range tests {
		got := CollectionName(tc.base, tc.lane)
		if got != tc.want {
			t.Errorf("CollectionName(%q,%q) = %q, want %q", tc.base, tc.lane, got, tc.want)
		}
	}
}

func TestFingerprintStable(t *testing.T) {
	a := Fingerprint(LaneFastEmbed, "local", "BAAI/bge-small-en", 384)
	b := Fingerprint(LaneFastEmbed, "local", "BAAI/bge-small-en", 384)
	if a != b {
		t.Fatalf("fingerprint changed between identical calls: %q vs %q", a, b)
	}
	if len(a) != 16 {
		t.Errorf("fingerprint length = %d, want 16 hex chars", len(a))
	}
}

func TestFingerprintDiffersOnChange(t *testing.T) {
	base := Fingerprint(LaneFastEmbed, "local", "BAAI/bge-small-en", 384)
	cases := []struct {
		name       string
		url, model string
		dim        int
	}{
		{"different url", "remote", "BAAI/bge-small-en", 384},
		{"different model", "local", "BAAI/bge-large-en", 384},
		{"different dim", "local", "BAAI/bge-small-en", 768},
		{"different lane", "local", "BAAI/bge-small-en", 384},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := Fingerprint(tc.name, tc.url, tc.model, tc.dim)
			if got == base {
				t.Errorf("fingerprint should differ when %s changes (got %q)", tc.name, got)
			}
		})
	}
}

func TestMetadataShape(t *testing.T) {
	md := Metadata(LaneFastEmbed, "local", "BAAI/bge-small-en", 384, "deadbeefdeadbeef")
	want := map[string]any{
		"hnsw:space":            "cosine",
		"embedding_lane":        LaneFastEmbed,
		"embedding_url":         "local",
		"embedding_model":       "BAAI/bge-small-en",
		"embedding_dimension":   384,
		"embedding_fingerprint": "deadbeefdeadbeef",
	}
	if !reflect.DeepEqual(md, want) {
		t.Errorf("Metadata = %#v, want %#v", md, want)
	}
}

// ---------------------------------------------------------------------------
// Lane + Encode + Stats.
// ---------------------------------------------------------------------------

func TestEncodeTexts(t *testing.T) {
	c := &fakeClient{dim: 4}
	got, err := EncodeTexts(c, []string{"hello", "world"})
	if err != nil {
		t.Fatalf("EncodeTexts error: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("got %d rows, want 2", len(got))
	}
	for i, row := range got {
		if len(row) != 4 {
			t.Errorf("row %d length = %d, want 4", i, len(row))
		}
	}
}

func TestEncodeTextsToListAdapter(t *testing.T) {
	// Confirm that a client returning a ToListConverter-shaped value is
	// properly unwrapped, matching the Python `hasattr(vecs, "tolist")`
	// branch.
	type toListShape struct {
		v [][]float64
	}
	adapter := struct {
		EmbeddingClient
	}{}
	_ = adapter // silence unused

	// Build a one-off implementation of ToListConverter via the
	// interface contract; the wrapper Encode function only reads
	// `ToList() [][]float64`.
	wrapper := toListValue{v: [][]float64{{1, 2, 3}, {4, 5, 6}}}
	got, err := EncodeTexts(&toListClient{w: wrapper}, []string{"a", "b"})
	if err != nil {
		t.Fatalf("EncodeTexts error: %v", err)
	}
	if !reflect.DeepEqual(got, wrapper.v) {
		t.Errorf("EncodeTexts returned %#v, want %#v", got, wrapper.v)
	}
}

func TestEncodeTextsUnsupported(t *testing.T) {
	c := &stringSliceClient{}
	if _, err := EncodeTexts(c, []string{"a"}); err == nil {
		t.Fatal("expected error for unsupported Encode result, got nil")
	}
}

type toListValue struct{ v [][]float64 }

func (t toListValue) ToList() [][]float64 { return t.v }

type toListClient struct{ w toListValue }

func (t *toListClient) Encode(_ []string) any { return t.w }
func (t *toListClient) Dimension() int        { return len(t.w.v[0]) }
func (t *toListClient) Model() string         { return "tolist" }
func (t *toListClient) URL() string           { return "" }

type stringSliceClient struct{}

func (s *stringSliceClient) Encode(_ []string) any { return []string{"not a vector"} }
func (s *stringSliceClient) Dimension() int        { return 0 }
func (s *stringSliceClient) Model() string         { return "" }
func (s *stringSliceClient) URL() string           { return "" }

func TestLaneHealthyAndStats(t *testing.T) {
	chroma := newFakeChroma()
	client := &fakeClient{dim: 8, model: "m", url: "u"}
	lane, err := CreateLane(chroma, "kb", LaneFastEmbed, client)
	if err != nil {
		t.Fatalf("CreateLane: %v", err)
	}
	if !lane.Healthy() {
		t.Error("expected fresh lane to be healthy")
	}
	stats := lane.Stats()
	for _, key := range []string{"name", "collection", "model", "url", "dimension", "fingerprint", "count", "healthy"} {
		if _, ok := stats[key]; !ok {
			t.Errorf("Stats missing key %q", key)
		}
	}
	if stats["name"] != LaneFastEmbed {
		t.Errorf("Stats[name] = %v, want %q", stats["name"], LaneFastEmbed)
	}

	// After dropping the collection, Healthy should turn false but Stats
	// should still be callable. The fake chroma keeps a reference to
	// the deleted collection in our lane struct, so simulate the
	// external reference by hand instead of using the lane's pointer.
	if err := chroma.DeleteCollection(lane.CollectionName); err != nil {
		t.Fatalf("DeleteCollection: %v", err)
	}
	lane.Collection = nil
	if lane.Healthy() {
		t.Error("lane should not be healthy after collection was deleted")
	}
	stats2 := lane.Stats()
	if stats2["healthy"] != false {
		t.Errorf("expected stats2 healthy=false, got %v", stats2["healthy"])
	}
}

func TestLaneCountErrorsSilently(t *testing.T) {
	c := newFakeCollection("foo", nil)
	c.countHook = func() (int, error) { return 0, errors.New("kaboom") }
	lane := &EmbeddingLane{Name: "x", Collection: c, Client: &fakeClient{dim: 4}}
	if got := lane.Count(); got != 0 {
		t.Errorf("Count = %d, want 0", got)
	}
}

// ---------------------------------------------------------------------------
// Collection drift + reset.
// ---------------------------------------------------------------------------

func TestGetOrResetCollectionFresh(t *testing.T) {
	chroma := newFakeChroma()
	client := &fakeClient{dim: 4, model: "m", url: "u"}
	md := Metadata(LaneFastEmbed, "u", "m", 4, Fingerprint(LaneFastEmbed, "u", "m", 4))
	col, err := GetOrResetCollection(chroma, client, "x", md)
	if err != nil {
		t.Fatalf("GetOrResetCollection: %v", err)
	}
	if col == nil {
		t.Fatal("expected non-nil collection")
	}
	if got := chroma.snapshot("x"); got == nil {
		t.Fatal("expected collection to be created in chroma")
	}
}

func TestGetOrResetCollectionNoDrift(t *testing.T) {
	chroma := newFakeChroma()
	client := &fakeClient{dim: 4, model: "m", url: "u"}
	md := Metadata(LaneFastEmbed, "u", "m", 4, Fingerprint(LaneFastEmbed, "u", "m", 4))
	if _, err := GetOrResetCollection(chroma, client, "x", md); err != nil {
		t.Fatalf("first Create: %v", err)
	}
	// Pre-populate the collection with a row so we can verify it survives.
	first, _ := chroma.GetCollection("x")
	if err := first.Add(ChromaAddArgs{
		IDs:        []string{"row1"},
		Documents:  []string{"hello"},
		Metadatas:  []map[string]any{{"src": "orig"}},
		Embeddings: [][]float64{{1, 2, 3, 4}},
	}); err != nil {
		t.Fatalf("seed Add: %v", err)
	}

	// Same fingerprint → no recreation, no re-embed.
	createCount := 0
	chroma.createHooks = append(chroma.createHooks, func(string, map[string]any) {
		createCount++
	})
	if _, err := GetOrResetCollection(chroma, client, "x", md); err != nil {
		t.Fatalf("second GetOrReset: %v", err)
	}
	if createCount != 0 {
		t.Errorf("expected zero recreations on no-drift, got %d", createCount)
	}
	res, _ := first.Get(ChromaGetArgs{IDs: []string{"row1"}})
	if len(res.IDs) != 1 || res.Documents[0] != "hello" {
		t.Errorf("row was disturbed on no-drift reset: %+v", res)
	}
}

func TestGetOrResetCollectionRecreatesOnDrift(t *testing.T) {
	chroma := newFakeChroma()
	client := &fakeClient{dim: 4, model: "m", url: "u"}
	md1 := Metadata(LaneFastEmbed, "u", "m", 4, Fingerprint(LaneFastEmbed, "u", "m", 4))
	if _, err := GetOrResetCollection(chroma, client, "x", md1); err != nil {
		t.Fatalf("seed: %v", err)
	}
	first, _ := chroma.GetCollection("x")
	if err := first.Add(ChromaAddArgs{
		IDs:        []string{"row1", "row2"},
		Documents:  []string{"hello", "world"},
		Metadatas:  []map[string]any{{"k": "v"}, {"k": "v"}},
		Embeddings: [][]float64{{1, 2, 3, 4}, {5, 6, 7, 8}},
	}); err != nil {
		t.Fatalf("seed add: %v", err)
	}

	md2 := Metadata(LaneFastEmbed, "u", "m2", 4, Fingerprint(LaneFastEmbed, "u", "m2", 4))
	if _, err := GetOrResetCollection(chroma, client, "x", md2); err != nil {
		t.Fatalf("reset: %v", err)
	}
	// The collection should have been recreated and re-populated.
	col := chroma.snapshot("x")
	if col == nil {
		t.Fatal("collection missing after reset")
	}
	md := col.Metadata()
	if md["embedding_model"] != "m2" {
		t.Errorf("metadata embedding_model = %v, want m2", md["embedding_model"])
	}
	if n, _ := col.Count(); n != 2 {
		t.Errorf("after re-embed: Count = %d, want 2", n)
	}
	res, _ := col.Get(ChromaGetArgs{IDs: []string{"row1", "row2"}})
	if len(res.IDs) != 2 {
		t.Errorf("expected 2 rows after re-embed, got %d", len(res.IDs))
	}
}

// ---------------------------------------------------------------------------
// BuildLanes (custom + fastembed).
// ---------------------------------------------------------------------------

func TestBuildLanesPreferenceOrder(t *testing.T) {
	chroma := newFakeChroma()
	custom := &fakeClient{dim: 16, model: "custom-m", url: "http://custom"}
	fastembed := &fakeClient{dim: 4, model: "fe-m", url: ""}
	builders := ClientBuilders{
		CustomBuilder:    func() (EmbeddingClient, error) { return custom, nil },
		FastEmbedBuilder: func() (EmbeddingClient, error) { return fastembed, nil },
	}
	lanes := BuildLanes(chroma, "kb", builders)
	if len(lanes) != 2 {
		t.Fatalf("len(lanes) = %d, want 2", len(lanes))
	}
	if lanes[0].Name != LaneCustom || lanes[1].Name != LaneFastEmbed {
		t.Errorf("lane order = [%q, %q], want [custom, fastembed]", lanes[0].Name, lanes[1].Name)
	}
}

func TestBuildLanesSkipsUnavailable(t *testing.T) {
	chroma := newFakeChroma()
	// Custom lane blows up; fastembed lane builder returns nil client.
	builders := ClientBuilders{
		CustomBuilder:    func() (EmbeddingClient, error) { return nil, errors.New("nope") },
		FastEmbedBuilder: func() (EmbeddingClient, error) { return nil, nil },
	}
	lanes := BuildLanes(chroma, "kb", builders)
	if len(lanes) != 0 {
		t.Errorf("expected no lanes when builders all fail/return nil, got %d", len(lanes))
	}
}

func TestBuildLanesNilChroma(t *testing.T) {
	lanes := BuildLanes(nil, "kb", ClientBuilders{
		CustomBuilder:    func() (EmbeddingClient, error) { return &fakeClient{dim: 4}, nil },
		FastEmbedBuilder: func() (EmbeddingClient, error) { return &fakeClient{dim: 4}, nil },
	})
	if lanes != nil {
		t.Errorf("expected nil lanes for nil chroma, got %v", lanes)
	}
}

// ---------------------------------------------------------------------------
// Legacy migration.
// ---------------------------------------------------------------------------

func TestMigrateLegacyCollection(t *testing.T) {
	chroma := newFakeChroma()
	// Seed the legacy collection with three rows.
	legacy, err := chroma.GetOrCreateCollection("kb", Metadata(LaneCustom, "", "m", 4, "fp"))
	if err != nil {
		t.Fatalf("create legacy: %v", err)
	}
	if err := legacy.Add(ChromaAddArgs{
		IDs:        []string{"a", "b", "c"},
		Documents:  []string{"alpha", "beta", "gamma"},
		Metadatas:  []map[string]any{{"src": "old"}, {"src": "old"}, {}},
		Embeddings: [][]float64{{1, 1, 1, 1}, {2, 2, 2, 2}, {3, 3, 3, 3}},
	}); err != nil {
		t.Fatalf("seed legacy: %v", err)
	}
	// Set up an empty fastembed lane and pre-populate it with one of the
	// legacy ids so we can verify the migration skips existing rows.
	lane, err := CreateLane(chroma, "kb", LaneFastEmbed, &fakeClient{dim: 4, model: "m"})
	if err != nil {
		t.Fatalf("CreateLane: %v", err)
	}
	if err := lane.Collection.Add(ChromaAddArgs{
		IDs:        []string{"a"},
		Documents:  []string{"alpha"},
		Metadatas:  []map[string]any{{"pre": "1"}},
		Embeddings: [][]float64{{1, 1, 1, 1}},
	}); err != nil {
		t.Fatalf("prepopulate: %v", err)
	}

	MigrateLegacyCollection(chroma, "kb", []*EmbeddingLane{lane})

	res, _ := lane.Collection.Get(ChromaGetArgs{IDs: []string{"a", "b", "c"}})
	if len(res.IDs) != 3 {
		t.Errorf("after migration expected 3 ids, got %d (%v)", len(res.IDs), res.IDs)
	}
}

func TestMigrateLegacyNoLegacy(t *testing.T) {
	chroma := newFakeChroma()
	lane, err := CreateLane(chroma, "kb", LaneFastEmbed, &fakeClient{dim: 4, model: "m"})
	if err != nil {
		t.Fatalf("CreateLane: %v", err)
	}
	// Should not panic or error when no legacy collection exists.
	MigrateLegacyCollection(chroma, "kb", []*EmbeddingLane{lane})
	if n, _ := lane.Collection.Count(); n != 0 {
		t.Errorf("expected lane count 0 (no legacy), got %d", n)
	}
}

// ---------------------------------------------------------------------------
// LaneCount + DedupeResults.
// ---------------------------------------------------------------------------

func TestLaneCount(t *testing.T) {
	lanes := []*EmbeddingLane{
		{Collection: newFakeCollectionWithRows(3)},
		{Collection: newFakeCollectionWithRows(7)},
		{Collection: newFakeCollectionWithRows(0)},
	}
	if got := LaneCount(lanes); got != 7 {
		t.Errorf("LaneCount = %d, want 7", got)
	}
	if got := LaneCount(nil); got != 0 {
		t.Errorf("LaneCount(nil) = %d, want 0", got)
	}
}

func TestDedupeResults(t *testing.T) {
	rows := []map[string]any{
		{"id": "a", "v": 1},
		{"id": "b", "v": 2},
		{"id": "a", "v": 99}, // duplicate
		{"id": "", "v": 3},   // empty id skipped
		{"v": 4},             // missing id skipped
		{"id": "c", "v": 5},
		{"id": "d", "v": 6},
	}
	got := DedupeResults(rows, "id", 0)
	if len(got) != 4 {
		t.Fatalf("len = %d, want 4 (a, b, c, d)", len(got))
	}
	for i, want := range []string{"a", "b", "c", "d"} {
		if got[i]["id"] != want {
			t.Errorf("got[%d].id = %v, want %v", i, got[i]["id"], want)
		}
	}

	// Limit truncates after `limit` unique rows.
	limited := DedupeResults(rows, "id", 2)
	if len(limited) != 2 {
		t.Errorf("limited len = %d, want 2", len(limited))
	}
}

func TestDedupeResultsCustomKey(t *testing.T) {
	rows := []map[string]any{
		{"uid": "x"},
		{"uid": "y"},
		{"uid": "x"},
	}
	got := DedupeResults(rows, "uid", 0)
	if len(got) != 2 {
		t.Errorf("len = %d, want 2", len(got))
	}
}

// ---------------------------------------------------------------------------
// QueryLanes.
// ---------------------------------------------------------------------------

func TestQueryLanes(t *testing.T) {
	chroma := newFakeChroma()
	client := &fakeClient{dim: 4, model: "m"}
	lane, err := CreateLane(chroma, "kb", LaneFastEmbed, client)
	if err != nil {
		t.Fatalf("CreateLane: %v", err)
	}
	if err := lane.Collection.Add(ChromaAddArgs{
		IDs:        []string{"r1", "r2"},
		Documents:  []string{"d1", "d2"},
		Metadatas:  []map[string]any{{}, {}},
		Embeddings: [][]float64{{1, 0, 0, 0}, {0, 1, 0, 0}},
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	out, err := QueryLanes(
		[]*EmbeddingLane{lane},
		"hello",
		func(*EmbeddingLane) int { return 5 },
		[]string{"documents"},
		nil,
		false,
	)
	if err != nil {
		t.Fatalf("QueryLanes: %v", err)
	}
	if len(out) != 1 {
		t.Fatalf("len(out) = %d, want 1", len(out))
	}
	if got := len(out[0].Results.IDs[0]); got != 2 {
		t.Errorf("results = %d ids, want 2", got)
	}
}

func TestQueryLanesSkipsEmpty(t *testing.T) {
	chroma := newFakeChroma()
	empty, _ := CreateLane(chroma, "kb", LaneFastEmbed, &fakeClient{dim: 4, model: "m"})
	populated, _ := CreateLane(chroma, "kb2", LaneFastEmbed, &fakeClient{dim: 4, model: "m"})
	if err := populated.Collection.Add(ChromaAddArgs{
		IDs:        []string{"x"},
		Documents:  []string{"y"},
		Metadatas:  []map[string]any{{}},
		Embeddings: [][]float64{{1, 1, 1, 1}},
	}); err != nil {
		t.Fatalf("seed: %v", err)
	}
	out, err := QueryLanes(
		[]*EmbeddingLane{empty, populated},
		"q",
		func(*EmbeddingLane) int { return 3 },
		[]string{"documents"},
		nil,
		false,
	)
	if err != nil {
		t.Fatalf("QueryLanes: %v", err)
	}
	if len(out) != 1 || out[0].Lane.Name != LaneFastEmbed {
		t.Errorf("expected one result on the populated lane, got %+v", out)
	}
}

func TestQueryLanesRaiseIfAllFailed(t *testing.T) {
	// A lane whose collection always errors on Query.
	bad := newFakeCollection("bad", nil)
	bad.countHook = func() (int, error) { return 1, nil }
	// Replace Query with a method that always errors via the interface
	// by wrapping in a struct that satisfies ChromaCollection.
	badQuery := &errQueryCollection{fakeCollection: bad}
	lane := &EmbeddingLane{
		Name:           "bad",
		Client:         &fakeClient{dim: 4, model: "m"},
		Collection:     badQuery,
		CollectionName: "bad",
	}
	out, err := QueryLanes(
		[]*EmbeddingLane{lane},
		"q",
		func(*EmbeddingLane) int { return 5 },
		[]string{"documents"},
		nil,
		true,
	)
	if err == nil {
		t.Fatal("expected error when raise_if_all_failed=true and all queries failed")
	}
	if !strings.Contains(err.Error(), "bad:") {
		t.Errorf("error %q should mention the failing lane", err.Error())
	}
	if len(out) != 0 {
		t.Errorf("out should be empty on all-fail, got %d", len(out))
	}
}

type errQueryCollection struct{ *fakeCollection }

func (e *errQueryCollection) Query(args ChromaQueryArgs) (ChromaQueryResult, error) {
	return ChromaQueryResult{}, errors.New("query boom")
}

// ---------------------------------------------------------------------------
// ResetState + hook.
// ---------------------------------------------------------------------------

func TestResetStateCallsHook(t *testing.T) {
	called := 0
	prev := ResetHook
	defer func() { ResetHook = prev }()
	ResetHook = func() { called++ }
	ResetState()
	if called != 1 {
		t.Errorf("ResetHook called %d times, want 1", called)
	}
	// ResetState must not panic when the hook itself panics (mirrors the
	// Python except-clause that swallows errors).
	ResetHook = func() { panic("kaboom") }
	ResetState()
}

// ---------------------------------------------------------------------------
// CreateLane nil guards.
// ---------------------------------------------------------------------------

func TestCreateLaneNilGuards(t *testing.T) {
	if _, err := CreateLane(nil, "kb", LaneFastEmbed, &fakeClient{dim: 4}); err == nil {
		t.Error("expected error for nil chroma")
	}
	if _, err := CreateLane(newFakeChroma(), "kb", LaneFastEmbed, nil); err == nil {
		t.Error("expected error for nil client")
	}
}

// ---------------------------------------------------------------------------
// EncodeTexts nil client guard.
// ---------------------------------------------------------------------------

func TestEncodeTextsNilClient(t *testing.T) {
	if _, err := EncodeTexts(nil, []string{"a"}); err == nil {
		t.Error("expected error for nil client")
	}
}

// ---------------------------------------------------------------------------
// CollectionDrift semantics.
// ---------------------------------------------------------------------------

func TestCollectionDrift(t *testing.T) {
	base := map[string]any{
		"embedding_fingerprint": "fp",
		"embedding_dimension":   4,
		"embedding_lane":        LaneFastEmbed,
	}
	if collectionDrift(base, base) {
		t.Error("identical metadata should not be reported as drift")
	}
	if !collectionDrift(nil, base) {
		t.Error("nil current should be drift (no existing metadata to compare)")
	}
	if !collectionDrift(
		map[string]any{"embedding_fingerprint": "OTHER"},
		base,
	) {
		t.Error("mismatched fingerprint should be drift")
	}
}

// ---------------------------------------------------------------------------
// helpers for tests.
// ---------------------------------------------------------------------------

func newFakeCollectionWithRows(n int) *fakeCollection {
	c := newFakeCollection("c", nil)
	for i := 0; i < n; i++ {
		_ = c.Add(ChromaAddArgs{
			IDs:        []string{fmt.Sprintf("id-%d", i)},
			Documents:  []string{fmt.Sprintf("doc-%d", i)},
			Metadatas:  []map[string]any{{}},
			Embeddings: [][]float64{{0, 0, 0, 0}},
		})
	}
	return c
}
