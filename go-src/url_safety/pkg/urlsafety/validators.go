package urlsafety

import (
	"fmt"
	"net"
	"net/url"
	"strings"
)

// Resolver is the injected hostname-to-IPs lookup. The Python source uses
// socket.getaddrinfo; the Go equivalent is net.LookupHost which returns
// both A and AAAA records. Tests substitute a stub Resolver to avoid real
// DNS lookups.
type Resolver func(host string) ([]string, error)

// DefaultResolver is the production resolver. It uses net.LookupHost
// (which returns the A + AAAA records the OS resolver provides) and is the
// equivalent of Python's socket.getaddrinfo(host, None).
func DefaultResolver(host string) ([]string, error) {
	ips, err := net.LookupHost(host)
	if err != nil {
		return nil, err
	}
	return ips, nil
}

// Result is the typed outcome of a Check call. It mirrors the Python
// tuple (ok, reason) but adds classification context — scheme, host,
// resolved IP — so logs and tests can assert what the validator saw.
type Result struct {
	// OK is true only when the URL is safe to fetch.
	OK bool

	// Reason is "ok" when OK is true; otherwise it is a short human-readable
	// explanation. Callers can pass this back to the user as a 400 body.
	Reason string

	// Scheme is the (lower-cased) scheme the validator observed. Empty when
	// the input had no scheme.
	Scheme string

	// Host is the (lower-cased) host the validator observed. Empty when the
	// input had no host.
	Host string

	// IPs is the resolved IP list (after StripIPv6Zone, before
	// classification). Useful for logging which A/AAAA records were
	// checked. Nil when the host did not resolve.
	IPs []string
}

// Check validates a user-supplied outbound URL.
//
// Behaviour mirrors src/url_safety.py:
//
//   - empty / non-string / whitespace-only input is rejected;
//   - the scheme must be http or https (case-insensitive);
//   - the host must be present;
//   - the host must resolve via the configured Resolver (or
//     DefaultResolver when nil);
//   - every resolved IP is classified — link-local is always rejected;
//     private/loopback is rejected only when blockPrivate is true.
//
// The resolver parameter is injectable so callers (and tests) can avoid
// real DNS. Pass nil to use DefaultResolver.
func Check(rawURL string, blockPrivate bool, resolver Resolver) Result {
	if rawURL == "" {
		return Result{OK: false, Reason: "URL is required"}
	}
	trimmed := strings.TrimSpace(rawURL)
	if trimmed == "" {
		return Result{OK: false, Reason: "URL is required"}
	}

	parsed, err := url.Parse(trimmed)
	if err != nil {
		return Result{
			OK:     false,
			Reason: fmt.Sprintf("unparseable URL: %v", err),
		}
	}

	scheme := NormalizeScheme(parsed.Scheme)
	if !IsAllowedScheme(scheme) {
		display := scheme
		if display == "" {
			display = "(none)"
		}
		return Result{
			OK:     false,
			Reason: fmt.Sprintf("scheme must be http or https, got '%s'", display),
			Scheme: scheme,
		}
	}

	host := parsed.Hostname()
	if host == "" {
		return Result{OK: false, Reason: "URL has no host", Scheme: scheme}
	}

	r := resolver
	if r == nil {
		r = DefaultResolver
	}
	rawIPs, err := r(host)
	if err != nil {
		return Result{
			OK:     false,
			Reason: fmt.Sprintf("host does not resolve: %v", err),
			Scheme: scheme,
			Host:   host,
		}
	}
	if len(rawIPs) == 0 {
		return Result{
			OK:     false,
			Reason: "host does not resolve",
			Scheme: scheme,
			Host:   host,
		}
	}

	resolved := make([]string, 0, len(rawIPs))
	for _, raw := range rawIPs {
		cleaned := StripIPv6Zone(raw)
		ip := net.ParseIP(cleaned)
		if ip == nil {
			// Skip unparseable records (shouldn't happen for a real
			// resolver, but defensive). The Python source uses
			// `continue` for the same case.
			continue
		}
		resolved = append(resolved, ip.String())
		if reason := ClassifyIP(ip, blockPrivate); reason != "" {
			return Result{
				OK:     false,
				Reason: reason,
				Scheme: scheme,
				Host:   host,
				IPs:    resolved,
			}
		}
	}

	return Result{
		OK:     true,
		Reason: "ok",
		Scheme: scheme,
		Host:   host,
		IPs:    resolved,
	}
}
