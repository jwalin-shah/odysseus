package deepresearch

import (
	"sync"
	"time"
)

// Finding mirrors the dict shape returned by the extractor's JSON object:
// "url", "title", "og_image", "rational", "evidence", "summary".  Kept as a
// struct so the rest of the package does not have to pass map[string]any
// around.
type Finding struct {
	URL      string
	Title    string
	OGImage  string
	Rational string
	Evidence string
	Summary  string
}

// SearchResult is the minimal shape returned by the injected Search dep.
type SearchResult struct {
	URL   string
	Title string
}

// FetchedPage mirrors the dict returned by src.search.fetch_webpage_content
// ("success", "title", "content", "og_image").
type FetchedPage struct {
	Success bool
	Title   string
	Content string
	OGImage string
}

// Stats is the shape returned by DeepResearcher.Stats().  Mirrors the
// Python get_stats() dict.
type Stats struct {
	Duration string
	Rounds   int
	Queries  int
	URLs     int
	Model    string
	Search   string
	Category string
}

// Config bundles the knobs the Python DeepResearcher exposes via its
// constructor.  The Go port injects everything via Deps instead of network
// calls, so it leaves out the live endpoint/header fields.
type Config struct {
	Model                  string
	MaxRounds              int
	MaxTimeSec             int
	MaxURLsPerRound        int
	MaxContentChars        int
	MaxReportTokens        int
	ExtractionTimeoutSec   int
	PlanningTimeoutSec     int
	QueryTimeoutSec        int
	ExtractionConcurrency  int
	MinRounds              int
	MaxEmptyRounds         int
	SynthesisWindow        int
	SearchProviderOverride string
	Category               string
}

// DeepResearcher mirrors the Python class state.  Public fields exist so
// callers (and tests) can inspect them after a run; methods are the only
// correct way to mutate them.
type DeepResearcher struct {
	Cfg             Config
	Deps            Deps
	QueriesUsed     map[string]struct{}
	URLsFetched     map[string]struct{}
	AnalyzedURLs    []AnalyzedURL
	RoundCount      int
	ProvidersUsed   []string
	Findings        []Finding
	EvolvingReport  string
	ResearchPlan    string
	Category        string
	LastSearchError string

	mu        sync.Mutex // guards cancel/startTime
	cancelled bool
	startTime time.Time
}

// AnalyzedURL records a URL the researcher decided to fetch.
type AnalyzedURL struct {
	URL   string
	Title string
}
