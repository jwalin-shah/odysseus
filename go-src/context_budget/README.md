# context_budget (Go port)

Go port of `src/context_budget.py` — the adaptive input-token budget
helper for the agent loop (#1170, follow-up hardening in #1230 and #4122).

The Python module exposes two pure, side-effect-free functions:

```python
DEFAULT_HARD_MAX = 200_000
DEFAULT_BUDGET = 6_000
DEFAULT_HEADROOM = 0.85

def compute_input_token_budget(
    configured: int,
    context_length: int,
    explicit: bool,
    *,
    default: int = DEFAULT_BUDGET,
    headroom: float = DEFAULT_HEADROOM,
    hard_max: int = DEFAULT_HARD_MAX,
) -> int: ...

def budget_is_explicit(
    configured: int,
    *,
    default: int = DEFAULT_BUDGET,
) -> bool: ...
```

The Go port preserves both contracts and adds no behavior of its own.

## Why this exists

The old soft-trim was `min(context_length or budget, budget)`, which
made the 6000 default a hard ceiling for *every* model — a 128K or 1M
context model was silently capped at 6000 input tokens even though it
can hold far more. This module derives the effective budget from the
model's discovered context window when the user has NOT set an
explicit budget, while still honouring an explicit setting exactly
(clamped to the window).

## Public API

```go
import "github.com/odysseus/context_budget/pkg/contextbudget"

const (
    DefaultHardMax  = 200_000
    DefaultBudget   = 6_000
    DefaultHeadroom = 0.85
)

type Options struct {
    Configured    int
    ContextLength int
    Explicit      bool
    Default       int
    Headroom      float64
    HardMax       int
}

func DefaultOptions() Options
func (o Options) With(configured, contextLength int, explicit bool) Options
func (o Options) WithDefault(d int) Options
func (o Options) WithHeadroom(h float64) Options
func (o Options) WithHardMax(m int) Options

func ComputeInputTokenBudget(opts Options) int
func BudgetIsExplicit(configured int, opts Options) bool
```

The fluent `With*` methods mirror Python's keyword-only arguments;
`DefaultOptions()` seeds every field with the package constants, then
each `With` returns a copy. Zero allocations beyond the stack-allocated
copy — call sites stay readable.

## Rules preserved from Python

1. **Explicit user budget wins** (`explicit && configured > 0`):
   return `min(configured, contextLength)` when the window is known,
   otherwise return `configured` as-is. `DefaultHardMax` does NOT cap
   an explicit user choice — that ceiling is auto-budget only (#1230).

2. **Auto path with a known window** (`contextLength > 0`):
   `scaled = int(contextLength * headroom)`; return
   `max(1, min(scaled, HardMax))`.

3. **Auto path with an unknown window** (`contextLength == 0`):
   return `configured` if `> 0`, otherwise `Default`.

4. **Defensive coercion**: negative `Configured` and `ContextLength`
   are normalised to zero, mirroring `int(x or 0)`.

`BudgetIsExplicit` keys off the VALUE, not settings *presence*: only
a positive value different from the (possibly overridden) default
counts as explicit. This is the materialized-default contract from
#4121 / #1230 — a persisted default must still read as auto.

## Mapping (Python → Go)

| Python                                        | Go                                                           |
|-----------------------------------------------|--------------------------------------------------------------|
| `DEFAULT_HARD_MAX`                            | `contextbudget.DefaultHardMax`                               |
| `DEFAULT_BUDGET`                              | `contextbudget.DefaultBudget`                                |
| `DEFAULT_HEADROOM`                            | `contextbudget.DefaultHeadroom`                              |
| `compute_input_token_budget(configured, ctx, explicit, *, default, headroom, hard_max)` | `contextbudget.ComputeInputTokenBudget(DefaultOptions().With(configured, ctx, explicit).WithDefault(...).WithHeadroom(...).WithHardMax(...))` |
| `budget_is_explicit(configured, *, default)`  | `contextbudget.BudgetIsExplicit(configured, DefaultOptions().WithDefault(...))` |

## Layout

```
context_budget/
├── go.mod
├── README.md
├── pkg/contextbudget/
│   ├── options.go              # constants + Options struct + DefaultOptions + With*
│   ├── budget.go               # ComputeInputTokenBudget
│   ├── explicit.go             # BudgetIsExplicit
│   ├── constants.go            # package doc placeholder
│   ├── budget_test.go          # Compute* table-driven + named branch tests
│   └── explicit_test.go        # BudgetIsExplicit table-driven + named cases
└── cmd/contextbudget-demo/
    └── main.go                 # CLI with --help / --list-tests / --print-all
```

## Demo CLI

```bash
cd go-src/context_budget

go run ./cmd/contextbudget-demo                      # single-call path (uses --configured etc.)
go run ./cmd/contextbudget-demo --print-all          # matrix of representative scenarios
go run ./cmd/contextbudget-demo --help               # usage
go run ./cmd/contextbudget-demo --list-tests         # scenario names
```

Sample `--print-all` output (abbreviated):

```
== context_budget demo ==

[explicit user budget clamped to window] configured=4000 contextLength=128000 explicit=true -> 4000
[auto budget scales to 128k window] configured=6000 contextLength=128000 explicit=false -> 108800
[auto budget hits hard-max ceiling on 2M window] configured=6000 contextLength=2000000 explicit=false -> 200000
[unknown window falls back to default] configured=0 contextLength=0 explicit=false -> 6000
[explicit user budget returned as-is when window unknown] configured=4000 contextLength=0 explicit=true -> 4000
[explicit zero configured falls through to auto] configured=0 contextLength=128000 explicit=true -> 108800
[custom headroom 0.5 on 4k window] configured=0 contextLength=4000 explicit=false -> 2000
[explicit user budget bypasses small hard max] configured=180000 contextLength=0 explicit=true -> 180000

[budget_is_explicit]
  configured=0          -> explicit=false
  configured=6000       -> explicit=false (default = auto sentinel)
  configured=1          -> explicit=true
  configured=6001       -> explicit=true
  configured=-1         -> explicit=false (defensive coercion)
  configured=6000 (WithDefault(6000)) -> explicit=false
  configured=6000 (WithDefault(5000)) -> explicit=true
```

## Tests

```bash
cd go-src/context_budget
go build ./...
go test -race ./...
go vet ./...
```

Coverage (table-driven in both `*_test.go` files):

- Explicit user budget honoured and clamped in both directions
  (configured below window, configured above window).
- Explicit values are NOT capped at `HardMax` (the #1230 contract).
- Explicit with `configured == 0` falls through to the auto path.
- Auto scaling, hard-cap at `2_000_000` window, and the floor of 1.
- Auto fallback to `configured > 0` and then `Default`.
- Negative inputs normalised to zero (matches `int(x or 0)`).
- `BudgetIsExplicit` covers zero / default / just-above / negative /
  `WithDefault` match / `WithDefault` mismatch.

## Out of scope

- **Flask integration**: the Python module is consumed by the agent
  loop and settings loader. The Go port exposes the same surface but
  does not wrap a Flask handler. Callers wire it up directly.
- **Settings persistence**: this module derives a number from settings;
  it does not load or save them. The settings layer is responsible for
  populating `Configured` / `Explicit` correctly (the materialized-
  default contract is enforced by `BudgetIsExplicit`).
- **Headroom range-checking**: the Python source documents `headroom`
  as a tunable in `(0, 1]` but does not range-check. The Go port
  matches that — passing `<= 0` or `> 1` produces nonsense but does
  not panic.