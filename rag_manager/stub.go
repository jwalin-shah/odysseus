package rag_manager

import (
	"context"
	"sync"
)

// Stub is a deterministic in-memory VectorRAG used by the CLI and tests.
//
// It records every call so tests can assert on argument propagation, and it
// returns sensible zero-value results. It is safe for concurrent use.
type Stub struct {
	mu sync.Mutex

	// Calls recorded for assertions.
	SearchCalls                 []SearchCall
	IndexPersonalDocumentsCalls []IndexCall
	RetrieveCalls               []RetrieveCall
	RebuildIndexCalls           int
	AddDocumentCalls            []AddDocCall
	AddDocumentsBatchCalls      []BatchCall

	// IndexedPaths accumulates paths handed to IndexPersonalDocuments so the
	// CLI can echo them back via stats.
	IndexedPaths []string
}

// Compile-time guarantee that Stub satisfies VectorRAG.
var _ VectorRAG = (*Stub)(nil)

// SearchCall captures one Search invocation.
type SearchCall struct {
	Query string
	K     int
}

// IndexCall captures one IndexPersonalDocuments invocation.
type IndexCall struct {
	Directory      string
	FileExtensions []string
	Owner          string
}

// RetrieveCall captures one Retrieve invocation.
type RetrieveCall struct {
	Query string
	K     int
}

// AddDocCall captures one AddDocument invocation.
type AddDocCall struct {
	Text     string
	Metadata map[string]any
}

// BatchCall captures one AddDocumentsBatch invocation.
type BatchCall struct {
	Docs []Document
}

// NewStub returns an empty Stub.
func NewStub() *Stub {
	return &Stub{}
}

// Search returns an empty slice and records the call.
func (s *Stub) Search(_ context.Context, query string, k int) ([]SearchResult, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.SearchCalls = append(s.SearchCalls, SearchCall{Query: query, K: k})
	return nil, nil
}

// IndexPersonalDocuments records the call and accumulates the directory as
// a single indexed path. Returns zeros except for the indexed-count bump.
func (s *Stub) IndexPersonalDocuments(_ context.Context, directory string, fileExtensions []string, owner string) (IndexResult, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.IndexPersonalDocumentsCalls = append(s.IndexPersonalDocumentsCalls, IndexCall{
		Directory:      directory,
		FileExtensions: fileExtensions,
		Owner:          owner,
	})
	s.IndexedPaths = append(s.IndexedPaths, directory)
	return IndexResult{IndexedCount: 1}, nil
}

// Retrieve returns an empty slice and records the call.
func (s *Stub) Retrieve(_ context.Context, query string, k int) ([]string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.RetrieveCalls = append(s.RetrieveCalls, RetrieveCall{Query: query, K: k})
	return nil, nil
}

// RebuildIndex records the call and returns true.
func (s *Stub) RebuildIndex(_ context.Context) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.RebuildIndexCalls++
	return true, nil
}

// GetStats returns the number of paths the stub has indexed.
func (s *Stub) GetStats() Stats {
	s.mu.Lock()
	defer s.mu.Unlock()
	return Stats{
		DocumentCount: len(s.IndexedPaths),
		ChunkCount:    len(s.IndexedPaths),
	}
}

// AddDocument records the call and returns true.
func (s *Stub) AddDocument(_ context.Context, text string, metadata map[string]any) (bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.AddDocumentCalls = append(s.AddDocumentCalls, AddDocCall{Text: text, Metadata: metadata})
	return true, nil
}

// AddDocumentsBatch records the call and returns the count of added docs.
func (s *Stub) AddDocumentsBatch(_ context.Context, docs []Document) (BatchResult, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	// Defensive copy so later mutation by the caller cannot affect our record.
	cp := make([]Document, len(docs))
	for i, d := range docs {
		cp[i] = Document{Text: d.Text, Metadata: d.Metadata}
	}
	s.AddDocumentsBatchCalls = append(s.AddDocumentsBatchCalls, BatchCall{Docs: cp})
	return BatchResult{AddedCount: len(docs)}, nil
}
