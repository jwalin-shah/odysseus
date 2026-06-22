# url_safety (Go port)

Go port of `src/url_safety.py`. The Python module is a small SSRF-hardening
guard: it validates user-supplied URLs **before** the server makes an
outbound HTTP request, so a caller cannot trick Odysseus into fetching
`http://169.254.169.254/latest/meta-data/` and exfiltrating cloud
credentials, or `file:///etc/passwd` to read local files.

## Scope

This package does NOT re-implement the outbound HTTP request itself. It
is a pure validation library that returns "ok" or a rejection reason.
The caller (Odysseus' `httpx`-using endpoint handler) does the actual
fetch.

The port captures every public function from the Python source:

| Python | Go | Notes |
| --- | --- | --- |
| `ALLOWED_SCHEMES` | `urlsafety.AllowedSchemes` | exact same whitelist |
| `_default_resolver(host)` | `urlsafety.DefaultResolver` | uses `net.LookupHost` (A + AAAA) |
| `_classify(ip, block_private)` | `urlsafety.ClassifyIP` | unwraps IPv4-mapped IPv6 |
| `check_outbound_url(url, block_private, resolver)` | `urlsafety.Check` | returns a `Result` struct instead of `(ok, reason)` tuple |

## Threat model

| Threat | Default behaviour | With `BlockPrivate=true` |
| --- | --- | --- |
| Non-HTTP(S) scheme (`file://`, `javascript:`, `data:`, `vbscript:`, `gopher://`, `ftp://`, ...) | Reject | Reject |
| Link-local (`169.254.0.0/16`, `fe80::/10`) — cloud instance-metadata SSRF | Reject | Reject |
| Multicast / reserved / unspecified addresses (`0.0.0.0`, `::`, `224.0.0.0/4`, `240.0.0.0/4`) | Reject | Reject |
| IPv4-mapped IPv6 (e.g. `::ffff:169.254.169.254`) — unwrapped before classification | Reject | Reject |
| Private (`10/8`, `172.16/12`, `192.168/16`, `fc00::/7`) | Allow (local-first embedding endpoints) | Reject |
| Loopback (`127.0.0.0/8`, `::1`) | Allow (local-first embedding endpoints) | Reject |
| Punycode / IDN homograph attacks | **Not enforced** — surfaced via `InspectIDN` for the caller to log | Same |
| Empty / missing / whitespace URL | Reject ("URL is required") | Reject |
| Unresolvable host | Reject ("host does not resolve") | Reject |

IDN homograph detection is intentionally not enforced by `Check` itself.
The validator's job is the SSRF guard; the IDN heuristic lives in
`InspectIDN` so callers can decide whether to log, warn, or block based
on their own policy.

## Why an injectable Resolver

The Python module accepts an optional `resolver` callable. Tests inject
a stub so they don't make real DNS queries. The Go port keeps the same
pattern:

```go
type Resolver func(host string) ([]string, error)
```

Pass `nil` to use `DefaultResolver` (which calls `net.LookupHost`). Pass
a custom `Resolver` to make tests deterministic.

## Layout

```
go-src/url_safety/
  go.mod                          # module github.com/odysseus/url_safety
  README.md
  cmd/urlsafety-demo/main.go      # --url <URL> [--block-private] [--resolver <IP>]
  pkg/urlsafety/
    types.go                      # package doc + Result struct
    schemes.go                    # AllowedSchemes + IsAllowedScheme + NormalizeScheme
    classifiers.go                # ClassifyIP + StripIPv6Zone
    validators.go                 # Resolver + DefaultResolver + Check
    idn.go                        # InspectIDN + IsPunycodeASCII + ParseHostLiteral
    urlsafety_test.go             # full coverage of the public surface
```

## Public API

```go
// One-shot check.
res := urlsafety.Check("https://example.com/", false, nil)
if !res.OK {
    return fmt.Errorf("outbound URL rejected: %s", res.Reason)
}

// Classify an IP directly (useful when the caller already has a literal).
reason := urlsafety.ClassifyIP(net.ParseIP("169.254.169.254"), false)
// reason != "" → rejected.

// IDN soft-signal (caller decides policy).
report := urlsafety.InspectIDN(host)
if report.MixedScripts { /* log / warn */ }
```

## Port notes

- **`Result` instead of `(ok, reason)` tuple.** The Python source returns a
  bare tuple; the Go port widens it to a struct so callers can also see
  the scheme, host, and resolved IPs. The Reason field carries the same
  human-readable message as the Python return value.
- **IPv4-mapped IPv6 unwrap.** Python's `ipaddress.IPv6Address.ipv4_mapped`
  returns the embedded v4 for `::ffff:0:0/96` literals. Go's `net.IP`
  makes the 16-byte slice parse as both v4 and v6; we unwrap to v4 when
  the slice length is `net.IPv6len` AND `To4()` succeeds. This matches
  the Python branch.
- **Zone ID stripping.** `net.ParseIP` rejects `fe80::1%eth0`. The
  Python source does `raw.split("%")[0]`; the Go port exposes the same
  step as `StripIPv6Zone` and uses it before classification.
- **Default resolver.** Python uses `socket.getaddrinfo(host, None)`,
  which returns A + AAAA records as `(family, ..., sockaddr)` tuples.
  Go's `net.LookupHost` returns the same records as a string slice.
- **No external dependencies.** Stdlib only: `net`, `net/url`,
  `strings`. No DNS library, no regex, no IDN decoder.

## Running tests

```bash
cd go-src/url_safety
go build ./...
go test ./...
```

Tests use a `fakeResolver` stub so they make zero DNS queries. The one
`DefaultResolver` test uses an `.invalid` TLD which is reserved by RFC
2606 and guaranteed not to resolve, so it stays offline-safe.

## Demo CLI

```bash
# Safe URL, public IP.
go run ./cmd/urlsafety-demo --url https://example.com

# SSRF target — link-local, must be rejected.
go run ./cmd/urlsafety-demo --url http://169.254.169.254/latest/meta-data/

# SSRF target — RFC1918, only rejected when --block-private is set.
go run ./cmd/urlsafety-demo --url http://10.0.0.5/ --block-private

# Use a custom resolver (returns only this IP, regardless of host).
go run ./cmd/urlsafety-demo --url http://anything/ --resolver 127.0.0.1 --block-private
```

Exit code is `0` on OK, `1` on rejection, `2` on bad arguments.