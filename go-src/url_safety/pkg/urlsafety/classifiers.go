package urlsafety

import (
	"net"
	"strings"
)

// Pre-built IPNet descriptors used by ClassifyIP. We pre-build them at
// package init so the hot path doesn't re-parse the CIDR strings on
// every check. The set matches what Python's ipaddress module considers
// "link-local", "multicast", "reserved", "unspecified", "private", and
// "loopback".
var (
	// ipv4LinkLocal is 169.254.0.0/16.
	ipv4LinkLocal = mustCIDR("169.254.0.0/16")

	// ipv6LinkLocal is fe80::/10. This is the IPv6 link-local prefix;
	// covers fe80::/10 exactly as Python's IPv6Address.is_link_local.
	ipv6LinkLocal = mustCIDR("fe80::/10")

	// ipv4Multicast is 224.0.0.0/4.
	ipv4Multicast = mustCIDR("224.0.0.0/4")

	// ipv6Multicast is ff00::/8.
	ipv6Multicast = mustCIDR("ff00::/8")

	// ipv4Reserved is 240.0.0.0/4. The future-use range.
	ipv4Reserved = mustCIDR("240.0.0.0/4")

	// ipv4Unspecified is 0.0.0.0/32 (matches Python's IPv4Address.is_unspecified).
	ipv4Unspecified = mustCIDR("0.0.0.0/32")

	// ipv6Unspecified is ::/128.
	ipv6Unspecified = mustCIDR("::/128")

	// ipv4PrivateAll is a covering CIDR for the RFC1918 + loopback
	// ranges. We don't call net.IP.IsPrivate() because the Go stdlib
	// returns different answers from Python in some edge cases (notably
	// 0.0.0.0/8 — Go treats parts of it as private, Python doesn't). We
	// pin the exact set the Python module blocks.
	ipv4Private = []net.IPNet{
		mustCIDR("10.0.0.0/8"),
		mustCIDR("172.16.0.0/12"),
		mustCIDR("192.168.0.0/16"),
	}
	ipv4Loopback = mustCIDR("127.0.0.0/8")

	// ipv6UniqueLocal is fc00::/7 — RFC4193. Python's IPv6Address.is_private
	// returns true here.
	ipv6UniqueLocal = []net.IPNet{mustCIDR("fc00::/7")}

	// ipv6Loopback is ::1/128. Python's IPv6Address.is_loopback returns
	// true here.
	ipv6Loopback = mustCIDR("::1/128")
)

// mustCIDR is a tiny helper that panics if s is not a valid CIDR. It is
// only called from package-level var initialisers so a malformed CIDR
// would be a build-time bug, not a runtime hazard.
func mustCIDR(s string) net.IPNet {
	_, n, err := net.ParseCIDR(s)
	if err != nil {
		panic("urlsafety: bad CIDR in package init: " + s + ": " + err.Error())
	}
	return *n
}

// ClassifyIP returns a non-empty rejection reason if ip is not safe to
// reach from a server context, or "" if it is allowed.
//
// The order of checks matters:
//
//  1. IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254) is unwrapped to the
//     embedded IPv4. Without this, an attacker who controls an AAAA record
//     could wrap a link-local v4 in an IPv6 literal to bypass the
//     link-local check.
//  2. Link-local (169.254.0.0/16, fe80::/10) is always rejected. This is
//     the cloud instance-metadata SSRF credential-exfil vector — nobody
//     serves user traffic there.
//  3. Multicast, reserved, and unspecified addresses are always rejected.
//  4. If blockPrivate is true, private (10/8, 172.16/12, 192.168/16,
//     fc00::/7) and loopback (127.0.0.0/8, ::1) are also rejected.
//
// The function returns "" when the IP is allowed — callers should not
// treat "" as an error.
//
// The IP must be normalised: zone IDs should be stripped first (see
// StripIPv6Zone). We do the IPv4-mapped-IPv6 unwrap here so callers
// don't have to do it themselves.
func ClassifyIP(ip net.IP, blockPrivate bool) string {
	// Step 1: unwrap IPv4-mapped IPv6. net.IP may be a 16-byte slice
	// that also parses as an IPv4 (the ::ffff:0:0/96 prefix). Re-judge
	// the embedded v4 so the link-local / private checks see the right
	// range.
	if v4 := ip.To4(); v4 != nil && len(ip) == net.IPv6len {
		ip = v4
	}

	// Step 2: link-local — always rejected.
	if ip4 := ip.To4(); ip4 != nil {
		if ipv4LinkLocal.Contains(ip4) {
			return "link-local address blocked (SSRF metadata risk): " + ip.String()
		}
	} else if ipv6LinkLocal.Contains(ip) {
		return "link-local address blocked (SSRF metadata risk): " + ip.String()
	}

	// Step 3: multicast, reserved, unspecified — always rejected.
	switch {
	case containsNet(ip, ipv4Multicast, ipv6Multicast):
		return "disallowed address (multicast): " + ip.String()
	case containsNet(ip, ipv4Reserved):
		return "disallowed address (reserved): " + ip.String()
	case containsNet(ip, ipv4Unspecified, ipv6Unspecified):
		return "disallowed address (unspecified): " + ip.String()
	}

	// Step 4: private/loopback — only when blockPrivate is set.
	if blockPrivate {
		if ip4 := ip.To4(); ip4 != nil {
			if containsNet(ip4, ipv4Private...) {
				return "private/loopback address blocked: " + ip.String()
			}
			if ipv4Loopback.Contains(ip4) {
				return "private/loopback address blocked: " + ip.String()
			}
		} else {
			if containsNet(ip, ipv6UniqueLocal...) {
				return "private/loopback address blocked: " + ip.String()
			}
			if ipv6Loopback.Contains(ip) {
				return "private/loopback address blocked: " + ip.String()
			}
		}
	}

	return ""
}

// containsNet reports whether ip is in any of the supplied CIDRs. The
// helper exists because each IP family has a different set, and a
// switch-statement would explode combinatorially.
func containsNet(ip net.IP, nets ...net.IPNet) bool {
	for i := range nets {
		if nets[i].Contains(ip) {
			return true
		}
	}
	return false
}

// StripIPv6Zone strips the trailing "%zone" from a literal IPv6 string
// (e.g. "fe80::1%eth0" -> "fe80::1"). net.ParseIP does not accept zone IDs,
// so callers must remove them first. The original Python code uses
// `raw.split("%")[0]` for the same reason.
func StripIPv6Zone(s string) string {
	if i := strings.Index(s, "%"); i >= 0 {
		return s[:i]
	}
	return s
}
