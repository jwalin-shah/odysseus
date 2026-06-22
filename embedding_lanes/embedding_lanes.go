// Package embedding_lanes is the Go port of src/embedding_lanes.py.
//
// ChromaDB fixes a collection's dimension on first insert, so different
// embedding models must never share one collection. This package keeps
// FastEmbed fallback vectors separate from user-configured embedding vectors
// by giving each lane its own suffixed collection. It also handles the
// recreate-on-fingerprint-change flow: when an existing collection's metadata
// disagrees with the configured lane fingerprint, the old rows are preserved
// (and re-embedded if their original embeddings are unavailable) before the
// collection is deleted and recreated.
//
// The package is stdlib-only and depends on a small pluggable interface
// surface (Encoder, Collection, ChromaClient) so it can be tested without a
// real ChromaDB. A small package-internal stub of chromadb-go is NOT
// included — that lives in the chroma_client package.
package embedding_lanes

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
)

// Lane names exported as constants so tests and callers can reference them
// by symbol rather than copying string literals.
const (
	LANE_FASTEMBED = "fastembed"
	LANE_CUSTOM    = "custom"
)

// fingerprintLen is the length of the prefix of the SHA-256 hex digest that
// the package uses as a lane fingerprint. Matches the Python reference.
const fingerprintLen = 16

// Encoder is the subset of an embedding client that the lane helpers need.
// The Python module uses different concrete clients (FastEmbedClient /
// EmbeddingClient) but they share this surface.
type Encoder interface {
	Encode(texts []string) ([][]float32, error)
	Dimension() int
	Model() string
	URL() string
}

// CollectionRows is the row payload returned by Collection.Get. Embeddings is
// optional — when the Chroma collection was created without an embedding
// function, Chroma does not return embeddings on Get and Encode must run
// again during the recreate flow.
type CollectionRows struct {
	IDs        []string
	Documents  []string
	Metadatas  []map[string]any
	Embeddings [][]float32
}

// QueryResult is the per-lane payload returned by Collection.Query. The
// Python reference returns a dict with parallel arrays for ids/documents/
// distances/metadatas; we mirror that shape exactly.
type QueryResult struct {
	IDs       [][]string
	Documents [][]string
	Metadatas [][]map[string]any
	Distances [][]float32
}

// Collection is the subset of a Chroma collection that the lane helpers use.
// The interface is the bare minimum needed to count, fetch, query, and write
// rows; it is intentionally narrower than the chromadb-go surface so the
// package can be unit-tested with an in-memory fake.
type Collection interface {
	Count() int
	Get(ids []string) (CollectionRows, error)
	Query(embeddings [][]float32, nResults int, where map[string]any, include []string) (QueryResult, error)
	Add(ids []string, docs []string, metas []map[string]any, embeddings [][]float32) error
	Metadata() map[string]any
}

// ChromaClient is the subset of a Chroma client the lane helpers need.
// Real chromadb-go clients satisfy this; tests inject a fake.
type ChromaClient interface {
	GetCollection(name string) (Collection, error)
	GetOrCreateCollection(name string, metadata map[string]any) (Collection, error)
	DeleteCollection(name string) error
}

// CollectionName returns "<base_name>_<lane_name>". Mirrors
// Python's collection_name().
func CollectionName(baseName, laneName string) string {
	return baseName + "_" + laneName
}

// Fingerprint returns the first 16 hex characters of the SHA-256 digest of
// "lane\nurl\nmodel\ndimension". Stable across processes so a process restart
// recomputes the same value for the same configuration.
func Fingerprint(laneName, url, model string, dimension int) string {
	raw := fmt.Sprintf("%s\n%s\n%s\n%d", laneName, url, model, dimension)
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])[:fingerprintLen]
}

// Metadata returns the collection metadata written into a lane. The hnsw:space
// value is fixed to cosine to match the Python reference; the remaining keys
// identify the lane that produced the embeddings so a future recreate flow can
// detect a model swap.
func Metadata(laneName, url, model string, dimension int, fingerprint string) map[string]any {
	return map[string]any{
		"hnsw:space":            "cosine",
		"embedding_lane":        laneName,
		"embedding_url":         url,
		"embedding_model":       model,
		"embedding_dimension":   dimension,
		"embedding_fingerprint": fingerprint,
	}
}

// CustomEndpoint mirrors the dict returned by the Python _load_custom_endpoint
// helper. Only the env-only path is supported here; the persisted-endpoint
// path lives in the embeddings package.
type CustomEndpoint struct {
	URL    string
	Model  string
	APIKey string
}

// LoadCustomEndpoint reads the env-only path of the Python
// _load_custom_endpoint helper. It returns an empty CustomEndpoint when no
// EMBEDDING_URL is set, matching the Python "no URL -> {}" branch.
//
// The persisted-endpoint and api-key decryption branches are intentionally
// not implemented — the package is stdlib-only and the embeddings package
// owns the richer loader.
func LoadCustomEndpoint() CustomEndpoint {
	url := os.Getenv("EMBEDDING_URL")
	if url == "" {
		return CustomEndpoint{}
	}
	return CustomEndpoint{
		URL:    url,
		Model:  os.Getenv("EMBEDDING_MODEL"),
		APIKey: os.Getenv("EMBEDDING_API_KEY"),
	}
}

// batchSize matches the Python _get_or_reset_collection batching (100 rows).
// Exposed as a constant so tests can reference it without copying the magic
// number.
const batchSize = 100

// EmbeddingLane is the Go analogue of the Python EmbeddingLane dataclass.
// Methods on it are thin wrappers that delegate to the embedded client and
// collection — the real logic lives in the package-level helpers so the
// helpers can be exercised without a concrete lane.
type EmbeddingLane struct {
	Name           string
	Client         Encoder
	Collection     Collection
	CollectionName string
	Model          string
	URL            string
	Dimension      int
	Fingerprint    string
}

// NewEmbeddingLane constructs an EmbeddingLane from its components. No
// validation is performed — callers must guarantee client and collection are
// non-nil for Healthy() to return true.
func NewEmbeddingLane(name string, client Encoder, collection Collection, collectionName, model, url string, dimension int, fingerprint string) *EmbeddingLane {
	return &EmbeddingLane{
		Name:           name,
		Client:         client,
		Collection:     collection,
		CollectionName: collectionName,
		Model:          model,
		URL:            url,
		Dimension:      dimension,
		Fingerprint:    fingerprint,
	}
}

// Healthy reports whether the lane has a usable client and collection. This
// is the Go analogue of the Python @property healthy.
func (l *EmbeddingLane) Healthy() bool {
	return l != nil && l.Collection != nil && l.Client != nil
}

// Encode encodes texts through the lane's client. The float32 vectors are
// returned as-is (Python used numpy with normalize_embeddings=True; callers
// that need L2-normalised output should normalise after the call, matching
// the Python `_encode_with_client` helper that wraps the client.encode).
func (l *EmbeddingLane) Encode(texts []string) ([][]float32, error) {
	if l == nil || l.Client == nil {
		return nil, fmt.Errorf("embedding_lanes: lane has no client")
	}
	return l.Client.Encode(texts)
}

// Count returns the number of rows in the lane's collection. Any error from
// the underlying collection collapses to 0 to match the Python
// `try / except Exception -> 0` semantics.
func (l *EmbeddingLane) Count() int {
	if l == nil || l.Collection == nil {
		return 0
	}
	c := l.Collection.Count()
	if c < 0 {
		return 0
	}
	return c
}

// Stats returns the same dict shape as the Python EmbeddingLane.stats()
// helper. It exists so the CLI and tests can render a lane without
// importing every field by hand.
func (l *EmbeddingLane) Stats() map[string]any {
	if l == nil {
		return map[string]any{}
	}
	return map[string]any{
		"name":        l.Name,
		"collection":  l.CollectionName,
		"model":       l.Model,
		"url":         l.URL,
		"dimension":   l.Dimension,
		"fingerprint": l.Fingerprint,
		"count":       l.Count(),
		"healthy":     l.Healthy(),
	}
}

// fingerprintMismatch returns true when current collection metadata disagrees
// with the desired metadata on any of the three fingerprint/dimension/lane
// fields. Matches the Python `not (... not in (None, ...))` semantics — a
// missing key on the current side is treated as "no constraint" so a fresh
// collection never triggers a recreate.
func fingerprintMismatch(current, desired map[string]any) bool {
	if current == nil {
		return false
	}
	checks := []struct {
		key string
	}{
		{"embedding_fingerprint"},
		{"embedding_dimension"},
		{"embedding_lane"},
	}
	for _, c := range checks {
		cur, ok := current[c.key]
		if !ok {
			continue
		}
		want, present := desired[c.key]
		if !present {
			continue
		}
		if !equalAny(cur, want) {
			return true
		}
	}
	return false
}

// equalAny compares two values that come out of map[string]any without
// assuming a concrete type. Chroma returns dimension as float64 in JSON but
// the Python metadata builds it as int; the helper coerces both sides.
func equalAny(a, b any) bool {
	if af, ok := a.(float64); ok {
		switch bv := b.(type) {
		case int:
			return af == float64(bv)
		case float64:
			return af == bv
		case int64:
			return af == float64(bv)
		}
	}
	if ai, ok := a.(int); ok {
		switch bv := b.(type) {
		case float64:
			return float64(ai) == bv
		case int:
			return ai == bv
		case int64:
			return int64(ai) == bv
		}
	}
	return a == b
}

// preserveRows pulls the existing rows out of a collection before it is
// deleted. The "preserve embeddings" branch mirrors the Python comment that
// flags `if ids and docs and len(old_embeddings)` — when Chroma returns the
// stored embeddings we can re-add them directly, avoiding the re-encode cost
// (and the failure mode where a model is no longer reachable).
func preserveRows(c Collection) (CollectionRows, error) {
	rows, err := c.Get(nil)
	if err != nil {
		return CollectionRows{}, fmt.Errorf("preserve rows: %w", err)
	}
	return rows, nil
}

// getOrResetCollection is the Go analogue of Python's
// _get_or_reset_collection. It returns a collection whose metadata matches
// desired; if the existing one disagrees, the old rows are preserved (with
// re-encoding when embeddings are missing) and the collection is recreated.
//
// The restore-on-write-failure branch mirrors the Python except branch: if
// the post-reset Add fails, we delete again and re-create the collection
// with the *old* metadata, populating it with whatever rows we still have
// (preferring preserved embeddings over re-encoded ones).
func getOrResetCollection(chroma ChromaClient, name string, desired map[string]any, client Encoder) (Collection, error) {
	existing, err := chroma.GetCollection(name)
	if err != nil {
		return chroma.GetOrCreateCollection(name, desired)
	}
	current := existing.Metadata()
	if !fingerprintMismatch(current, desired) {
		return existing, nil
	}

	rows, preserveErr := preserveRows(existing)
	if preserveErr != nil {
		return nil, preserveErr
	}

	// Re-encode any preserved documents. Mirrors the Python batching loop
	// (100 rows at a time) so a large collection does not hit a single
	// oversized request.
	var prepared []preparedBatch
	if len(rows.IDs) > 0 && len(rows.Documents) > 0 {
		for start := 0; start < len(rows.IDs); start += batchSize {
			end := start + batchSize
			if end > len(rows.IDs) {
				end = len(rows.IDs)
			}
			batchDocs := rows.Documents[start:end]
			batchMetas := padMetas(rows.Metadatas[start:end], end-start)
			vecs, encErr := client.Encode(batchDocs)
			if encErr != nil {
				return nil, fmt.Errorf("re-embed preserved rows for %s: %w", name, encErr)
			}
			prepared = append(prepared, preparedBatch{
				IDs:        rows.IDs[start:end],
				Docs:       batchDocs,
				Metas:      batchMetas,
				Embeddings: vecs,
			})
		}
	}

	if delErr := chroma.DeleteCollection(name); delErr != nil {
		return nil, fmt.Errorf("delete collection %s: %w", name, delErr)
	}
	fresh, gcErr := chroma.GetOrCreateCollection(name, desired)
	if gcErr != nil {
		return nil, fmt.Errorf("recreate collection %s: %w", name, gcErr)
	}

	for _, b := range prepared {
		if addErr := fresh.Add(b.IDs, b.Docs, b.Metas, b.Embeddings); addErr != nil {
			// Restore-on-write-failure: delete the half-built collection
			// and recreate it with the OLD metadata, then re-add the
			// original rows. Prefer preserved embeddings so we do not
			// have to re-encode (the original model may be unreachable).
			_ = chroma.DeleteCollection(name)
			restored, restoreErr := chroma.GetOrCreateCollection(name, current)
			if restoreErr == nil {
				if len(rows.Embeddings) > 0 && len(rows.IDs) > 0 && len(rows.Documents) > 0 {
					for start := 0; start < len(rows.IDs); start += batchSize {
						end := start + batchSize
						if end > len(rows.IDs) {
							end = len(rows.IDs)
						}
						batchIDs := rows.IDs[start:end]
						batchDocs := rows.Documents[start:end]
						batchMetas := padMetas(rows.Metadatas[start:end], end-start)
						batchVecs := rows.Embeddings[start:end]
						_ = restored.Add(batchIDs, batchDocs, batchMetas, batchVecs)
					}
				}
			}
			return nil, fmt.Errorf("write reset collection %s: %w", name, addErr)
		}
	}
	return fresh, nil
}

// preparedBatch is one prepared re-embed batch waiting to be written to the
// recreated collection.
type preparedBatch struct {
	IDs        []string
	Docs       []string
	Metas      []map[string]any
	Embeddings [][]float32
}

// padMetas returns metas padded with empty maps so it always matches the
// number of rows in ids. Mirrors the Python
// `if len(batch_metas) < len(batch_ids): batch_metas += [{}] * (...)` guard.
func padMetas(metas []map[string]any, n int) []map[string]any {
	if len(metas) >= n {
		return metas[:n]
	}
	out := make([]map[string]any, n)
	copy(out, metas)
	for i := len(metas); i < n; i++ {
		out[i] = map[string]any{}
	}
	return out
}

// LaneBuilder is the factory contract BuildEmbeddingLanes uses to obtain a
// client for a lane. Returning an error skips that lane (matches the Python
// `except Exception` branch in build_embedding_lanes).
type LaneBuilder func() (Encoder, error)

// BuildEmbeddingLanes returns the lanes the caller should serve, in
// retrieval-preference order: custom first, fastembed second. Any builder
// that returns an error is skipped — that matches the Python
// `try / except Exception` semantics.
//
// Each surviving lane is opened via getOrResetCollection, so an existing
// collection with a mismatched fingerprint is recreated and its rows
// preserved.
func BuildEmbeddingLanes(baseName string, chroma ChromaClient, customBuilder, fastembedBuilder LaneBuilder) ([]*EmbeddingLane, error) {
	if chroma == nil {
		return nil, fmt.Errorf("embedding_lanes: nil chroma client")
	}

	out := []*EmbeddingLane{}

	if customBuilder != nil {
		if client, err := customBuilder(); err == nil && client != nil {
			lane, laneErr := createLane(chroma, baseName, LANE_CUSTOM, client)
			if laneErr != nil {
				return nil, laneErr
			}
			out = append(out, lane)
		}
	}

	if fastembedBuilder != nil {
		if client, err := fastembedBuilder(); err == nil && client != nil {
			lane, laneErr := createLane(chroma, baseName, LANE_FASTEMBED, client)
			if laneErr != nil {
				return nil, laneErr
			}
			out = append(out, lane)
		}
	}

	return out, nil
}

// createLane materialises one lane: open or recreate the collection, then
// build the EmbeddingLane struct. The fingerprint mismatch path is delegated
// to getOrResetCollection so the recreate-and-restore logic is shared.
func createLane(chroma ChromaClient, baseName, laneName string, client Encoder) (*EmbeddingLane, error) {
	dimension := client.Dimension()
	model := client.Model()
	url := client.URL()
	fp := Fingerprint(laneName, url, model, dimension)
	name := CollectionName(baseName, laneName)
	meta := Metadata(laneName, url, model, dimension, fp)

	coll, err := getOrResetCollection(chroma, name, meta, client)
	if err != nil {
		return nil, err
	}

	return NewEmbeddingLane(laneName, client, coll, name, model, url, dimension, fp), nil
}

// LaneCount returns the largest row count across lanes, matching the Python
// max(...) defaulting to 0 when lanes is empty.
func LaneCount(lanes []*EmbeddingLane) int {
	best := 0
	for _, l := range lanes {
		if l == nil {
			continue
		}
		if c := l.Count(); c > best {
			best = c
		}
	}
	return best
}

// DedupeResults returns the first occurrence of each row keyed by idKey.
// Empty / missing ids are treated as duplicates (they are dropped), matching
// the Python `if not row_id or row_id in seen: continue` branch. When limit
// is non-nil and positive, the result is truncated to that many entries.
func DedupeResults[T any](rows []T, idKey func(T) string, limit int) []T {
	seen := make(map[string]struct{})
	out := make([]T, 0, len(rows))
	for _, row := range rows {
		id := idKey(row)
		if id == "" {
			continue
		}
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		out = append(out, row)
		if limit > 0 && len(out) >= limit {
			break
		}
	}
	return out
}

// NResultsFunc returns the per-lane result cap for QueryLanes. Mirrors the
// Python callable shape — it lets callers tune n per lane (e.g. cap by the
// lane's own row count) without copying logic.
type NResultsFunc func(*EmbeddingLane) int

// LaneQuery is one entry in the QueryLanes result: the lane that produced
// the hit and its raw QueryResult payload.
type LaneQuery struct {
	Lane   *EmbeddingLane
	Result QueryResult
}

// QueryLanes walks the supplied lanes, queries each one whose Count() > 0,
// and returns the per-lane results. It mirrors the Python query_lanes
// helper: empty lanes are skipped, a query that throws is recorded into the
// failures list, and when raiseIfAllFailed is true and every attempted lane
// failed the joined failure message is returned as an error.
func QueryLanes(lanes []*EmbeddingLane, query string, nResults NResultsFunc, include []string, where map[string]any, raiseIfAllFailed bool) ([]LaneQuery, error) {
	out := []LaneQuery{}
	attempted := 0
	var failures []string

	for _, lane := range lanes {
		if lane == nil {
			continue
		}
		count := lane.Count()
		if count == 0 {
			continue
		}
		attempted++
		n := nResults(lane)
		if n > count {
			n = count
		}
		if n <= 0 {
			continue
		}

		vecs, err := lane.Encode([]string{query})
		if err != nil {
			failures = append(failures, fmt.Sprintf("%s: %v", lane.Name, err))
			continue
		}
		result, err := lane.Collection.Query(vecs, n, where, include)
		if err != nil {
			failures = append(failures, fmt.Sprintf("%s: %v", lane.Name, err))
			continue
		}
		out = append(out, LaneQuery{Lane: lane, Result: result})
	}

	if raiseIfAllFailed && attempted > 0 && len(out) == 0 && len(failures) > 0 {
		return nil, fmt.Errorf("embedding_lanes: all lanes failed: %s", joinStrings(failures, "; "))
	}
	return out, nil
}

// joinStrings is a tiny strings.Join shim so we don't pull in the strings
// package just for one separator.
func joinStrings(parts []string, sep string) string {
	out := ""
	for i, p := range parts {
		if i > 0 {
			out += sep
		}
		out += p
	}
	return out
}

// MigrateLegacyCollection backfills rows from a legacy unsuffixed collection
// (baseName) into any lane that is missing them. Matches the Python
// migrate_legacy_collection helper: returns nil if no lanes are supplied, if
// the legacy collection is missing/unreadable, or if every missing-row
// backfill succeeds.
func MigrateLegacyCollection(baseName string, lanes []*EmbeddingLane, chroma ChromaClient) error {
	if len(lanes) == 0 || chroma == nil {
		return nil
	}

	legacy, err := chroma.GetCollection(baseName)
	if err != nil {
		return nil
	}
	data, getErr := legacy.Get(nil)
	if getErr != nil {
		return nil
	}
	if len(data.IDs) == 0 || len(data.Documents) == 0 {
		return nil
	}

	paddedMetas := padMetas(data.Metadatas, len(data.IDs))

	for _, lane := range lanes {
		if lane == nil || lane.Collection == nil {
			continue
		}

		existing, getErr := lane.Collection.Get(data.IDs)
		existingSet := make(map[string]struct{})
		if getErr == nil {
			for _, id := range existing.IDs {
				existingSet[id] = struct{}{}
			}
		}

		type missingRow struct {
			id   string
			doc  string
			meta map[string]any
		}
		var missing []missingRow
		for i, id := range data.IDs {
			if _, ok := existingSet[id]; ok {
				continue
			}
			missing = append(missing, missingRow{
				id:   id,
				doc:  data.Documents[i],
				meta: paddedMetas[i],
			})
		}
		if len(missing) == 0 {
			continue
		}

		for start := 0; start < len(missing); start += batchSize {
			end := start + batchSize
			if end > len(missing) {
				end = len(missing)
			}
			batch := missing[start:end]
			batchIDs := make([]string, 0, len(batch))
			batchDocs := make([]string, 0, len(batch))
			batchMetas := make([]map[string]any, 0, len(batch))
			for _, m := range batch {
				batchIDs = append(batchIDs, m.id)
				batchDocs = append(batchDocs, m.doc)
				if m.meta == nil {
					batchMetas = append(batchMetas, map[string]any{})
				} else {
					batchMetas = append(batchMetas, m.meta)
				}
			}
			vecs, encErr := lane.Encode(batchDocs)
			if encErr != nil {
				return fmt.Errorf("encode legacy rows for %s lane: %w", lane.Name, encErr)
			}
			if addErr := lane.Collection.Add(batchIDs, batchDocs, batchMetas, vecs); addErr != nil {
				return fmt.Errorf("backfill %s lane from %s: %w", lane.Name, baseName, addErr)
			}
		}
	}
	return nil
}
