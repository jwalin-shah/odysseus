# deep_research (Go port)

Go port of [`src/deep_research.py`](../../src/deep_research.py) — the
IterResearch-style deep research engine that runs an iterative
Think→Search→Extract→Synthesize loop driven by an LLM. Each round the model
decides what to search, what's relevant, what's missing, and when to stop.

The Python module wraps an injected `LLM` callable around Flask / DB / search
provider plumbing that lives elsewhere in Odysseus. The Go port preserves the
loop logic verbatim but inverts the dependencies: callers wire four injected
function types (`LLMFunc`, `SearchFunc`, `FetchFunc`, `ProgressFunc`) into the
engine, so the package itself stays in-memory, stdlib-only, and free of
Flask, SQLAlchemy, or any HTTP client.

## What this package does

```go
type DeepResearcher struct { /* ... */ }

func New(cfg Config, deps Deps) *DeepResearcher
func (d *DeepResearcher) Research(ctx context.Context, question string, priorReport string, priorFindings []Finding, priorURLs []string) (string, error)
func (d *DeepResearcher) Cancel()
func (d *DeepResearcher) Stats() Stats
func (d *DeepResearcher) RecordProvider(name string)
```

`Research` runs up to `Config.MaxRounds` rounds. Each round:

1. **THINK** — `Deps.LLM` is asked for a JSON array of search queries.
2. **SEARCH** — `Deps.Search` returns search hits for each query (parallel).
3. **EXTRACT** — `Deps.Fetch` retrieves the top URLs; `Deps.LLM` extracts
   `rational` / `evidence` / `summary` JSON for each.
4. **SYNTHESIZE** — `Deps.LLM` is asked to merge the last
   `Config.SynthesisWindow` findings into the evolving report.
5. **DECIDE** — once `MinRounds` is reached, `Deps.LLM` is asked whether the
   report is comprehensive enough to stop.

When the loop ends the engine produces a final, long-form report (with an
expansion pass if the first draft is under 400 words) and returns it.

## Public API

```go
import (
    "context"

    deepresearch "github.com/jwalinshah/odysseus/deep_research/pkg/deepresearch"
)

cfg := deepresearch.Config{
    Model:                 "gpt-4o",
    MaxRounds:             8,
    MaxTimeSec:            300,
    MaxURLsPerRound:       3,
    MaxContentChars:       15000,
    MaxReportTokens:       8192,
    ExtractionTimeoutSec:  90,
    PlanningTimeoutSec:    90,
    QueryTimeoutSec:       120,
    ExtractionConcurrency: 3,
    MinRounds:             2,
    MaxEmptyRounds:        2,
    SynthesisWindow:       10,
}

deps := deepresearch.Deps{
    LLM:           myLLM,
    Search:        mySearch,
    Fetch:         myFetch,
    StripThinking: myStripThinking,
    Progress:      myProgress,
}

r := deepresearch.New(cfg, deps)
report, err := r.Research(ctx, "What is Go?", "", nil, nil)
stats := r.Stats()
```

`Stats` returns a `Stats` struct with `Duration`, `Rounds`, `Queries`, `URLs`,
`Model`, plus optional `Search` and `Category` fields populated from
`RecordProvider` and the auto-detected (or pre-set) category.

## Layout

```
deep_research/
├── go.mod                    # module github.com/jwalinshah/odysseus/deep_research, go 1.22
├── README.md                 # this file
├── pkg/deepresearch/
│   ├── types.go              # Finding, SearchResult, FetchedPage, Stats, Config, DeepResearcher, AnalyzedURL
│   ├── parser.go             # StripCodeBlock, ParseJSONArray, ParseJSONObject, FormatFindings, FallbackReport
│   ├── prompts.go            # prompt templates + CurrentDateContext
│   ├── researcher.go         # Deps, LLMFunc/SearchFunc/FetchFunc/ProgressFunc, New, Research, Cancel, Stats, RecordProvider
│   └── researcher_test.go    # table-driven tests for every exported function
└── cmd/deepresearch-demo/
    └── main.go               # runnable demo wiring stub deps
```

## Design choices

- **Inverted dependencies.** The Python source reaches into `src.llm_core`,
  `src.search.providers`, `src.goal_based_extractor`, and
  `src.prompt_security` at call time. The Go port moves all of those into
  `Deps` so the package has no implicit global state and zero external
  dependencies beyond the standard library.
- **Cooperative cancellation via `Cancel()` and `ctx`.** `Cancel()` flips an
  atomic flag; `ctx` is checked between rounds and inside the bounded
  fetch goroutines. Either source of cancellation aborts the run cleanly.
- **JSON repair utilities.** `ParseJSONArray` and `ParseJSONObject` mirror
  the Python implementation's multi-pass repair strategy (strip fences →
  strict parse → greedy outermost match → non-greedy scan → quoted-string
  harvest) so the package survives the same kinds of LLM output quirks the
  Python engine does.
- **`FormatFindings` / `FallbackReport` are exported** because they have
  value outside the engine itself — callers wiring custom UI can reuse the
  exact same markdown layout the Python version emits.
- **`RecordProvider` is exported** so a caller-supplied `SearchFunc` can
  publish the actual provider that served results (e.g. "searxng"), which
  the engine then surfaces in `Stats.Search` and via `progress` events.

## Out of scope (Python-only at runtime)

These pieces of the Python module are deliberately not ported — they
require live infrastructure that lives in other parts of the Odysseus repo:

- **Flask integration.** `src/deep_research.py` is invoked from a Flask
  route that streams progress via `progress_callback`. The Go port treats
  the callback as an injected `ProgressFunc` instead — there is no HTTP
  layer here.
- **LLM transport.** `src.llm_core.llm_call_async` makes the real HTTP call
  to the configured endpoint. The Go port takes an `LLMFunc` and trusts the
  caller to wire it to whatever transport they want.
- **SearXNG / Brave / Tavily provider chain.** `_build_provider_chain`,
  `_call_provider`, and the provider settings table are out of scope; the
  Go port treats search as an opaque function returning `[]SearchResult`.
- **`fetch_webpage_content`.** The Python module pulls the URL fetch
  implementation from `src.search`. The Go port takes a `FetchFunc` instead.
- **`EXTRACTOR_SYSTEM` is duplicated** as `ExtractorSystem` here, and
  `untrusted_context_message` is reproduced inline in `fetchAndExtract`.
  Both are the minimal subset of those helpers needed by the loop.
- **`is_low_quality`** from `src.research_utils` is duplicated as the
  unexported `isLowQuality` so the package stays stdlib-only.

These are all explained inline in the relevant files (see the long
docstrings in `researcher.go`).

## Running tests

```bash
cd go-src/deep_research
go build ./...
go test -race ./...
go vet ./...
```

Tests are pure stdlib `testing` — no fixtures, no network, no temp files.
The integration test (`TestResearch_RoundTrip`) wires a scripted LLM stub,
a fake search, and a fake fetch to walk one full round of the engine.

## Demo CLI

```bash
cd go-src/deep_research
go run ./cmd/deepresearch-demo
```

The demo wires stub `Deps` (the LLM returns a canned research plan, the
search returns one URL, the fetch returns one paragraph about Go) so the
whole loop can be exercised without any external services. It prints the
final report and the `Stats` struct.

## Port notes

- The Python module is a single ~900-line file; the Go port is split into
  `types.go`, `parser.go`, `prompts.go`, and `researcher.go` to keep the
  public surface scannable. Public function names match the Python ones
  where possible (`New`, `Research`, `Cancel`, `Stats`, `RecordProvider`).
- `progress_callback(kwargs)` becomes `ProgressFunc(event map[string]any)`.
  Events still use the same string keys (`phase`, `round`, `queries`,
  `total_sources`, `total_findings`, `message`, ...).
- `strip_thinking` is injected as `Deps.StripThinking` rather than imported
  from a shared utility. The default is identity if the field is nil.
- `get_stats()` returns a `map[string]string` in Python; the Go port
  returns a typed `Stats` struct so callers get field-level access.
- Set/dedupe logic (`queries_used`, `urls_fetched`, `providers_used`) is
  preserved as `map[string]struct{}` and a slice respectively, mirroring
  the Python `Set` / `List` semantics.
