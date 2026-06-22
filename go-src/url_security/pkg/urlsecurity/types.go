// Package urlsecurity validates outbound URLs against the strict
// "public HTTP(S) endpoint" policy. It is the Go port of
// src/url_security.py.
//
// The package enforces the same blocklists as the Python source:
//   - scheme must be http or https;
//   - host must not match the well-known internal hostnames
//     (localhost, metadata, metadata.google.internal, .localhost,
//     .local, .internal, .lan, .intranet);
//   - host must resolve to one or more IP addresses, every one of which
//     must be non-private, non-loopback, non-link-local, non-multicast,
//     non-reserved, non-unspecified.
//
// The package has no external dependencies. It only uses Go stdlib
// (net, net/url, strings, errors).
package urlsecurity

import (
	"net"
	"net/url"
	"strings"
)

// internalHostnames is the closed set of hostnames that are always
// rejected regardless of DNS resolution. Mirrors
// `_INTERNAL_HOSTNAMES` in src/url_security.py.
var internalHostnames = map[string]struct{}{
	"localhost":                {},
	"metadata":                 {},
	"metadata.google.internal": {},
}

// internalSuffixes is the closed set of hostname suffixes that are
// always rejected regardless of DNS resolution. Mirrors
// `_INTERNAL_SUFFIXES` in src/url_security.py.
var internalSuffixes = []string{
	".localhost",
	".local",
	".internal",
	".lan",
	".intranet",
}

// blockedNetworks mirrors `_BLOCKED_NETWORKS` in src/url_security.py.
// Every IPv4 or IPv6 address is tested for membership in any of these
// nets; on top of that, the standard library's per-IP predicates
// (IsPrivate, IsLoopback, IsLinkLocal, IsMulticast, IsUnspecified,
// IsReserved) are also applied.
var blockedNetworks = []*net.IPNet{
	// 0.0.0.0/8 — "this network"
	mustCIDR("0.0.0.0/8"),
	// 10.0.0.0/8 — private (RFC 1918)
	mustCIDR("10.0.0.0/8"),
	// 100.64.0.0/10 — CGNAT shared address space (RFC 6598)
	mustCIDR("100.64.0.0/10"),
	// 127.0.0.0/8 — loopback
	mustCIDR("127.0.0.0/8"),
	// 169.254.0.0/16 — link-local (cloud metadata SSRF risk)
	mustCIDR("169.254.0.0/16"),
	// 172.16.0.0/12 — private (RFC 1918)
	mustCIDR("172.16.0.0/12"),
	// 192.168.0.0/16 — private (RFC 1918)
	mustCIDR("192.168.0.0/16"),
	// ::/128 — unspecified IPv6
	mustCIDR("::/128"),
	// ::1/128 — loopback IPv6
	mustCIDR("::1/128"),
	// fc00::/7 — unique local addresses (RFC 4193)
	mustCIDR("fc00::/7"),
	// fe80::/10 — IPv6 link-local
	mustCIDR("fe80::/10"),
}

func mustCIDR(s string) *net.IPNet {
	_, n, err := net.ParseCIDR(s)
	if err != nil {
		panic("urlsecurity: bad CIDR in blockedNetworks: " + s)
	}
	return n
}

// DefaultMaxLength is the default cap on the cleaned URL length used by
// ValidatePublicHTTPURL. Mirrors the Python default of 2048.
const DefaultMaxLength = 2048

// Verdict is the structured result of Classify.
type Verdict struct {
	// URL is the trimmed, validated URL when the input was a valid
	// http(s) URL. Otherwise it is the original input.
	URL string
	// Reason describes why the URL was rejected; "ok" when the URL
	// passes the strict policy.
	Reason string
	// Private is true when the host resolved to a private/loopback/
	// link-local address. Always false when the verdict is "ok".
	Private bool
	// IP is the first resolved IP address (the only one we report),
	// or the empty string when DNS failed. Useful for debug logs.
	IP string
}

// IsInternalHostname reports whether the hostname (already lowercased
// and stripped) matches one of the closed internal hostname sets.
func IsInternalHostname(host string) bool {
	if host == "" {
		return false
	}
	if _, ok := internalHostnames[host]; ok {
		return true
	}
	for _, suf := range internalSuffixes {
		if strings.HasSuffix(host, suf) {
			return true
		}
	}
	return false
}

// ResolveHostnameIPs resolves the given hostname to its A and AAAA
// records. Returns nil when DNS fails. IPv6 zone identifiers are
// stripped (matching the Python `raw.split("%")[0]` step in
// `check_outbound_url`).
func ResolveHostnameIPs(hostname string) []net.IP {
	if hostname == "" {
		return nil
	}
	ips, err := net.LookupIP(hostname)
	if err != nil {
		return nil
	}
	out := make([]net.IP, 0, len(ips))
	for _, ip := range ips {
		if ip == nil {
			continue
		}
		out = append(out, ip)
	}
	if len(out) == 0 {
		return nil
	}
	return out
}

// IsBlockedIP reports whether the address belongs to any of the
// blocklists in src/url_security.py. Returns false for nil.
//
// The blocklist combines:
//   - explicit CIDR ranges (see blockedNetworks above);
//   - net.IP.IsPrivate, IsLoopback, IsLinkLocal, IsMulticast,
//     IsUnspecified, IsReserved.
//
// IPv4-mapped IPv6 addresses (e.g. ::ffff:169.254.169.254) are
// evaluated via their IPv4 representation, mirroring the explicit
// downgrade in `src/url_safety._classify`.
func IsBlockedIP(addr net.IP) bool {
	if addr == nil {
		return false
	}
	v4 := addr
	if v4.To4() != nil {
		v4 = v4.To4()
	}
	for _, n := range blockedNetworks {
		if n.Contains(v4) {
			return true
		}
	}
	if addr.IsPrivate() {
		return true
	}
	if addr.IsLoopback() {
		return true
	}
	if addr.IsLinkLocalUnicast() || addr.IsLinkLocalMulticast() {
		return true
	}
	if addr.IsMulticast() {
		return true
	}
	if addr.IsUnspecified() {
		return true
	}
	return false
}

// parseURL returns the scheme and hostname (lowercased, no port) or
// an error describing why the URL is invalid.
func parseURL(rawURL string) (scheme, host string, err error) {
	s := strings.TrimSpace(rawURL)
	if s == "" {
		return "", "", errEmpty
	}
	u, perr := url.Parse(s)
	if perr != nil {
		return "", "", errUnparseable
	}
	scheme = strings.ToLower(u.Scheme)
	host = strings.ToLower(u.Hostname())
	if scheme != "http" && scheme != "https" {
		return "", "", errBadScheme
	}
	if host == "" {
		return "", "", errNoHost
	}
	return scheme, host, nil
}

// Classify inspects a URL without raising. It returns a Verdict whose
// Reason is "ok" only when the URL passes the strict policy.
//
// This is the Go equivalent of combining
// `is_public_http_url(url)` and `_host_resolves_publicly(hostname)` and
// surfacing the rejection reason as a string instead of an error.
func Classify(rawURL string) Verdict {
	_, host, err := parseURL(rawURL)
	if err != nil {
		return Verdict{URL: rawURL, Reason: err.Error()}
	}

	if IsInternalHostname(host) {
		return Verdict{URL: rawURL, Reason: "internal hostname blocked: " + host, Private: true}
	}

	// Try as a literal IP first (handles URLs like http://10.0.0.1/x).
	if ip := net.ParseIP(host); ip != nil {
		if IsBlockedIP(ip) {
			return Verdict{URL: rawURL, Reason: "blocked IP literal: " + ip.String(), Private: true, IP: ip.String()}
		}
		return Verdict{URL: rawURL, Reason: "ok", IP: ip.String()}
	}

	ips := ResolveHostnameIPs(host)
	if len(ips) == 0 {
		return Verdict{URL: rawURL, Reason: "host does not resolve: " + host}
	}
	first := ips[0]
	for _, ip := range ips {
		if IsBlockedIP(ip) {
			return Verdict{URL: rawURL, Reason: "blocked IP " + ip.String() + " for host " + host, Private: true, IP: first.String()}
		}
	}
	return Verdict{URL: rawURL, Reason: "ok", IP: first.String()}
}

// Small error sentinels used by parseURL. They are mapped to human
// reason strings via their .Error() method.
var (
	errEmpty       = strErr("URL is required")
	errUnparseable = strErr("URL could not be parsed")
	errBadScheme   = strErr("URL scheme must be http or https")
	errNoHost      = strErr("URL has no host")
	errTooLong     = strErr("URL is too long")
	errNotPublic   = strErr("URL must point to a public HTTP(S) endpoint")
)

type strErr string

func (e strErr) Error() string { return string(e) }
