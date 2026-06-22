# url_security (Go port)

Go port of `src/url_security.py` — validation helpers for server-side outbound
URLs supplied by untrusted callers (web/API tokens, embedding endpoint config,
custom web tools, etc.).

This package lives in its own module (`github.com/odysseus/url_security`) so
that other Go services can drop it in without pulling the entire odysseus
graph. It has **zero external dependencies** — only Go stdlib
(`net`, `net/url`, `strings`, `errors`).

## What this package does

`url_security` enforces *fail-closed* outbound URL validation for
user-supplied destinations. The companion `src/url_safety.py` is a
different, more permissive policy that targets the embedding endpoint
(local-first defaults: private/loopback allowed by default). This package is
the **strict** policy: only public, http(s) hosts are allowed.

Specifically, `url_security`:

- Requires the URL scheme to be `http` or `https` (rejects `file://`,
  `gopher://`, `ftp://`, `javascript:`, etc.).
- Resolves the host via `getaddrinfo` and rejects if any A/AAAA record
  points at a private, loopback, link-local, multicast, reserved, or
  unspecified network. This is the SSRF metadata-service guard.
- Rejects well-known cloud metadata hostnames even when DNS is broken
  (`localhost`, `metadata`, `metadata.google.internal`, plus suffixes
  `.localhost`, `.local`, `.internal`, `.lan`, `.intranet`).
- Fails closed on DNS errors (no answer = blocked).
- Caps URL length at 2048 characters by default.

## What this package does NOT do (that `url_safety` does)

- It does **not** allow private/loopback destinations by default. If you
  need a local-first policy for an embedded model server, use
  `url_safety.check_outbound_url(..., block_private=False)`.
- It does **not** classify an IP with the `(ok, reason)` tuple API —
  it raises `errors.New` from the strict validator and returns a plain
  `bool` from the lax predicate.
- It does **not** include the IPv4-mapped IPv6 explicit downgrade
  branch that `url_safety._classify` uses; in Go the
  `net.ParseIP` + `ip.To4()` chain handles that case uniformly via
  the standard library's `IP.IsPrivate`, `IP.IsLoopback`,
  `IP.IsLinkLocal`, etc.

## Public API

```go
// pkg/urlsecurity/validators.go
func IsPublicHTTPURL(rawURL string) bool
func ValidatePublicHTTPURL(rawURL string, maxLength int) (string, error)
func DefaultMaxLength() int

// pkg/urlsecurity/types.go
type Verdict struct {
    URL     string
    Reason  string
    Private bool   // true when the host resolved to a private/loopback/link-local address
    IP      string // first resolved IP (when resolution succeeded); "" otherwise
}

func Classify(rawURL string) Verdict

// pkg/urlsecurity/internal.go (low-level helpers, exported for tests)
func ResolveHostnameIPs(hostname string) []net.IP
func IsBlockedIP(addr net.IP) bool
func IsInternalHostname(host string) bool
```

The Go port uses Go's `net.IP` instead of Python's
`ipaddress._BaseAddress`. All other blocklists/suffixes mirror the Python
source 1:1.

## Usage

```go
import urlsecurity "github.com/odysseus/url_security/pkg/urlsecurity"

ok := urlsecurity.IsPublicHTTPURL("https://example.com/data")
cleaned, err := urlsecurity.ValidatePublicHTTPURL(userSupplied, 2048)
if err != nil {
    return fmt.Errorf("rejecting outbound URL: %w", err)
}
resp, err := http.Get(cleaned)
```

## DNS-rebinding note

`ValidatePublicHTTPURL` resolves the hostname once at validation time and
inspects every A/AAAA record. This is the same strategy the Python port
uses and is documented in its docstring as reducing obvious private-network
targets but **not** eliminating every DNS rebinding race by itself.
Callers that load a URL between validation and the actual HTTP request
should re-pin the resolved IP at request time (e.g. with a `Dial`
override that refuses to connect to anything but the validated address).
That pinning lives outside the scope of this port.

## Layout

```
url_security/
├── go.mod
├── README.md
├── pkg/urlsecurity/
│   ├── types.go         # Verdict type + Classify
│   ├── validators.go    # IsPublicHTTPURL, ValidatePublicHTTPURL, DefaultMaxLength
│   ├── internal.go      # hostname/IP helpers (exported)
│   └── validators_test.go
└── cmd/urlsecurity-demo/
    └── main.go          # small CLI: --url prints the verdict
```

## Demo

```
go run ./cmd/urlsecurity-demo --url https://example.com
```

Output: `VERDICT: ok url=https://example.com ip=... reason=...`