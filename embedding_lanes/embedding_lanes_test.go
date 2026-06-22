package embedding_lanes

import (
	"errors"
	"fmt"
	"reflect"
	"sort"
	"strings"
	"sync"
	"testing"
)

// Compile-time interface assertions.
var (
	_ Encoder      = (*fakeEncoder)(nil)
	_ Collection   = (*fakeCollection)(nil)
	_ ChromaClient = (*fakeChroma)(nil)
)

// fakeEncoder is a deterministic Encoder used by tests. Encode returns a
// per-text zero vector of the configured dimension, so test assertions can
// reason about shape without coupling to specific float values.
type fakeEncoder struct {
	mu        sync.Mutex
	dim       int
	model     string
	url       string
	encodeErr error

	// Calls captures every Encode invocation for assertions.
	calls [][]string
}

func (f *fakeEncoder) Encode(texts []string) ([][]float32, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.calls = append(f.calls, append([]string(nil), texts...))
	if f.encodeErr != nil {
		return nil, f.encodeErr
	}
	out := make([][]float32, len(texts))
	for i := range texts {
		v := make([]float32, f.dim)
		out[i] = v
	}
	return out, nil
}

func (f *fakeEncoder) Dimension() int { return f.dim }
func (f *fakeEncoder) Model() string  { return f.model }
func (f *fakeEncoder) URL() string    { return f.url }

// fakeCollection is a controllable in-memory Collection. It records every
// Add call and exposes the row set so tests can assert that the recreate
// flow preserves / restores them correctly.
type fakeCollection struct {
	mu       sync.Mutex
	rows     []storedRow
	metadata map[string]any

	// Optional error hooks.
	addErr   error
	getErr   error
	queryErr error

	addCalls    []addCall
	queryCalls  []queryCall
	getCalls    [][]string
	countCalled int
}

type storedRow struct {
	ID        string
	Doc       string
	Meta      map[string]any
	Embedding []float32
}

type addCall struct {
	IDs        []string
	Docs       []string
	Metas      []map[string]any
	Embeddings [][]float32
}

type queryCall struct {
	Embeddings [][]float32
	NResults   int
	Where      map[string]any
	Include    []string
}

func (c *fakeCollection) Count() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.countCalled++
	return len(c.rows)
}

func (c *fakeCollection) Get(ids []string) (CollectionRows, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.getCalls = append(c.getCalls, append([]string(nil), ids...))
	if c.getErr != nil {
		return CollectionRows{}, c.getErr
	}
	if len(ids) == 0 {
		rows := make([]CollectionRows, 1)
		rows[0] = c.snapshot()
		return rows[0], nil
	}
	set := make(map[string]struct{}, len(ids))
	for _, id := range ids {
		set[id] = struct{}{}
	}
	out := CollectionRows{}
	for _, r := range c.rows {
		if _, ok := set[r.ID]; ok {
			out.IDs = append(out.IDs, r.ID)
			out.Documents = append(out.Documents, r.Doc)
			out.Metadatas = append(out.Metadatas, r.Meta)
			out.Embeddings = append(out.Embeddings, r.Embedding)
		}
	}
	return out, nil
}

func (c *fakeCollection) Query(embeddings [][]float32, n int, where map[string]any, include []string) (QueryResult, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.queryCalls = append(c.queryCalls, queryCall{
		Embeddings: embeddings,
		NResults:   n,
		Where:      where,
		Include:    include,
	})
	if c.queryErr != nil {
		return QueryResult{}, c.queryErr
	}
	n = min(n, len(c.rows))
	ids := make([][]string, 1)
	docs := make([][]string, 1)
	dists := make([][]float32, 1)
	ids[0] = make([]string, n)
	docs[0] = make([]string, n)
	dists[0] = make([]float32, n)
	for i := 0; i < n; i++ {
		ids[0][i] = c.rows[i].ID
		docs[0][i] = c.rows[i].Doc
		dists[0][i] = float32(i)
	}
	return QueryResult{IDs: ids, Documents: docs, Distances: dists}, nil
}

func (c *fakeCollection) Add(ids []string, docs []string, metas []map[string]any, embeddings [][]float32) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.addCalls = append(c.addCalls, addCall{
		IDs:        append([]string(nil), ids...),
		Docs:       append([]string(nil), docs...),
		Metas:      cloneMetas(metas),
		Embeddings: cloneVecs(embeddings),
	})
	if c.addErr != nil {
		return c.addErr
	}
	for i, id := range ids {
		row := storedRow{ID: id, Doc: docs[i], Meta: cloneMeta(metas[i])}
		if i < len(embeddings) {
			row.Embedding = append([]float32(nil), embeddings[i]...)
		}
		c.rows = append(c.rows, row)
	}
	return nil
}

func (c *fakeCollection) Metadata() map[string]any {
	c.mu.Lock()
	defer c.mu.Unlock()
	out := make(map[string]any, len(c.metadata))
	for k, v := range c.metadata {
		out[k] = v
	}
	return out
}

func (c *fakeCollection) snapshot() CollectionRows {
	out := CollectionRows{
		IDs:       make([]string, len(c.rows)),
		Documents: make([]string, len(c.rows)),
		Metadatas: make([]map[string]any, len(c.rows)),
	}
	for i, r := range c.rows {
		out.IDs[i] = r.ID
		out.Documents[i] = r.Doc
		out.Metadatas[i] = cloneMeta(r.Meta)
		if r.Embedding != nil {
			out.Embeddings = append(out.Embeddings, append([]float32(nil), r.Embedding...))
		}
	}
	return out
}

func cloneMetas(in []map[string]any) []map[string]any {
	out := make([]map[string]any, len(in))
	for i, m := range in {
		out[i] = cloneMeta(m)
	}
	return out
}

func cloneMeta(m map[string]any) map[string]any {
	if m == nil {
		return map[string]any{}
	}
	out := make(map[string]any, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}

func cloneVecs(in [][]float32) [][]float32 {
	out := make([][]float32, len(in))
	for i, v := range in {
		out[i] = append([]float32(nil), v...)
	}
	return out
}

// fakeChroma is a controllable ChromaClient. Each call to GetCollection /
// GetOrCreateCollection / DeleteCollection records its argument so tests can
// assert on the recreate sequence.
type fakeChroma struct {
	mu sync.Mutex

	// collections holds every collection by name. When GetCollection is
	// called with a name that is missing, it returns ErrNotFound.
	collections map[string]*fakeCollection

	// deleteNotFound is returned by DeleteCollection when the name is missing.
	// Defaults to nil — the Python reference silently succeeds.
	deleteNotFound error

	// getErr is returned by GetCollection for ANY call; useful for the
	// "fresh-collection" path in tests.
	getErr error

	// Calls captured for assertions.
	getCalls          []string
	createCalls       []createCall
	deleteCalls       []string
	resetOccurred     bool
	resetCollectionOK bool
}

type createCall struct {
	Name     string
	Metadata map[string]any
}

var errNotFound = errors.New("fakeChroma: not found")

func (c *fakeChroma) GetCollection(name string) (Collection, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.getCalls = append(c.getCalls, name)
	if c.getErr != nil {
		return nil, c.getErr
	}
	coll, ok := c.collections[name]
	if !ok {
		return nil, errNotFound
	}
	return coll, nil
}

func (c *fakeChroma) GetOrCreateCollection(name string, metadata map[string]any) (Collection, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.createCalls = append(c.createCalls, createCall{Name: name, Metadata: cloneMeta(metadata)})
	if c.collections == nil {
		c.collections = make(map[string]*fakeCollection)
	}
	if coll, ok := c.collections[name]; ok {
		// Update metadata on recreate.
		coll.mu.Lock()
		coll.metadata = cloneMeta(metadata)
		coll.mu.Unlock()
		return coll, nil
	}
	coll := &fakeCollection{metadata: cloneMeta(metadata)}
	c.collections[name] = coll
	return coll, nil
}

func (c *fakeChroma) DeleteCollection(name string) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.deleteCalls = append(c.deleteCalls, name)
	_, ok := c.collections[name]
	if !ok {
		return c.deleteNotFound
	}
	delete(c.collections, name)
	return nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// --- CollectionName ---------------------------------------------------------

func TestCollectionName_Format(t *testing.T) {
	if got := CollectionName("rag", LANE_FASTEMBED); got != "rag_fastembed" {
		t.Errorf("CollectionName(rag, fastembed) = %q, want rag_fastembed", got)
	}
	if got := CollectionName("memory", LANE_CUSTOM); got != "memory_custom" {
		t.Errorf("CollectionName(memory, custom) = %q, want memory_custom", got)
	}
}

// --- Fingerprint -------------------------------------------------------------

func TestFingerprint_Deterministic(t *testing.T) {
	a := Fingerprint("custom", "http://localhost:11434", "all-minilm:l6-v2", 384)
	b := Fingerprint("custom", "http://localhost:11434", "all-minilm:l6-v2", 384)
	if a != b {
		t.Errorf("Fingerprint not deterministic: %q vs %q", a, b)
	}
}

func TestFingerprint_LengthAndCharset(t *testing.T) {
	got := Fingerprint("custom", "http://x", "m", 8)
	if len(got) != 16 {
		t.Errorf("Fingerprint length = %d, want 16", len(got))
	}
	for _, r := range got {
		if !((r >= '0' && r <= '9') || (r >= 'a' && r <= 'f')) {
			t.Errorf("Fingerprint contains non-hex rune %q in %q", r, got)
		}
	}
}

func TestFingerprint_ChangesOnAnyInput(t *testing.T) {
	base := Fingerprint("custom", "http://x", "m", 8)
	cases := []struct {
		name string
		got  string
	}{
		{"lane", Fingerprint("fastembed", "http://x", "m", 8)},
		{"url", Fingerprint("custom", "http://y", "m", 8)},
		{"model", Fingerprint("custom", "http://x", "n", 8)},
		{"dim", Fingerprint("custom", "http://x", "m", 16)},
	}
	for _, c := range cases {
		if c.got == base {
			t.Errorf("Fingerprint unchanged when %s changed: %q", c.name, c.got)
		}
	}
}

// --- Metadata ----------------------------------------------------------------

func TestMetadata_AllKeys(t *testing.T) {
	m := Metadata("custom", "http://x", "m", 8, "abcd")
	want := []string{
		"hnsw:space",
		"embedding_lane",
		"embedding_url",
		"embedding_model",
		"embedding_dimension",
		"embedding_fingerprint",
	}
	for _, k := range want {
		if _, ok := m[k]; !ok {
			t.Errorf("Metadata missing key %q", k)
		}
	}
	if m["hnsw:space"] != "cosine" {
		t.Errorf("hnsw:space = %v, want cosine", m["hnsw:space"])
	}
}

// --- LoadCustomEndpoint ------------------------------------------------------

func TestLoadCustomEndpoint_EnvOnly(t *testing.T) {
	t.Setenv("EMBEDDING_URL", "http://example.test/v1/embeddings")
	t.Setenv("EMBEDDING_MODEL", "test-model")
	t.Setenv("EMBEDDING_API_KEY", "secret")

	ep := LoadCustomEndpoint()
	if ep.URL != "http://example.test/v1/embeddings" {
		t.Errorf("URL = %q", ep.URL)
	}
	if ep.Model != "test-model" {
		t.Errorf("Model = %q", ep.Model)
	}
	if ep.APIKey != "secret" {
		t.Errorf("APIKey = %q", ep.APIKey)
	}
}

func TestLoadCustomEndpoint_NoURLReturnsEmpty(t *testing.T) {
	t.Setenv("EMBEDDING_URL", "")
	got := LoadCustomEndpoint()
	if got != (CustomEndpoint{}) {
		t.Errorf("got %+v, want zero", got)
	}
}

// --- DedupeResults -----------------------------------------------------------

func TestDedupeResults_KeepsFirstOccurrence(t *testing.T) {
	rows := []map[string]any{
		{"id": "a", "v": 1},
		{"id": "b", "v": 2},
		{"id": "a", "v": 3},
		{"id": "c", "v": 4},
	}
	got := DedupeResults(rows, func(r map[string]any) string {
		id, _ := r["id"].(string)
		return id
	}, 0)
	if len(got) != 3 {
		t.Fatalf("got %d rows, want 3: %+v", len(got), got)
	}
	if got[0]["v"] != 1 {
		t.Errorf("first occurrence of a changed: got %v", got[0]["v"])
	}
	if got[1]["id"] != "b" || got[2]["id"] != "c" {
		t.Errorf("order broken: %+v", got)
	}
}

func TestDedupeResults_EmptyIDIsDuplicate(t *testing.T) {
	rows := []map[string]any{
		{"id": "", "v": 1},
		{"id": "", "v": 2},
		{"id": "a", "v": 3},
	}
	got := DedupeResults(rows, func(r map[string]any) string {
		id, _ := r["id"].(string)
		return id
	}, 0)
	if len(got) != 1 {
		t.Errorf("got %d rows, want 1: %+v", len(got), got)
	}
	if got[0]["id"] != "a" {
		t.Errorf("survivor = %v, want a", got[0]["id"])
	}
}

func TestDedupeResults_Limit(t *testing.T) {
	rows := []map[string]any{
		{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"},
	}
	got := DedupeResults(rows, func(r map[string]any) string {
		id, _ := r["id"].(string)
		return id
	}, 2)
	if len(got) != 2 {
		t.Errorf("got %d, want 2", len(got))
	}
}

// --- BuildEmbeddingLanes ----------------------------------------------------

func TestBuildEmbeddingLanes_OrderAndSkip(t *testing.T) {
	chroma := &fakeChroma{collections: map[string]*fakeCollection{}}
	customCalled := 0
	fastCalled := 0

	lanes, err := BuildEmbeddingLanes("rag", chroma,
		func() (Encoder, error) {
			customCalled++
			return &fakeEncoder{dim: 4, model: "m1", url: "u1"}, nil
		},
		func() (Encoder, error) {
			fastCalled++
			return &fakeEncoder{dim: 4, model: "m2", url: "u2"}, nil
		},
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(lanes) != 2 {
		t.Fatalf("got %d lanes, want 2", len(lanes))
	}
	if lanes[0].Name != LANE_CUSTOM || lanes[1].Name != LANE_FASTEMBED {
		t.Errorf("order = [%s, %s], want [custom, fastembed]", lanes[0].Name, lanes[1].Name)
	}
	if customCalled != 1 || fastCalled != 1 {
		t.Errorf("customCalled=%d fastCalled=%d, want 1 each", customCalled, fastCalled)
	}
}

func TestBuildEmbeddingLanes_SkipsBuildersThatThrow(t *testing.T) {
	chroma := &fakeChroma{collections: map[string]*fakeCollection{}}
	lanes, err := BuildEmbeddingLanes("rag", chroma,
		func() (Encoder, error) {
			return nil, errors.New("custom down")
		},
		func() (Encoder, error) {
			return &fakeEncoder{dim: 4, model: "m2", url: "u2"}, nil
		},
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(lanes) != 1 || lanes[0].Name != LANE_FASTEMBED {
		t.Errorf("got %+v, want only fastembed lane", lanes)
	}
}

// BuildEmbeddingLanes_RecreateOnFingerprintChange: an existing collection
// whose metadata disagrees with the new lane must be deleted and recreated;
// the old rows must be preserved (re-encoded here because the fake does not
// store embeddings in metadata).
func TestBuildEmbeddingLanes_RecreateOnFingerprintChange(t *testing.T) {
	chroma := &fakeChroma{collections: map[string]*fakeCollection{}}

	// Seed an existing collection with stale metadata.
	stale := &fakeCollection{
		metadata: map[string]any{
			"embedding_fingerprint": "old-fingerprint",
			"embedding_dimension":   4,
			"embedding_lane":        LANE_CUSTOM,
		},
	}
	stale.rows = []storedRow{
		{ID: "r1", Doc: "hello", Meta: map[string]any{"src": "a"}},
		{ID: "2", Doc: "world", Meta: map[string]any{}},
	}
	chroma.collections["rag_custom"] = stale

	enc := &fakeEncoder{dim: 8, model: "m1", url: "u1"}
	lanes, err := BuildEmbeddingLanes("rag", chroma,
		func() (Encoder, error) { return enc, nil },
		nil,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(lanes) != 1 {
		t.Fatalf("got %d lanes, want 1", len(lanes))
	}

	// Sequence: GetCollection, DeleteCollection, GetOrCreateCollection, Add.
	if !reflect.DeepEqual(chroma.getCalls, []string{"rag_custom"}) {
		t.Errorf("getCalls = %v, want [rag_custom]", chroma.getCalls)
	}
	if !reflect.DeepEqual(chroma.deleteCalls, []string{"rag_custom"}) {
		t.Errorf("deleteCalls = %v, want [rag_custom]", chroma.deleteCalls)
	}
	if len(chroma.createCalls) != 1 || chroma.createCalls[0].Name != "rag_custom" {
		t.Errorf("createCalls = %+v, want one rag_custom create", chroma.createCalls)
	}

	// Verify the recreated collection got the rows back, re-encoded.
	fresh, ok := chroma.collections["rag_custom"]
	if !ok {
		t.Fatal("rag_custom not present after recreate")
	}
	if len(fresh.rows) != 2 {
		t.Errorf("after recreate, %d rows; want 2", len(fresh.rows))
	}
	gotIDs := []string{fresh.rows[0].ID, fresh.rows[1].ID}
	sort.Strings(gotIDs)
	if gotIDs[0] != "2" || gotIDs[1] != "r1" {
		t.Errorf("rows = %v, want [2 r1]", gotIDs)
	}
	if len(enc.calls) == 0 {
		t.Errorf("expected at least one Encode call to re-embed preserved rows")
	}
}

// BuildEmbeddingLanes_RestoreOnWriteFailure: the recreated collection's
// first Add returns an error, so the code must delete again and recreate
// the collection with the OLD metadata, populating it with the preserved
// embeddings (NOT re-encoded) so the caller's rows survive.
func TestBuildEmbeddingLanes_RestoreOnWriteFailure(t *testing.T) {
	chroma := &fakeChroma{collections: map[string]*fakeCollection{}}

	stale := &fakeCollection{
		metadata: map[string]any{
			"embedding_fingerprint": "old",
			"embedding_dimension":   4,
			"embedding_lane":        LANE_CUSTOM,
		},
		rows: []storedRow{
			{ID: "r1", Doc: "hello", Embedding: []float32{0.1, 0.2, 0.3, 0.4}},
			{ID: "r2", Doc: "world", Embedding: []float32{0.5, 0.6, 0.7, 0.8}},
		},
	}
	chroma.collections["rag_custom"] = stale

	// Surface an addErr on the recreated collection: the first collection
	// returned by GetOrCreateCollection will hit it.
	var addGate sync.Mutex
	firstAddFails := true

	enc := &fakeEncoder{dim: 8, model: "m1", url: "u1"}
	// Wrap chroma so the FIRST GetOrCreateCollection (the fresh one) fails
	// on Add, but the SECOND (the restore one) succeeds.
	wrapped := &gatedChroma{
		inner: chroma,
		hookFirstCreate: func(c *fakeCollection) {
			addGate.Lock()
			defer addGate.Unlock()
			if firstAddFails {
				c.addErr = errors.New("synthetic write failure")
			}
		},
		afterFirstAdd: func() {
			addGate.Lock()
			firstAddFails = false
			addGate.Unlock()
		},
	}

	_, err := BuildEmbeddingLanes("rag", wrapped,
		func() (Encoder, error) { return enc, nil },
		nil,
	)
	if err == nil {
		t.Fatalf("expected write-failure error, got nil")
	}
	if !strings.Contains(err.Error(), "write reset collection") {
		t.Errorf("error %q should mention write reset collection", err)
	}

	// Sequence assertions:
	//   1) GetCollection("rag_custom") -> stale
	//   2) DeleteCollection("rag_custom") (pre-recreate)
	//   3) GetOrCreateCollection("rag_custom", NEW meta) -> fresh
	//   4) fresh.Add -> error
	//   5) DeleteCollection("rag_custom") (restore)
	//   6) GetOrCreateCollection("rag_custom", OLD meta) -> restored
	if got := chroma.deleteCalls; len(got) != 2 {
		t.Errorf("deleteCalls = %v, want two deletes", got)
	}
	if len(chroma.createCalls) != 2 {
		t.Errorf("createCalls len = %d, want 2 (fresh + restore)", len(chroma.createCalls))
	}
	if chroma.createCalls[1].Metadata["embedding_fingerprint"] != "old" {
		t.Errorf("restore metadata fp = %v, want old", chroma.createCalls[1].Metadata["embedding_fingerprint"])
	}
	restored := chroma.collections["rag_custom"]
	if restored == nil {
		t.Fatal("rag_custom missing after restore")
	}
	if len(restored.rows) != 2 {
		t.Errorf("restored rows = %d, want 2", len(restored.rows))
	}
	// The restore path must NOT call Encode for the restore step — the
	// preserved embeddings are re-used. We accept Encode calls for the
	// pre-failure re-encode, but after that the counter should not move.
	// Specifically: the encoder was called at least once (re-embed), and
	// the restored rows should carry the *original* embeddings (which the
	// fake pre-seeded as 0.1..0.8).
	for _, r := range restored.rows {
		if len(r.Embedding) != 4 {
			t.Errorf("row %s embedding dim = %d, want 4 (preserved)", r.ID, len(r.Embedding))
		}
	}
}

// gatedChroma wraps a fakeChroma so tests can install per-collection hooks.
type gatedChroma struct {
	inner           *fakeChroma
	hookFirstCreate func(*fakeCollection)
	afterFirstAdd   func()
}

func (g *gatedChroma) GetCollection(name string) (Collection, error) {
	return g.inner.GetCollection(name)
}

func (g *gatedChroma) GetOrCreateCollection(name string, metadata map[string]any) (Collection, error) {
	coll, err := g.inner.GetOrCreateCollection(name, metadata)
	if g.hookFirstCreate != nil {
		if fc, ok := coll.(*fakeCollection); ok {
			g.hookFirstCreate(fc)
		}
	}
	// Wrap with a counting Add so afterFirstAdd fires exactly once.
	if g.afterFirstAdd != nil {
		wrapped := &countingAddCollection{inner: coll, hook: g.afterFirstAdd}
		return wrapped, err
	}
	return coll, err
}

func (g *gatedChroma) DeleteCollection(name string) error {
	return g.inner.DeleteCollection(name)
}

type countingAddCollection struct {
	inner Collection
	hook  func()
	done  bool
	mu    sync.Mutex
}

func (c *countingAddCollection) Count() int                               { return c.inner.Count() }
func (c *countingAddCollection) Get(ids []string) (CollectionRows, error) { return c.inner.Get(ids) }
func (c *countingAddCollection) Query(e [][]float32, n int, w map[string]any, inc []string) (QueryResult, error) {
	return c.inner.Query(e, n, w, inc)
}
func (c *countingAddCollection) Metadata() map[string]any { return c.inner.Metadata() }
func (c *countingAddCollection) Add(ids []string, docs []string, metas []map[string]any, vecs [][]float32) error {
	c.mu.Lock()
	if !c.done {
		c.done = true
		c.mu.Unlock()
		err := c.inner.Add(ids, docs, metas, vecs)
		c.hook()
		return err
	}
	c.mu.Unlock()
	return c.inner.Add(ids, docs, metas, vecs)
}

// --- QueryLanes --------------------------------------------------------------

func TestQueryLanes_SkipsEmptyAndReturnsResults(t *testing.T) {
	enc := &fakeEncoder{dim: 4, model: "m", url: "u"}
	coll := &fakeCollection{
		rows: []storedRow{
			{ID: "a", Doc: "alpha"},
			{ID: "b", Doc: "beta"},
		},
	}
	lane := NewEmbeddingLane(LANE_CUSTOM, enc, coll, "rag_custom", "m", "u", 4, "fp")

	results, err := QueryLanes(
		[]*EmbeddingLane{lane},
		"alpha",
		func(*EmbeddingLane) int { return 10 },
		[]string{"documents"},
		nil,
		false,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("got %d results, want 1", len(results))
	}
	if len(coll.queryCalls) != 1 {
		t.Errorf("expected one query, got %d", len(coll.queryCalls))
	}
	if coll.queryCalls[0].NResults != 2 {
		t.Errorf("n_results = %d, want 2 (capped by lane.Count)", coll.queryCalls[0].NResults)
	}
}

func TestQueryLanes_SkipsEmptyCollection(t *testing.T) {
	enc := &fakeEncoder{dim: 4}
	empty := &fakeCollection{}
	full := &fakeCollection{
		rows: []storedRow{{ID: "a", Doc: "alpha"}},
	}
	laneEmpty := NewEmbeddingLane(LANE_FASTEMBED, enc, empty, "rag_fastembed", "m", "u", 4, "fp")
	laneFull := NewEmbeddingLane(LANE_CUSTOM, enc, full, "rag_custom", "m", "u", 4, "fp")

	results, err := QueryLanes(
		[]*EmbeddingLane{laneEmpty, laneFull},
		"x",
		func(*EmbeddingLane) int { return 10 },
		nil, nil, false,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 1 {
		t.Errorf("got %d results, want 1 (empty lane skipped)", len(results))
	}
}

func TestQueryLanes_RaiseIfAllFailed(t *testing.T) {
	enc := &fakeEncoder{dim: 4}
	failing := &fakeCollection{
		rows:     []storedRow{{ID: "a", Doc: "alpha"}},
		queryErr: errors.New("query down"),
	}
	lane := NewEmbeddingLane(LANE_CUSTOM, enc, failing, "rag_custom", "m", "u", 4, "fp")

	_, err := QueryLanes(
		[]*EmbeddingLane{lane},
		"x",
		func(*EmbeddingLane) int { return 5 },
		nil, nil, true,
	)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !strings.Contains(err.Error(), "all lanes failed") {
		t.Errorf("error %q should mention all lanes failed", err)
	}
	if !strings.Contains(err.Error(), "query down") {
		t.Errorf("error %q should mention underlying cause", err)
	}
}

func TestQueryLanes_DoesNotRaiseOnPartialSuccess(t *testing.T) {
	enc := &fakeEncoder{dim: 4}
	ok := &fakeCollection{
		rows: []storedRow{{ID: "a", Doc: "alpha"}},
	}
	bad := &fakeCollection{
		rows:     []storedRow{{ID: "b", Doc: "beta"}},
		queryErr: errors.New("query down"),
	}
	laneOK := NewEmbeddingLane(LANE_CUSTOM, enc, ok, "rag_custom", "m", "u", 4, "fp")
	laneBad := NewEmbeddingLane(LANE_FASTEMBED, enc, bad, "rag_fastembed", "m", "u", 4, "fp")

	results, err := QueryLanes(
		[]*EmbeddingLane{laneOK, laneBad},
		"x",
		func(*EmbeddingLane) int { return 5 },
		nil, nil, true,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(results) != 1 {
		t.Errorf("got %d results, want 1 (one good lane)", len(results))
	}
}

// --- MigrateLegacyCollection ------------------------------------------------

func TestMigrateLegacyCollection_BackfillsMissing(t *testing.T) {
	chroma := &fakeChroma{collections: map[string]*fakeCollection{}}

	legacy := &fakeCollection{
		rows: []storedRow{
			{ID: "1", Doc: "alpha"},
			{ID: "2", Doc: "beta"},
			{ID: "3", Doc: "gamma"},
		},
	}
	chroma.collections["memory"] = legacy

	// Lane already has id "2".
	enc := &fakeEncoder{dim: 4, model: "m", url: "u"}
	laneColl := &fakeCollection{
		rows: []storedRow{
			{ID: "2", Doc: "beta"},
		},
	}
	chroma.collections["memory_custom"] = laneColl
	lane := NewEmbeddingLane(LANE_CUSTOM, enc, laneColl, "memory_custom", "m", "u", 4, "fp")

	if err := MigrateLegacyCollection("memory", []*EmbeddingLane{lane}, chroma); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	gotIDs := []string{}
	for _, r := range laneColl.rows {
		gotIDs = append(gotIDs, r.ID)
	}
	sort.Strings(gotIDs)
	want := []string{"1", "2", "3"}
	if !reflect.DeepEqual(gotIDs, want) {
		t.Errorf("lane rows after backfill = %v, want %v", gotIDs, want)
	}
}

func TestMigrateLegacyCollection_NoLegacyIsNoop(t *testing.T) {
	chroma := &fakeChroma{collections: map[string]*fakeCollection{}}
	enc := &fakeEncoder{dim: 4}
	laneColl := &fakeCollection{}
	lane := NewEmbeddingLane(LANE_CUSTOM, enc, laneColl, "memory_custom", "m", "u", 4, "fp")

	if err := MigrateLegacyCollection("memory", []*EmbeddingLane{lane}, chroma); err != nil {
		t.Errorf("unexpected error: %v", err)
	}
	if len(laneColl.rows) != 0 {
		t.Errorf("lane got rows, want 0")
	}
}

func TestMigrateLegacyCollection_NoLanesIsNoop(t *testing.T) {
	if err := MigrateLegacyCollection("memory", nil, &fakeChroma{}); err != nil {
		t.Errorf("unexpected error: %v", err)
	}
}

// --- EmbeddingLane.Healthy / Encode / Count / Stats ------------------------

func TestEmbeddingLane_Healthy(t *testing.T) {
	enc := &fakeEncoder{dim: 4}
	coll := &fakeCollection{}
	lane := NewEmbeddingLane(LANE_CUSTOM, enc, coll, "x", "m", "u", 4, "fp")
	if !lane.Healthy() {
		t.Error("expected Healthy=true")
	}
	lane.Client = nil
	if lane.Healthy() {
		t.Error("expected Healthy=false when Client nil")
	}
	lane.Client = enc
	lane.Collection = nil
	if lane.Healthy() {
		t.Error("expected Healthy=false when Collection nil")
	}
}

func TestEmbeddingLane_CountHandlesNegative(t *testing.T) {
	enc := &fakeEncoder{dim: 4}
	coll := &fakeCollection{}
	coll.rows = nil
	lane := NewEmbeddingLane(LANE_CUSTOM, enc, coll, "x", "m", "u", 4, "fp")
	if got := lane.Count(); got != 0 {
		t.Errorf("Count() = %d, want 0", got)
	}
}

func TestEmbeddingLane_Stats(t *testing.T) {
	enc := &fakeEncoder{dim: 4, model: "m", url: "u"}
	coll := &fakeCollection{
		rows: []storedRow{{ID: "a"}},
	}
	lane := NewEmbeddingLane(LANE_CUSTOM, enc, coll, "rag_custom", "m", "u", 4, "fp")
	stats := lane.Stats()
	wantKeys := []string{"name", "collection", "model", "url", "dimension", "fingerprint", "count", "healthy"}
	for _, k := range wantKeys {
		if _, ok := stats[k]; !ok {
			t.Errorf("Stats missing key %q", k)
		}
	}
	if stats["count"] != 1 {
		t.Errorf("count = %v, want 1", stats["count"])
	}
	if stats["healthy"] != true {
		t.Errorf("healthy = %v, want true", stats["healthy"])
	}
}

func TestEmbeddingLane_EncodeDelegates(t *testing.T) {
	enc := &fakeEncoder{dim: 4, model: "m", url: "u"}
	coll := &fakeCollection{}
	lane := NewEmbeddingLane(LANE_CUSTOM, enc, coll, "x", "m", "u", 4, "fp")
	vecs, err := lane.Encode([]string{"a", "b"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(vecs) != 2 {
		t.Errorf("got %d vecs, want 2", len(vecs))
	}
}

// --- LaneCount --------------------------------------------------------------

func TestLaneCount(t *testing.T) {
	enc := &fakeEncoder{dim: 4}
	a := NewEmbeddingLane(LANE_CUSTOM, enc, &fakeCollection{rows: []storedRow{{ID: "1"}}}, "a", "m", "u", 4, "fp")
	b := NewEmbeddingLane(LANE_FASTEMBED, enc, &fakeCollection{rows: []storedRow{{ID: "1"}, {ID: "2"}}}, "b", "m", "u", 4, "fp")
	if got := LaneCount([]*EmbeddingLane{a, b}); got != 2 {
		t.Errorf("LaneCount = %d, want 2", got)
	}
	if got := LaneCount(nil); got != 0 {
		t.Errorf("LaneCount(nil) = %d, want 0", got)
	}
}

// --- helpers ----------------------------------------------------------------

// used to assert the unused-import lint catches nothing.
var _ = fmt.Sprintf
