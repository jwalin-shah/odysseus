package rag_manager

import (
	"context"
	"errors"
	"reflect"
	"testing"
)

// Compile-time assertion that fakeVectorRAG implements VectorRAG.
var _ VectorRAG = (*fakeVectorRAG)(nil)

// fakeVectorRAG is a controllable VectorRAG used by delegation tests.
type fakeVectorRAG struct {
	searchResult []SearchResult
	searchErr    error
	searchCtx    context.Context
	searchQuery  string
	searchK      int
	searchCalled int

	indexResult     IndexResult
	indexErr        error
	indexCtx        context.Context
	indexDirectory  string
	indexExtensions []string
	indexOwner      string
	indexCalled     int

	retrieveResult []string
	retrieveErr    error
	retrieveCtx    context.Context
	retrieveQuery  string
	retrieveK      int
	retrieveCalled int

	rebuildResult bool
	rebuildErr    error
	rebuildCtx    context.Context
	rebuildCalled int

	statsValue Stats
	statsCalls int

	addDocResult bool
	addDocErr    error
	addDocCtx    context.Context
	addDocText   string
	addDocMeta   map[string]any
	addDocCalled int

	batchResult BatchResult
	batchErr    error
	batchCtx    context.Context
	batchDocs   []Document
	batchCalled int
}

func (f *fakeVectorRAG) Search(ctx context.Context, query string, k int) ([]SearchResult, error) {
	f.searchCtx = ctx
	f.searchQuery = query
	f.searchK = k
	f.searchCalled++
	return f.searchResult, f.searchErr
}

func (f *fakeVectorRAG) IndexPersonalDocuments(ctx context.Context, directory string, fileExtensions []string, owner string) (IndexResult, error) {
	f.indexCtx = ctx
	f.indexDirectory = directory
	f.indexExtensions = fileExtensions
	f.indexOwner = owner
	f.indexCalled++
	return f.indexResult, f.indexErr
}

func (f *fakeVectorRAG) Retrieve(ctx context.Context, query string, k int) ([]string, error) {
	f.retrieveCtx = ctx
	f.retrieveQuery = query
	f.retrieveK = k
	f.retrieveCalled++
	return f.retrieveResult, f.retrieveErr
}

func (f *fakeVectorRAG) RebuildIndex(ctx context.Context) (bool, error) {
	f.rebuildCtx = ctx
	f.rebuildCalled++
	return f.rebuildResult, f.rebuildErr
}

func (f *fakeVectorRAG) GetStats() Stats {
	f.statsCalls++
	return f.statsValue
}

func (f *fakeVectorRAG) AddDocument(ctx context.Context, text string, metadata map[string]any) (bool, error) {
	f.addDocCtx = ctx
	f.addDocText = text
	f.addDocMeta = metadata
	f.addDocCalled++
	return f.addDocResult, f.addDocErr
}

func (f *fakeVectorRAG) AddDocumentsBatch(ctx context.Context, docs []Document) (BatchResult, error) {
	f.batchCtx = ctx
	f.batchDocs = docs
	f.batchCalled++
	return f.batchResult, f.batchErr
}

// errSentinel is a non-nil error used by delegation tests.
var errSentinel = errors.New("sentinel")

func TestNew_StoresPersistDirectoryAndVectorRAG(t *testing.T) {
	fake := &fakeVectorRAG{}
	mgr := New("/tmp/chroma", fake)

	if got, want := mgr.PersistDirectory(), "/tmp/chroma"; got != want {
		t.Errorf("PersistDirectory() = %q, want %q", got, want)
	}
	// No public accessor for the embedded VectorRAG; assert via behaviour.
	if mgr.GetStats() != (Stats{}) {
		t.Errorf("GetStats() with zero fake = %+v, want zero Stats", mgr.GetStats())
	}
	if fake.statsCalls != 1 {
		t.Errorf("fake.statsCalls = %d, want 1", fake.statsCalls)
	}
}

func TestNew_NilVectorRAGPanics(t *testing.T) {
	defer func() {
		if r := recover(); r == nil {
			t.Fatalf("New(nil) did not panic")
		}
	}()
	_ = New("/tmp/chroma", nil)
}

func TestNewDefault_ReturnsNonNilManagerWithStubVectorRAG(t *testing.T) {
	mgr := NewDefault("/tmp/chroma-default")
	if mgr == nil {
		t.Fatal("NewDefault returned nil")
	}
	if got, want := mgr.PersistDirectory(), "/tmp/chroma-default"; got != want {
		t.Errorf("PersistDirectory() = %q, want %q", got, want)
	}

	// NewDefault must wire a working VectorRAG. Exercising GetStats
	// indirectly asserts that the underlying impl is non-nil.
	if _, err := mgr.Search(context.Background(), "hello", 3); err != nil {
		t.Errorf("Search via NewDefault returned err = %v", err)
	}
}

func TestSearch_ForwardsArgsAndReturnsValueAndError(t *testing.T) {
	want := []SearchResult{{ID: "1", Text: "alpha"}, {ID: "2", Text: "beta"}}
	fake := &fakeVectorRAG{
		searchResult: want,
		searchErr:    errSentinel,
	}
	mgr := New("/p", fake)
	ctx := context.Background()

	got, err := mgr.Search(ctx, "query", 7)
	if !errors.Is(err, errSentinel) {
		t.Errorf("err = %v, want sentinel", err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("result = %+v, want %+v", got, want)
	}
	if fake.searchCalled != 1 {
		t.Errorf("searchCalled = %d, want 1", fake.searchCalled)
	}
	if fake.searchCtx != ctx {
		t.Errorf("ctx not forwarded")
	}
	if fake.searchQuery != "query" {
		t.Errorf("query = %q, want %q", fake.searchQuery, "query")
	}
	if fake.searchK != 7 {
		t.Errorf("k = %d, want 7", fake.searchK)
	}
}

func TestSearch_EmptyResult(t *testing.T) {
	fake := &fakeVectorRAG{}
	mgr := New("/p", fake)
	got, err := mgr.Search(context.Background(), "", 0)
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if got != nil {
		t.Errorf("got = %+v, want nil", got)
	}
}

func TestIndexPersonalDocuments_ForwardsAllArgs(t *testing.T) {
	want := IndexResult{IndexedCount: 9, SkippedCount: 1, Errors: []string{"e1"}}
	fake := &fakeVectorRAG{indexResult: want}
	mgr := New("/p", fake)
	ctx := context.Background()
	exts := []string{".md", ".txt"}

	got, err := mgr.IndexPersonalDocuments(ctx, "/docs", exts, "alice")
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if got.IndexedCount != want.IndexedCount ||
		got.SkippedCount != want.SkippedCount ||
		!reflect.DeepEqual(got.Errors, want.Errors) {
		t.Errorf("result = %+v, want %+v", got, want)
	}
	if fake.indexCalled != 1 {
		t.Errorf("indexCalled = %d, want 1", fake.indexCalled)
	}
	if fake.indexCtx != ctx {
		t.Errorf("ctx not forwarded")
	}
	if fake.indexDirectory != "/docs" {
		t.Errorf("directory = %q", fake.indexDirectory)
	}
	if !reflect.DeepEqual(fake.indexExtensions, exts) {
		t.Errorf("extensions = %+v, want %+v", fake.indexExtensions, exts)
	}
	if fake.indexOwner != "alice" {
		t.Errorf("owner = %q", fake.indexOwner)
	}
}

func TestIndexPersonalDocuments_NilExtensionsAndEmptyOwner(t *testing.T) {
	fake := &fakeVectorRAG{}
	mgr := New("/p", fake)
	if _, err := mgr.IndexPersonalDocuments(context.Background(), "/d", nil, ""); err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if fake.indexExtensions != nil {
		t.Errorf("extensions = %+v, want nil", fake.indexExtensions)
	}
	if fake.indexOwner != "" {
		t.Errorf("owner = %q, want \"\"", fake.indexOwner)
	}
}

func TestIndexPersonalDocuments_PropagatesError(t *testing.T) {
	fake := &fakeVectorRAG{indexErr: errSentinel}
	mgr := New("/p", fake)
	_, err := mgr.IndexPersonalDocuments(context.Background(), "/d", nil, "")
	if !errors.Is(err, errSentinel) {
		t.Errorf("err = %v, want sentinel", err)
	}
}

func TestRetrieve_ForwardsArgsAndReturnsValue(t *testing.T) {
	want := []string{"alpha", "beta"}
	fake := &fakeVectorRAG{retrieveResult: want}
	mgr := New("/p", fake)
	ctx := context.Background()

	got, err := mgr.Retrieve(ctx, "q", 4)
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got = %+v, want %+v", got, want)
	}
	if fake.retrieveCalled != 1 {
		t.Errorf("retrieveCalled = %d, want 1", fake.retrieveCalled)
	}
	if fake.retrieveCtx != ctx {
		t.Errorf("ctx not forwarded")
	}
	if fake.retrieveQuery != "q" {
		t.Errorf("query = %q", fake.retrieveQuery)
	}
	if fake.retrieveK != 4 {
		t.Errorf("k = %d, want 4", fake.retrieveK)
	}
}

func TestRetrieve_PropagatesError(t *testing.T) {
	fake := &fakeVectorRAG{retrieveErr: errSentinel}
	mgr := New("/p", fake)
	_, err := mgr.Retrieve(context.Background(), "q", 1)
	if !errors.Is(err, errSentinel) {
		t.Errorf("err = %v, want sentinel", err)
	}
}

func TestRebuildIndex_ForwardsContextAndReturnsValue(t *testing.T) {
	fake := &fakeVectorRAG{rebuildResult: true}
	mgr := New("/p", fake)
	ctx := context.Background()

	ok, err := mgr.RebuildIndex(ctx)
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if !ok {
		t.Errorf("ok = false, want true")
	}
	if fake.rebuildCalled != 1 {
		t.Errorf("rebuildCalled = %d, want 1", fake.rebuildCalled)
	}
	if fake.rebuildCtx != ctx {
		t.Errorf("ctx not forwarded")
	}
}

func TestRebuildIndex_FalseResult(t *testing.T) {
	fake := &fakeVectorRAG{rebuildResult: false}
	mgr := New("/p", fake)
	ok, err := mgr.RebuildIndex(context.Background())
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if ok {
		t.Errorf("ok = true, want false")
	}
}

func TestRebuildIndex_PropagatesError(t *testing.T) {
	fake := &fakeVectorRAG{rebuildErr: errSentinel}
	mgr := New("/p", fake)
	_, err := mgr.RebuildIndex(context.Background())
	if !errors.Is(err, errSentinel) {
		t.Errorf("err = %v, want sentinel", err)
	}
}

func TestGetStats_ReturnsUnderlyingValue(t *testing.T) {
	want := Stats{DocumentCount: 42, ChunkCount: 100, LastIndexedAt: "2026-06-21T00:00:00Z"}
	fake := &fakeVectorRAG{statsValue: want}
	mgr := New("/p", fake)

	if got := mgr.GetStats(); got != want {
		t.Errorf("got = %+v, want %+v", got, want)
	}
	if fake.statsCalls != 1 {
		t.Errorf("statsCalls = %d, want 1", fake.statsCalls)
	}
}

func TestAddDocument_ForwardsArgsAndReturnsValue(t *testing.T) {
	meta := map[string]any{"k": "v", "n": 1}
	fake := &fakeVectorRAG{addDocResult: true}
	mgr := New("/p", fake)
	ctx := context.Background()

	ok, err := mgr.AddDocument(ctx, "body", meta)
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if !ok {
		t.Errorf("ok = false, want true")
	}
	if fake.addDocCalled != 1 {
		t.Errorf("addDocCalled = %d, want 1", fake.addDocCalled)
	}
	if fake.addDocCtx != ctx {
		t.Errorf("ctx not forwarded")
	}
	if fake.addDocText != "body" {
		t.Errorf("text = %q", fake.addDocText)
	}
	if !reflect.DeepEqual(fake.addDocMeta, meta) {
		t.Errorf("metadata = %+v, want %+v", fake.addDocMeta, meta)
	}
}

func TestAddDocument_PropagatesError(t *testing.T) {
	fake := &fakeVectorRAG{addDocErr: errSentinel}
	mgr := New("/p", fake)
	_, err := mgr.AddDocument(context.Background(), "x", nil)
	if !errors.Is(err, errSentinel) {
		t.Errorf("err = %v, want sentinel", err)
	}
}

func TestAddDocumentsBatch_ForwardsDocsAndReturnsValue(t *testing.T) {
	docs := []Document{
		{Text: "a", Metadata: map[string]any{"i": 0}},
		{Text: "b", Metadata: map[string]any{"i": 1}},
	}
	want := BatchResult{AddedCount: 2, FailedCount: 0}
	fake := &fakeVectorRAG{batchResult: want}
	mgr := New("/p", fake)
	ctx := context.Background()

	got, err := mgr.AddDocumentsBatch(ctx, docs)
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if got != want {
		t.Errorf("got = %+v, want %+v", got, want)
	}
	if fake.batchCalled != 1 {
		t.Errorf("batchCalled = %d, want 1", fake.batchCalled)
	}
	if fake.batchCtx != ctx {
		t.Errorf("ctx not forwarded")
	}
	if !reflect.DeepEqual(fake.batchDocs, docs) {
		t.Errorf("docs = %+v, want %+v", fake.batchDocs, docs)
	}
}

func TestAddDocumentsBatch_EmptySlice(t *testing.T) {
	fake := &fakeVectorRAG{}
	mgr := New("/p", fake)
	got, err := mgr.AddDocumentsBatch(context.Background(), nil)
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if got.AddedCount != 0 || got.FailedCount != 0 {
		t.Errorf("got = %+v, want zero BatchResult", got)
	}
	if fake.batchCalled != 1 {
		t.Errorf("batchCalled = %d, want 1", fake.batchCalled)
	}
	if len(fake.batchDocs) != 0 {
		t.Errorf("batchDocs len = %d, want 0", len(fake.batchDocs))
	}
}

func TestAddDocumentsBatch_PropagatesError(t *testing.T) {
	fake := &fakeVectorRAG{batchErr: errSentinel}
	mgr := New("/p", fake)
	_, err := mgr.AddDocumentsBatch(context.Background(), []Document{})
	if !errors.Is(err, errSentinel) {
		t.Errorf("err = %v, want sentinel", err)
	}
}

func TestDelegation_TableDriven(t *testing.T) {
	// Sweep every Manager method through the fake and confirm the fake
	// saw exactly one call with the expected args.
	cases := []struct {
		name string
		call func(m *Manager)
	}{
		{
			name: "Search",
			call: func(m *Manager) { _, _ = m.Search(context.Background(), "q", 3) },
		},
		{
			name: "IndexPersonalDocuments",
			call: func(m *Manager) {
				_, _ = m.IndexPersonalDocuments(context.Background(), "/d", []string{".md"}, "owner")
			},
		},
		{
			name: "Retrieve",
			call: func(m *Manager) { _, _ = m.Retrieve(context.Background(), "q", 3) },
		},
		{
			name: "RebuildIndex",
			call: func(m *Manager) { _, _ = m.RebuildIndex(context.Background()) },
		},
		{
			name: "GetStats",
			call: func(m *Manager) { _ = m.GetStats() },
		},
		{
			name: "AddDocument",
			call: func(m *Manager) {
				_, _ = m.AddDocument(context.Background(), "t", map[string]any{"k": "v"})
			},
		},
		{
			name: "AddDocumentsBatch",
			call: func(m *Manager) {
				_, _ = m.AddDocumentsBatch(context.Background(), []Document{{Text: "a"}})
			},
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			fake := &fakeVectorRAG{}
			mgr := New("/p", fake)
			tc.call(mgr)
		})
	}
}

func TestStub_ImplementsVectorRAG(t *testing.T) {
	// Compile-time assertion lives at package top; runtime smoke too.
	var v VectorRAG = NewStub()
	if v == nil {
		t.Fatal("NewStub returned nil when assigned to VectorRAG interface")
	}
}

func TestStub_RecordsAndReturns(t *testing.T) {
	stub := NewStub()
	ctx := context.Background()

	if _, err := stub.Search(ctx, "q", 5); err != nil {
		t.Fatalf("Search: %v", err)
	}
	if len(stub.SearchCalls) != 1 || stub.SearchCalls[0] != (SearchCall{Query: "q", K: 5}) {
		t.Errorf("SearchCalls = %+v", stub.SearchCalls)
	}

	if _, err := stub.IndexPersonalDocuments(ctx, "/d", []string{".md"}, "alice"); err != nil {
		t.Fatalf("IndexPersonalDocuments: %v", err)
	}
	if len(stub.IndexPersonalDocumentsCalls) != 1 {
		t.Fatalf("IndexPersonalDocumentsCalls = %+v", stub.IndexPersonalDocumentsCalls)
	}
	c := stub.IndexPersonalDocumentsCalls[0]
	if c.Directory != "/d" || c.Owner != "alice" || len(c.FileExtensions) != 1 || c.FileExtensions[0] != ".md" {
		t.Errorf("IndexCall = %+v", c)
	}

	if _, err := stub.Retrieve(ctx, "q", 2); err != nil {
		t.Fatalf("Retrieve: %v", err)
	}
	if len(stub.RetrieveCalls) != 1 {
		t.Errorf("RetrieveCalls = %+v", stub.RetrieveCalls)
	}

	if _, err := stub.RebuildIndex(ctx); err != nil {
		t.Fatalf("RebuildIndex: %v", err)
	}
	if stub.RebuildIndexCalls != 1 {
		t.Errorf("RebuildIndexCalls = %d", stub.RebuildIndexCalls)
	}

	if _, err := stub.AddDocument(ctx, "t", map[string]any{"k": "v"}); err != nil {
		t.Fatalf("AddDocument: %v", err)
	}
	if len(stub.AddDocumentCalls) != 1 {
		t.Errorf("AddDocumentCalls = %+v", stub.AddDocumentCalls)
	}

	if _, err := stub.AddDocumentsBatch(ctx, []Document{{Text: "a"}, {Text: "b"}}); err != nil {
		t.Fatalf("AddDocumentsBatch: %v", err)
	}
	if len(stub.AddDocumentsBatchCalls) != 1 || len(stub.AddDocumentsBatchCalls[0].Docs) != 2 {
		t.Errorf("AddDocumentsBatchCalls = %+v", stub.AddDocumentsBatchCalls)
	}

	if got := stub.GetStats(); got.DocumentCount != 1 || got.ChunkCount != 1 {
		t.Errorf("GetStats after one index = %+v", got)
	}
}
