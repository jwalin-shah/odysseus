// Package rag_manager is a thin wrapper around VectorRAG for backward
// compatibility — see rag_vector.go (Python original: src/rag_manager.py).
//
// All Manager methods are pass-throughs to the embedded VectorRAG
// implementation, which is injected at construction time. This package
// does not own a concrete VectorRAG; tests and the CLI stub supply one.
package rag_manager

import "context"

// SearchResult represents a single hit returned by Search.
//
// Mirrors the Python Dict[str, Any] shape: id/text/metadata are strings,
// score is a float, metadata is free-form.
type SearchResult struct {
	ID       string         `json:"id"`
	Text     string         `json:"text"`
	Metadata map[string]any `json:"metadata"`
	Score    float64        `json:"score"`
}

// IndexResult summarises an IndexPersonalDocuments run.
//
// Mirrors the Python Dict[str, Any] returned by VectorRAG.index_personal_documents.
type IndexResult struct {
	IndexedCount int      `json:"indexed_count"`
	SkippedCount int      `json:"skipped_count"`
	Errors       []string `json:"errors,omitempty"`
}

// Stats summarises index state — read-only metadata about the underlying store.
type Stats struct {
	DocumentCount int    `json:"document_count"`
	ChunkCount    int    `json:"chunk_count"`
	LastIndexedAt string `json:"last_indexed_at,omitempty"`
}

// BatchResult summarises an AddDocumentsBatch run.
type BatchResult struct {
	AddedCount  int `json:"added_count"`
	FailedCount int `json:"failed_count"`
}

// Document is the (text, metadata) pair accepted by AddDocument.
//
// Metadata mirrors Python's Dict[str, Any] via map[string]any.
type Document struct {
	Text     string         `json:"text"`
	Metadata map[string]any `json:"metadata"`
}

// VectorRAG is the dependency the Manager wraps.
//
// Methods that touch I/O take a context.Context and may return an error.
// GetStats is sync because it is a cheap read.
type VectorRAG interface {
	Search(ctx context.Context, query string, k int) ([]SearchResult, error)
	IndexPersonalDocuments(ctx context.Context, directory string, fileExtensions []string, owner string) (IndexResult, error)
	Retrieve(ctx context.Context, query string, k int) ([]string, error)
	RebuildIndex(ctx context.Context) (bool, error)
	GetStats() Stats
	AddDocument(ctx context.Context, text string, metadata map[string]any) (bool, error)
	AddDocumentsBatch(ctx context.Context, docs []Document) (BatchResult, error)
}

// Manager is a thin pass-through wrapper around a VectorRAG.
//
// It exists for backward compatibility with the Python RAGManager class.
type Manager struct {
	persistDirectory string
	vectorRAG        VectorRAG
}

// New constructs a Manager that delegates to the supplied VectorRAG.
//
// Passing a nil VectorRAG panics — it is a programming error, not a runtime
// condition callers can recover from. Tests and the CLI stub inject their
// own implementation; production callers will eventually pass a real
// VectorRAG (to be ported separately).
func New(persistDirectory string, vr VectorRAG) *Manager {
	if vr == nil {
		panic("rag_manager: New: VectorRAG must not be nil")
	}
	return &Manager{
		persistDirectory: persistDirectory,
		vectorRAG:        vr,
	}
}

// NewDefault returns a Manager backed by the bundled stub VectorRAG.
//
// Used by the CLI and by callers that do not yet have a real VectorRAG.
// The stub records calls and returns deterministic empty values.
func NewDefault(persistDirectory string) *Manager {
	return New(persistDirectory, NewStub())
}

// PersistDirectory returns the configured persist directory.
func (m *Manager) PersistDirectory() string {
	return m.persistDirectory
}

// Search delegates to the underlying VectorRAG.
func (m *Manager) Search(ctx context.Context, query string, k int) ([]SearchResult, error) {
	return m.vectorRAG.Search(ctx, query, k)
}

// IndexPersonalDocuments delegates to the underlying VectorRAG.
//
// fileExtensions is normalised to a slice; owner is a free-form identifier.
func (m *Manager) IndexPersonalDocuments(ctx context.Context, directory string, fileExtensions []string, owner string) (IndexResult, error) {
	return m.vectorRAG.IndexPersonalDocuments(ctx, directory, fileExtensions, owner)
}

// Retrieve delegates to the underlying VectorRAG.
func (m *Manager) Retrieve(ctx context.Context, query string, k int) ([]string, error) {
	return m.vectorRAG.Retrieve(ctx, query, k)
}

// RebuildIndex delegates to the underlying VectorRAG.
func (m *Manager) RebuildIndex(ctx context.Context) (bool, error) {
	return m.vectorRAG.RebuildIndex(ctx)
}

// GetStats delegates to the underlying VectorRAG. Sync because it is a read.
func (m *Manager) GetStats() Stats {
	return m.vectorRAG.GetStats()
}

// AddDocument delegates to the underlying VectorRAG.
func (m *Manager) AddDocument(ctx context.Context, text string, metadata map[string]any) (bool, error) {
	return m.vectorRAG.AddDocument(ctx, text, metadata)
}

// AddDocumentsBatch delegates to the underlying VectorRAG.
func (m *Manager) AddDocumentsBatch(ctx context.Context, docs []Document) (BatchResult, error) {
	return m.vectorRAG.AddDocumentsBatch(ctx, docs)
}
