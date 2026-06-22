package urlsafety

import (
	"net"
	"strings"
)

// IDNReport describes whether a hostname contains non-ASCII characters
// that could indicate a punycode / IDN homograph attack. Odysseus does
// not block these by default (Check is the SSRF guard), but downstream
// callers may want to log or warn on them. This helper is here so the
// port can answer "does this hostname look like an IDN attack vector"
// without re-implementing the regex in two places.
type IDNReport struct {
	// HasNonASCII is true when the hostname contains any rune > 0x7F.
	HasNonASCII bool

	// HasPunycode is true when the host contains the "xn--" ACE prefix,
	// which is how IDN labels are encoded for DNS.
	HasPunycode bool

	// MixedScripts is true when the host contains characters from more
	// than one script (e.g. Latin mixed with Cyrillic). This is the
	// classic homograph-attack indicator.
	MixedScripts bool
}

// InspectIDN returns an IDNReport for host. It is intentionally cheap —
// no DNS, no allocation-heavy library. Use it as a soft signal, not as
// a hard allow/deny.
func InspectIDN(host string) IDNReport {
	r := IDNReport{}
	r.HasPunycode = strings.Contains(strings.ToLower(host), "xn--")

	var (
		sawNonASCII bool
		hasLatin    bool
		hasCyrillic bool
		hasGreek    bool
		hasOther    bool
	)
	for _, r := range host {
		switch {
		case r >= 0x80:
			sawNonASCII = true
			switch {
			case r >= 0x0400 && r <= 0x04FF: // Cyrillic
				hasCyrillic = true
			case r >= 0x0370 && r <= 0x03FF: // Greek
				hasGreek = true
			case r >= 0x0020 && r <= 0x007F: // ASCII
				hasLatin = true
			default:
				hasOther = true
			}
		case (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z'):
			hasLatin = true
		}
	}
	r.HasNonASCII = sawNonASCII

	// Mixed = at least two distinct scripts present. This is a coarse
	// heuristic — it will also fire on a perfectly innocent domain like
	// "пример.com" (Cyrillic only), but for the homograph-attack use
	// case we only care about *mixed* scripts.
	distinct := 0
	if hasLatin {
		distinct++
	}
	if hasCyrillic {
		distinct++
	}
	if hasGreek {
		distinct++
	}
	if hasOther {
		distinct++
	}
	r.MixedScripts = distinct >= 2

	return r
}

// IsPunycodeASCII reports whether s is the ASCII-compatible encoding of
// an IDN label (starts with "xn--"). The full IDN pipeline should
// resolve the punycode to Unicode before deciding safety; this helper is
// a fast-path signal only.
func IsPunycodeASCII(s string) bool {
	return strings.HasPrefix(strings.ToLower(s), "xn--")
}

// ParseHostLiteral parses a bare IP literal (with optional IPv6 zone)
// into a net.IP, returning nil when the input is not a literal. The
// caller must have already split host:port via url.URL.Hostname.
func ParseHostLiteral(host string) net.IP {
	return net.ParseIP(StripIPv6Zone(host))
}
