// Package embeddinglanes keeps FastEmbed fallback vectors separate from
// user-configured embedding vectors. ChromaDB fixes a collection's
// dimension on first insert, so different embedding models must never
// share one collection.
//
// It is the Go port of src/embedding_lanes.py. The Python implementation
// is tightly coupled to ChromaDB and to a process-local embedding client
// registry; the Go port preserves the public behaviour (lanes keyed by
// (model, url, dimension), collection-name suffixing, fingerprint
// regeneration on mismatch) but exposes small interfaces so it can be
// driven from tests without a live Chroma server or real embedding
// client.
package embeddinglanes

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
)

// Public lane-name constants. These match the LANE_FASTEMBED / LANE_CUSTOM
// strings used by the Python source so any persisted Chroma collections
// stay compatible across the language boundary.
const (
	// LaneFastEmbed identifies the local FastEmbed fallback lane.
	LaneFastEmbed = "fastembed"
	// LaneCustom identifies the user-configured HTTP embedding lane.
	LaneCustom = "custom"
)

// Logger is the package-level logger used for informational and
// diagnostic output. Tests may replace it with a silent logger.
var Logger = log.New(os.Stderr, "[embeddinglanes] ", log.LstdFlags)

// ---------------------------------------------------------------------------
// Public interfaces (decouple the lane helpers from Chroma / embedding
// clients).
// ---------------------------------------------------------------------------

// EmbeddingClient is the minimal subset of an embedding client that the
// lane helpers actually use. The Python original calls
// `client.encode(texts, normalize_embeddings=True)` and
// `client.get_sentence_embedding_dimension()`; both behaviours are
// captured here.
type EmbeddingClient interface {
	// Encode turns a slice of texts into a slice of normalised embedding
	// vectors. Implementations may return either [][]float64 or a type
	// that satisfies ToListConverter.
	Encode(texts []string) any
	// Dimension returns the embedding dimensionality of this client.
	Dimension() int
	// Model returns the model identifier (may be empty for the FastEmbed
	// default).
	Model() string
	// URL returns the endpoint URL (may be empty for local clients).
	URL() string
}

// ChromaCollection is the subset of a Chroma collection the lane helpers
// need. The Python original relies on `count`, `get`, `add`, and `query`.
type ChromaCollection interface {
	Count() (int, error)
	Get(args ChromaGetArgs) (ChromaGetResult, error)
	Add(args ChromaAddArgs) error
	Query(args ChromaQueryArgs) (ChromaQueryResult, error)
}

// ChromaClient is the subset of chromadb.Client the lane helpers need.
type ChromaClient interface {
	GetCollection(name string) (ChromaCollection, error)
	GetOrCreateCollection(name string, metadata map[string]any) (ChromaCollection, error)
	DeleteCollection(name string) error
}

// ChromaGetArgs mirrors the kwargs that the Python code passes to
// collection.get / collection.query.
type ChromaGetArgs struct {
	IDs     []string
	Include []string
}

// ChromaGetResult mirrors the dict returned by collection.get.
type ChromaGetResult struct {
	IDs        []string
	Documents  []string
	Metadatas  []map[string]any
	Embeddings [][]float64 // preserved as [][]float64; Chroma numpy arrays must be converted upstream
}

// ChromaAddArgs mirrors the kwargs collection.add accepts.
type ChromaAddArgs struct {
	IDs        []string
	Documents  []string
	Metadatas  []map[string]any
	Embeddings [][]float64
}

// ChromaQueryArgs mirrors the kwargs collection.query accepts.
type ChromaQueryArgs struct {
	QueryEmbeddings [][]float64
	NResults        int
	Where           map[string]any
	Include         []string
}

// ChromaQueryResult mirrors the dict returned by collection.query.
type ChromaQueryResult struct {
	IDs       [][]string
	Documents [][]string
	Metadatas [][]map[string]any
	Distances [][]float64
}

// ToListConverter lets a client implementation return either a slice of
// floats or any type with a Tolist() [][]float64 method. Mirrors the
// Python `vecs.tolist() if hasattr(vecs, "tolist")` check.
type ToListConverter interface {
	ToList() [][]float64
}

// EncodeTexts normalises the client's Encode output to [][]float64.
// If the result already implements [][]float64, it is returned as-is.
// If it implements ToListConverter, ToList() is called. Anything else
// returns an error so callers see the failure rather than silently
// getting an empty result.
func EncodeTexts(client EmbeddingClient, texts []string) ([][]float64, error) {
	if client == nil {
		return nil, errors.New("embeddinglanes: nil client")
	}
	raw := client.Encode(texts)
	switch v := raw.(type) {
	case [][]float64:
		return v, nil
	case ToListConverter:
		return v.ToList(), nil
	case [][]float32:
		out := make([][]float64, len(v))
		for i, row := range v {
			out[i] = make([]float64, len(row))
			for j, f := range row {
				out[i][j] = float64(f)
			}
		}
		return out, nil
	default:
		return nil, fmt.Errorf("embeddinglanes: unsupported Encode result %T", raw)
	}
}

// ---------------------------------------------------------------------------
// EmbeddingLane value type.
// ---------------------------------------------------------------------------

// EmbeddingLane is one (client, collection) pair tied to a lane name.
// It mirrors the Python @dataclass EmbeddingLane.
type EmbeddingLane struct {
	Name           string
	Client         EmbeddingClient
	Collection     ChromaCollection
	CollectionName string
	Model          string
	URL            string
	Dimension      int
	Fingerprint    string
}

// Healthy reports whether the lane has both a live client and a live
// collection. Matches the `healthy` property in the Python source.
func (l *EmbeddingLane) Healthy() bool {
	return l != nil && l.Collection != nil && l.Client != nil
}

// Encode delegates to the embedded client and normalises the result to
// [][]float64. Returns an error if the client is missing or returns an
// unsupported shape.
func (l *EmbeddingLane) Encode(texts []string) ([][]float64, error) {
	if l == nil || l.Client == nil {
		return nil, errors.New("embeddinglanes: lane has no client")
	}
	return EncodeTexts(l.Client, texts)
}

// Count returns the live row count from the underlying collection.
// On error (collection missing, etc.) it returns 0 — matches the
// Python except-clause that swallows errors.
func (l *EmbeddingLane) Count() int {
	if l == nil || l.Collection == nil {
		return 0
	}
	n, err := l.Collection.Count()
	if err != nil {
		return 0
	}
	return n
}

// Stats returns a serialisable snapshot of the lane. Matches the
// `stats()` method on the Python dataclass.
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

// ---------------------------------------------------------------------------
// Pure helpers (collection_name, fingerprint, metadata).
// ---------------------------------------------------------------------------

// CollectionName returns the suffixed collection name used for a lane.
// Mirrors `f"{base_name}_{lane_name}"` from the Python source.
func CollectionName(baseName, laneName string) string {
	return baseName + "_" + laneName
}

// Fingerprint computes the 16-hex-char fingerprint used to detect lane
// drift. It hashes lane_name, url, model, and dimension into a SHA-256
// digest and takes the first 16 hex chars.
func Fingerprint(laneName, url, model string, dimension int) string {
	raw := fmt.Sprintf("%s\n%s\n%s\n%d", laneName, url, model, dimension)
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])[:16]
}

// Metadata builds the metadata dict written onto each Chroma collection
// to make fingerprint drift detectable.
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

// ---------------------------------------------------------------------------
// Reset hook (port of reset_embedding_lane_state).
// ---------------------------------------------------------------------------

// ResetHook is invoked by ResetState. The Python source calls
// `src.embeddings.reset_http_embed_state()` to drop any cached HTTP
// embedding client; the Go port invokes a swappable hook so tests can
// observe calls without a real embeddings package.
var ResetHook = func() {}

// ResetState drops any process-local embedding client cache. Mirrors
// `reset_embedding_lane_state`. Never returns an error — the Python
// version swallows everything; we follow suit so callers can safely
// invoke it after endpoint config changes.
func ResetState() {
	defer func() {
		// Match the Python except-clause that silently swallows errors.
		_ = recover()
	}()
	ResetHook()
}

// ---------------------------------------------------------------------------
// Collection retrieval with fingerprint-driven reset.
// ---------------------------------------------------------------------------

// GetOrResetCollection returns the existing collection if its
// fingerprint/dimension/lane match the requested metadata; otherwise it
// preserves the rows, recreates the collection with new metadata, and
// re-embeds the rows through `client`. On error during the new
// collection's add step the previous rows are restored from the
// preserved snapshot.
//
// Mirrors `_get_or_reset_collection`.
func GetOrResetCollection(
	chroma ChromaClient,
	client EmbeddingClient,
	name string,
	metadata map[string]any,
) (ChromaCollection, error) {
	if chroma == nil {
		return nil, errors.New("embeddinglanes: nil chroma client")
	}
	if client == nil {
		return nil, errors.New("embeddinglanes: nil embedding client")
	}

	collection, err := chroma.GetCollection(name)
	preservedOK := err == nil && collection != nil
	if !preservedOK {
		// No prior collection — create fresh.
		return chroma.GetOrCreateCollection(name, metadata)
	}

	current := readCollectionMetadata(collection)
	if !collectionDrift(current, metadata) {
		return collection, nil
	}

	Logger.Printf("Recreating Chroma collection %s for embedding lane change (%v -> %v)",
		name, current["embedding_fingerprint"], metadata["embedding_fingerprint"])

	preserved := ChromaGetResult{IDs: []string{}, Documents: []string{}, Metadatas: []map[string]any{}, Embeddings: [][]float64{}}
	if getErr := safeGetPreserved(collection, &preserved); getErr != nil {
		return nil, fmt.Errorf("embeddinglanes: could not preserve documents before resetting %s: %w", name, getErr)
	}

	preparedBatches := preparePreservedBatches(client, preserved)

	if delErr := chroma.DeleteCollection(name); delErr != nil {
		return nil, fmt.Errorf("embeddinglanes: delete collection %s: %w", name, delErr)
	}
	fresh, cErr := chroma.GetOrCreateCollection(name, metadata)
	if cErr != nil {
		return nil, fmt.Errorf("embeddinglanes: create collection %s: %w", name, cErr)
	}

	for _, b := range preparedBatches {
		if addErr := fresh.Add(b); addErr != nil {
			Logger.Printf("Could not write reset collection %s; restoring previous rows: %v", name, addErr)
			restoreErr := restorePrevious(chroma, name, current, preserved, preparedBatches, addErr)
			if restoreErr != nil {
				Logger.Printf("Could not restore previous collection %s: %v", name, restoreErr)
			}
			return nil, fmt.Errorf("embeddinglanes: could not write reset collection %s: %w", name, addErr)
		}
	}
	if len(preparedBatches) > 0 {
		Logger.Printf("Re-embedded %d rows after resetting %s", len(preserved.IDs), name)
	}
	return fresh, nil
}

// readCollectionMetadata reads metadata from the live collection. The
// Python original reads `collection.metadata`; a Chroma collection is
// expected to expose a `Metadata()` method on the Go port. We tolerate
// nil collections or missing metadata defensively.
func readCollectionMetadata(c ChromaCollection) map[string]any {
	if c == nil {
		return nil
	}
	if md, ok := c.(interface{ Metadata() map[string]any }); ok {
		return md.Metadata()
	}
	return nil
}

// collectionDrift returns true when the existing collection's
// fingerprint / dimension / lane differ from the requested metadata.
// Matches the `not (current.get(...) not in (None, md[...])))` block.
func collectionDrift(current, requested map[string]any) bool {
	if current == nil {
		return true
	}
	for _, k := range []string{"embedding_fingerprint", "embedding_dimension", "embedding_lane"} {
		cv := current[k]
		rv := requested[k]
		// Drift when current has a non-nil value that does not match
		// requested. The Python source uses `not in (None, requested)`
		// which means "current is None OR equal". We negate that here.
		if cv != nil && cv != rv {
			return true
		}
	}
	return false
}

// safeGetPreserved asks the collection for its rows + embeddings. Any
// error returns it to the caller.
func safeGetPreserved(collection ChromaCollection, out *ChromaGetResult) error {
	res, err := collection.Get(ChromaGetArgs{Include: []string{"documents", "metadatas", "embeddings"}})
	if err != nil {
		return err
	}
	*out = res
	return nil
}

// preparePreservedBatches re-embeds preserved documents through the
// client in batches of 100 (matches the Python `range(0, len(ids), 100)`).
// If the collection returned no IDs/documents, the slice is empty.
func preparePreservedBatches(client EmbeddingClient, preserved ChromaGetResult) []ChromaAddArgs {
	ids := preserved.IDs
	docs := preserved.Documents
	metas := preserved.Metadatas
	out := []ChromaAddArgs{}
	if len(ids) == 0 || len(docs) == 0 {
		return out
	}
	for start := 0; start < len(ids); start += 100 {
		end := start + 100
		if end > len(ids) {
			end = len(ids)
		}
		batchIDs := append([]string{}, ids[start:end]...)
		batchDocs := append([]string{}, docs[start:end]...)
		batchMetas := padMetadatas(metas[start:end], len(batchIDs))
		emb, err := EncodeTexts(client, batchDocs)
		if err != nil {
			// Preserve Python's "raise RuntimeError" behaviour.
			panic(fmt.Sprintf("embeddinglanes: re-embed preserved rows for failed: %v", err))
		}
		out = append(out, ChromaAddArgs{
			IDs:        batchIDs,
			Documents:  batchDocs,
			Metadatas:  batchMetas,
			Embeddings: emb,
		})
	}
	return out
}

// padMetadatas makes sure the metadatas slice is at least as long as
// the IDs slice, padding with empty maps where needed.
func padMetadatas(metas []map[string]any, want int) []map[string]any {
	if len(metas) >= want {
		return metas
	}
	out := append([]map[string]any{}, metas...)
	for i := len(out); i < want; i++ {
		out = append(out, map[string]any{})
	}
	return out
}

// restorePrevious tries to put the deleted collection back with the
// previous metadata + previously-stored embeddings. Mirrors the inner
// `try/except` block in `_get_or_reset_collection`.
//
// The Python original uses explicit None + len() checks to avoid
// numpy's truthy-ambiguity; we keep that idiom because the
// `Embeddings` field is an opaque `any`.
func restorePrevious(
	chroma ChromaClient,
	name string,
	previousMetadata map[string]any,
	preserved ChromaGetResult,
	_ []ChromaAddArgs,
	_ error,
) error {
	if delErr := chroma.DeleteCollection(name); delErr != nil {
		return delErr
	}
	restored, cErr := chroma.GetOrCreateCollection(name, previousMetadata)
	if cErr != nil {
		return cErr
	}
	oldEmbeddings := preserved.Embeddings
	if len(preserved.IDs) == 0 || len(preserved.Documents) == 0 || len(oldEmbeddings) == 0 {
		return nil
	}
	for start := 0; start < len(preserved.IDs); start += 100 {
		end := start + 100
		if end > len(preserved.IDs) {
			end = len(preserved.IDs)
		}
		batchIDs := append([]string{}, preserved.IDs[start:end]...)
		batchDocs := append([]string{}, preserved.Documents[start:end]...)
		batchMetas := padMetadatas(preserved.Metadatas[start:end], len(batchIDs))
		batchEmbs := append([][]float64{}, oldEmbeddings[start:end]...)
		if aErr := restored.Add(ChromaAddArgs{
			IDs:        batchIDs,
			Documents:  batchDocs,
			Metadatas:  batchMetas,
			Embeddings: batchEmbs,
		}); aErr != nil {
			return aErr
		}
	}
	return nil
}

// ---------------------------------------------------------------------------
// Lane construction.
// ---------------------------------------------------------------------------

// CreateLane builds an EmbeddingLane for the given lane name. It
// computes dimension + fingerprint from the client, builds the suffixed
// collection name, writes the metadata, and asks Chroma to either
// reuse or recreate the collection.
func CreateLane(
	chroma ChromaClient,
	baseName, laneName string,
	client EmbeddingClient,
) (*EmbeddingLane, error) {
	if chroma == nil {
		return nil, errors.New("embeddinglanes: nil chroma client")
	}
	if client == nil {
		return nil, errors.New("embeddinglanes: nil client")
	}
	dimension := client.Dimension()
	model := client.Model()
	url := client.URL()
	fp := Fingerprint(laneName, url, model, dimension)
	name := CollectionName(baseName, laneName)
	md := Metadata(laneName, url, model, dimension, fp)
	collection, err := GetOrResetCollection(chroma, client, name, md)
	if err != nil {
		return nil, err
	}
	return &EmbeddingLane{
		Name:           laneName,
		Client:         client,
		Collection:     collection,
		CollectionName: name,
		Model:          model,
		URL:            url,
		Dimension:      dimension,
		Fingerprint:    fp,
	}, nil
}

// ---------------------------------------------------------------------------
// Lane wiring (custom + fastembed).
// ---------------------------------------------------------------------------

// ClientBuilders is the set of factory functions the port uses to
// construct the per-lane clients. Tests can swap these out without
// importing a real embedding backend.
//
// CustomBuilder is consulted first; FastEmbedBuilder is the fallback.
// Either may return (nil, nil) to indicate "lane not available" (the
// caller treats that as a soft skip rather than an error).
type ClientBuilders struct {
	CustomBuilder    func() (EmbeddingClient, error)
	FastEmbedBuilder func() (EmbeddingClient, error)
}

// BuildLanes returns the available lanes for `baseName` in retrieval
// preference order: custom first, then fastembed. Either lane may be
// skipped if its builder returns (nil, nil) or an error — both are
// treated as "not available" to mirror the Python source's
// `try/except` blocks that warn-and-continue.
//
// `chroma` is required; if it is nil the function returns an empty
// slice with no error (matches the Python `get_chroma_client()` behaviour
// where a missing client logs a warning and yields zero lanes).
func BuildLanes(chroma ChromaClient, baseName string, builders ClientBuilders) []*EmbeddingLane {
	if chroma == nil {
		Logger.Printf("BuildLanes: no chroma client; returning empty lane list for %s", baseName)
		return nil
	}
	lanes := []*EmbeddingLane{}

	if builders.CustomBuilder != nil {
		c, err := builders.CustomBuilder()
		if err != nil {
			Logger.Printf("Custom embedding lane unavailable for %s: %v", baseName, err)
		} else if c != nil {
			lane, lerr := CreateLane(chroma, baseName, LaneCustom, c)
			if lerr != nil {
				Logger.Printf("Custom embedding lane unavailable for %s: %v", baseName, lerr)
			} else {
				lanes = append(lanes, lane)
			}
		}
	}

	if builders.FastEmbedBuilder != nil {
		c, err := builders.FastEmbedBuilder()
		if err != nil {
			Logger.Printf("FastEmbed lane unavailable for %s: %v", baseName, err)
		} else if c != nil {
			lane, lerr := CreateLane(chroma, baseName, LaneFastEmbed, c)
			if lerr != nil {
				Logger.Printf("FastEmbed lane unavailable for %s: %v", baseName, lerr)
			} else {
				lanes = append(lanes, lane)
			}
		}
	}
	return lanes
}

// ---------------------------------------------------------------------------
// Legacy collection migration.
// ---------------------------------------------------------------------------

// MigrateLegacyCollection copies rows from a legacy unsuffixed
// collection into any empty lanes. Mirrors `migrate_legacy_collection`.
// Errors during the lookup of the legacy collection are silently
// ignored (the legacy collection simply may not exist).
func MigrateLegacyCollection(chroma ChromaClient, baseName string, lanes []*EmbeddingLane) {
	if chroma == nil || len(lanes) == 0 {
		return
	}
	legacy, err := chroma.GetCollection(baseName)
	if err != nil || legacy == nil {
		return
	}
	data, gErr := legacy.Get(ChromaGetArgs{Include: []string{"documents", "metadatas"}})
	if gErr != nil {
		return
	}
	ids := data.IDs
	docs := data.Documents
	metas := data.Metadatas
	if len(ids) == 0 || len(docs) == 0 {
		return
	}

	for _, lane := range lanes {
		existingIDs := map[string]struct{}{}
		if lane != nil && lane.Collection != nil {
			if existing, eErr := lane.Collection.Get(ChromaGetArgs{IDs: ids}); eErr == nil {
				for _, id := range existing.IDs {
					existingIDs[id] = struct{}{}
				}
			}
		}
		allMetas := append([]map[string]any{}, metas...)
		allMetas = padMetadatas(allMetas, len(ids))

		missing := make([]int, 0, len(ids))
		for i, id := range ids {
			if _, ok := existingIDs[id]; ok {
				continue
			}
			missing = append(missing, i)
		}
		if len(missing) == 0 {
			continue
		}

		failed := false
		for start := 0; start < len(missing); start += 100 {
			end := start + 100
			if end > len(missing) {
				end = len(missing)
			}
			batchIdx := missing[start:end]
			batchIDs := make([]string, 0, len(batchIdx))
			batchDocs := make([]string, 0, len(batchIdx))
			batchMetas := make([]map[string]any, 0, len(batchIdx))
			for _, idx := range batchIdx {
				batchIDs = append(batchIDs, ids[idx])
				batchDocs = append(batchDocs, docs[idx])
				batchMetas = append(batchMetas, allMetas[idx])
			}
			batchMetas = padMetadatas(batchMetas, len(batchIDs))

			emb, encErr := lane.Encode(batchDocs)
			if encErr != nil {
				Logger.Printf("Could not backfill %s lane from legacy collection %s: %v",
					lane.Name, baseName, encErr)
				failed = true
				break
			}
			if addErr := lane.Collection.Add(ChromaAddArgs{
				IDs:        batchIDs,
				Documents:  batchDocs,
				Metadatas:  batchMetas,
				Embeddings: emb,
			}); addErr != nil {
				Logger.Printf("Could not backfill %s lane from legacy collection %s: %v",
					lane.Name, baseName, addErr)
				failed = true
				break
			}
		}
		if !failed {
			Logger.Printf("Backfilled %d %s lane rows from legacy collection %s",
				len(missing), lane.Name, baseName)
		}
	}
}

// ---------------------------------------------------------------------------
// Aggregate helpers.
// ---------------------------------------------------------------------------

// LaneCount returns the maximum count across the given lanes, or 0 if
// `lanes` is empty. Mirrors the Python `max((... for lane in lanes), default=0)`.
func LaneCount(lanes []*EmbeddingLane) int {
	if len(lanes) == 0 {
		return 0
	}
	max := 0
	for _, l := range lanes {
		if l == nil {
			continue
		}
		if c := l.Count(); c > max {
			max = c
		}
	}
	return max
}

// DedupeResults collapses a stream of result dicts down to unique IDs,
// optionally truncating to `limit`. Mirrors `dedupe_results`.
//
// `idKey` selects which field identifies a row (default "id"). Rows
// with an empty or missing id are skipped.
func DedupeResults(results []map[string]any, idKey string, limit int) []map[string]any {
	if idKey == "" {
		idKey = "id"
	}
	seen := map[string]struct{}{}
	out := make([]map[string]any, 0, len(results))
	for _, row := range results {
		raw, ok := row[idKey]
		if !ok || raw == nil {
			continue
		}
		id, ok := raw.(string)
		if !ok || id == "" {
			continue
		}
		if _, dup := seen[id]; dup {
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

// QueryNFunc returns how many results to ask of a lane.
type QueryNFunc func(lane *EmbeddingLane) int

// LaneQueryResult bundles the lane with its raw query payload.
type LaneQueryResult struct {
	Lane    *EmbeddingLane
	Results ChromaQueryResult
}

// QueryLanes fans the query out to each lane, skipping lanes whose
// count is 0. If `raiseIfAllFailed` is true and every attempted lane
// failed, the joined error is returned. Mirrors `query_lanes`.
func QueryLanes(
	lanes []*EmbeddingLane,
	query string,
	nResults QueryNFunc,
	include []string,
	where map[string]any,
	raiseIfAllFailed bool,
) ([]LaneQueryResult, error) {
	out := []LaneQueryResult{}
	attempted := 0
	failures := []string{}
	for _, lane := range lanes {
		if lane == nil || lane.Collection == nil || lane.Client == nil {
			continue
		}
		count := lane.Count()
		if count == 0 {
			continue
		}
		attempted++
		n := nResults(lane)
		if n <= 0 {
			continue
		}
		if n > count {
			n = count
		}
		emb, err := lane.Encode([]string{query})
		if err != nil {
			failures = append(failures, fmt.Sprintf("%s: %v", lane.Name, err))
			Logger.Printf("%s lane encode failed for %s: %v", lane.Name, lane.CollectionName, err)
			continue
		}
		res, qErr := lane.Collection.Query(ChromaQueryArgs{
			QueryEmbeddings: emb,
			NResults:        n,
			Where:           where,
			Include:         include,
		})
		if qErr != nil {
			failures = append(failures, fmt.Sprintf("%s: %v", lane.Name, qErr))
			Logger.Printf("%s lane query failed for %s: %v", lane.Name, lane.CollectionName, qErr)
			continue
		}
		out = append(out, LaneQueryResult{Lane: lane, Results: res})
	}
	if raiseIfAllFailed && attempted > 0 && len(out) == 0 && len(failures) > 0 {
		return out, errors.New(strings.Join(failures, "; "))
	}
	return out, nil
}

// ---------------------------------------------------------------------------
// String formatting helpers.
// ---------------------------------------------------------------------------

// FormatInt is a small convenience used in log messages; mirrors the
// Python `%s` interpolation used in the original.
func FormatInt(n int) string {
	return strconv.Itoa(n)
}
