package urlsafety

import (
	"net"
	"strings"
	"testing"
)

// fakeResolver returns a Resolver that yields ips in order, regardless of
// host. It also records every host it was called with so tests can assert
// that the validator stopped at the first rejected IP.
type fakeResolver struct {
	ips   []string
	calls []string
}

func (f *fakeResolver) resolve(host string) ([]string, error) {
	f.calls = append(f.calls, host)
	return f.ips, nil
}

// errResolver always returns the supplied error. Used to exercise the
// "host does not resolve" branch.
type errResolver struct{ err error }

func (e errResolver) resolve(host string) ([]string, error) {
	_ = host
	return nil, e.err
}

// TestCheckSchemeWhitelist pins the happy path: http and https both pass
// the scheme check (assuming the resolver returns a public IP).
func TestCheckSchemeWhitelist(t *testing.T) {
	r := &fakeResolver{ips: []string{"93.184.216.34"}}
	cases := []struct {
		rawURL string
		scheme string
	}{
		{"http://example.com", "http"},
		{"https://example.com", "https"},
		{"HTTPS://Example.COM", "https"}, // case-insensitive
	}
	for _, tc := range cases {
		t.Run(tc.rawURL, func(t *testing.T) {
			res := Check(tc.rawURL, false, r.resolve)
			if !res.OK {
				t.Fatalf("expected OK for %s, got reason=%q", tc.rawURL, res.Reason)
			}
			if res.Scheme != tc.scheme {
				t.Errorf("scheme=%q, want %q", res.Scheme, tc.scheme)
			}
		})
	}
}

// TestCheckRejectsNonHTTPSchemes covers file://, javascript:, data:,
// vbscript:, gopher://, ftp://, and a couple of obscure-but-real
// vectors. None of these should ever reach an outbound request.
func TestCheckRejectsNonHTTPSchemes(t *testing.T) {
	cases := []string{
		"file:///etc/passwd",
		"javascript:alert(1)",
		"data:text/html,<script>alert(1)</script>",
		"vbscript:msgbox(1)",
		"gopher://example.com/_test",
		"ftp://example.com/secret",
		"FILE:///etc/passwd", // case-insensitive
	}
	r := &fakeResolver{ips: []string{"1.2.3.4"}}
	for _, raw := range cases {
		t.Run(raw, func(t *testing.T) {
			res := Check(raw, false, r.resolve)
			if res.OK {
				t.Fatalf("expected rejection for %s, got OK", raw)
			}
			if !strings.Contains(res.Reason, "scheme must be http or https") {
				t.Errorf("expected scheme rejection reason, got %q", res.Reason)
			}
		})
	}
}

// TestCheckRejectsLinkLocal covers the cloud instance-metadata SSRF
// vector — 169.254.0.0/16 (IPv4) and fe80::/10 (IPv6). This must always
// reject, even when BlockPrivate is false.
func TestCheckRejectsLinkLocal(t *testing.T) {
	cases := []struct {
		rawURL string
		ips    []string
	}{
		{"http://169.254.169.254/latest/meta-data/", []string{"169.254.169.254"}},
		{"http://169.254.0.5/", []string{"169.254.0.5"}},
		{"http://[fe80::1]/", []string{"fe80::1"}},
		{"http://[fe80::abcd:ef01]/", []string{"fe80::abcd:ef01"}},
	}
	for _, tc := range cases {
		t.Run(tc.rawURL, func(t *testing.T) {
			r := &fakeResolver{ips: tc.ips}
			res := Check(tc.rawURL, false, r.resolve)
			if res.OK {
				t.Fatalf("expected rejection for %s, got OK", tc.rawURL)
			}
			if !strings.Contains(res.Reason, "link-local") {
				t.Errorf("expected link-local rejection, got %q", res.Reason)
			}
		})
	}
}

// TestCheckBlockPrivateRejectsLoopback verifies that BlockPrivate=true
// also catches loopback (127.0.0.0/8, ::1). Without BlockPrivate, the
// same URLs would pass — local-first embedding endpoints are normal.
func TestCheckBlockPrivateRejectsLoopback(t *testing.T) {
	r := &fakeResolver{ips: []string{"127.0.0.1"}}
	res := Check("http://localhost/", false, r.resolve)
	if !res.OK {
		t.Fatalf("expected loopback allowed with BlockPrivate=false, got %q", res.Reason)
	}

	res = Check("http://localhost/", true, r.resolve)
	if res.OK {
		t.Fatal("expected loopback rejected with BlockPrivate=true")
	}
	if !strings.Contains(res.Reason, "private/loopback") {
		t.Errorf("expected private/loopback rejection, got %q", res.Reason)
	}

	// IPv6 loopback.
	r6 := &fakeResolver{ips: []string{"::1"}}
	res = Check("http://[::1]/", false, r6.resolve)
	if !res.OK {
		t.Fatalf("expected ::1 allowed with BlockPrivate=false, got %q", res.Reason)
	}
	res = Check("http://[::1]/", true, r6.resolve)
	if res.OK {
		t.Fatal("expected ::1 rejected with BlockPrivate=true")
	}
}

// TestCheckBlockPrivateRejectsRFC1918 covers 10/8, 172.16/12, 192.168/16
// in both IPv4 and their IPv6 counterparts.
func TestCheckBlockPrivateRejectsRFC1918(t *testing.T) {
	cases := []struct {
		host string
		ips  []string
	}{
		{"http://10.0.0.5/", []string{"10.0.0.5"}},
		{"http://172.16.0.1/", []string{"172.16.0.1"}},
		{"http://172.31.255.254/", []string{"172.31.255.254"}},
		{"http://192.168.1.1/", []string{"192.168.1.1"}},
		{"http://[fc00::1]/", []string{"fc00::1"}},
		{"http://[fd12:3456:789a::1]/", []string{"fd12:3456:789a::1"}},
	}
	for _, tc := range cases {
		t.Run(tc.host, func(t *testing.T) {
			// Allowed when BlockPrivate=false.
			r := &fakeResolver{ips: tc.ips}
			if res := Check(tc.host, false, r.resolve); !res.OK {
				t.Errorf("expected %s allowed with BlockPrivate=false, got %q", tc.host, res.Reason)
			}
			// Rejected when BlockPrivate=true.
			if res := Check(tc.host, true, r.resolve); res.OK {
				t.Errorf("expected %s rejected with BlockPrivate=true", tc.host)
			}
		})
	}
}

// TestCheckRejectsIPv4MappedLinkLocal exercises the IPv4-mapped-IPv6
// unwrap branch. ::ffff:169.254.169.254 is a 16-byte IP that parses as
// v4-mapped v6; it must be judged as the embedded v4 and rejected as
// link-local.
func TestCheckRejectsIPv4MappedLinkLocal(t *testing.T) {
	r := &fakeResolver{ips: []string{"::ffff:169.254.169.254"}}
	res := Check("http://example.com/", false, r.resolve)
	if res.OK {
		t.Fatal("expected IPv4-mapped link-local to be rejected")
	}
	if !strings.Contains(res.Reason, "link-local") {
		t.Errorf("expected link-local rejection, got %q", res.Reason)
	}
}

// TestCheckRejectsMulticastReservedUnspecified covers the "always
// rejected regardless of BlockPrivate" tier: multicast (224.0.0.0/4,
// ff00::/8), reserved (240.0.0.0/4), and unspecified (0.0.0.0, ::).
func TestCheckRejectsMulticastReservedUnspecified(t *testing.T) {
	cases := []struct {
		host string
		ips  []string
		tag  string
	}{
		{"http://224.0.0.1/", []string{"224.0.0.1"}, "multicast"},
		{"http://[ff02::1]/", []string{"ff02::1"}, "multicast-v6"},
		{"http://240.1.2.3/", []string{"240.1.2.3"}, "reserved"},
		{"http://0.0.0.0/", []string{"0.0.0.0"}, "unspecified-v4"},
		{"http://[::]/", []string{"::"}, "unspecified-v6"},
	}
	for _, tc := range cases {
		t.Run(tc.tag, func(t *testing.T) {
			r := &fakeResolver{ips: tc.ips}
			res := Check(tc.host, false, r.resolve)
			if res.OK {
				t.Fatalf("expected %s rejected (%s), got OK", tc.host, tc.tag)
			}
			if !strings.Contains(res.Reason, "disallowed address") {
				t.Errorf("expected disallowed-address reason, got %q", res.Reason)
			}
		})
	}
}

// TestCheckRejectsAnyIPWhenMultiple verifies that if any one of the
// resolved IPs is dangerous, the URL is rejected. This is the classic
// DNS-rebinding mitigation: a hostname may resolve to multiple A/AAAA
// records, only one of which needs to be a private IP for the SSRF to
// succeed.
func TestCheckRejectsAnyIPWhenMultiple(t *testing.T) {
	// Two IPs: one public, one link-local. We expect rejection on the
	// link-local regardless of resolution order.
	r := &fakeResolver{ips: []string{"93.184.216.34", "169.254.169.254"}}
	res := Check("http://example.com/", false, r.resolve)
	if res.OK {
		t.Fatal("expected rejection when one resolved IP is link-local")
	}
	if !strings.Contains(res.Reason, "link-local") {
		t.Errorf("expected link-local reason, got %q", res.Reason)
	}
}

// TestCheckRejectsEmptyAndWhitespace verifies that empty / whitespace
// URLs are rejected with a clear reason.
func TestCheckRejectsEmptyAndWhitespace(t *testing.T) {
	for _, raw := range []string{"", "   ", "\t\n"} {
		t.Run("raw="+raw, func(t *testing.T) {
			res := Check(raw, false, nil)
			if res.OK {
				t.Fatalf("expected rejection for %q, got OK", raw)
			}
			if !strings.Contains(res.Reason, "URL is required") {
				t.Errorf("expected 'URL is required' reason, got %q", res.Reason)
			}
		})
	}
}

// TestCheckRejectsMissingHost covers the "scheme but no host" case
// (e.g. "http:///path" or "https:" alone).
func TestCheckRejectsMissingHost(t *testing.T) {
	cases := []string{
		"http:///path",
		"https:",
	}
	for _, raw := range cases {
		t.Run(raw, func(t *testing.T) {
			res := Check(raw, false, nil)
			if res.OK {
				t.Fatalf("expected rejection for %q, got OK", raw)
			}
			if !strings.Contains(res.Reason, "no host") {
				t.Errorf("expected 'no host' reason, got %q", res.Reason)
			}
		})
	}
}

// TestCheckRejectsUnresolvableHost covers the resolver-error path.
func TestCheckRejectsUnresolvableHost(t *testing.T) {
	r := errResolver{err: &net.DNSError{Err: "no such host", Name: "nx.example"}}
	res := Check("http://nx.example/", false, r.resolve)
	if res.OK {
		t.Fatal("expected rejection when resolver fails")
	}
	if !strings.Contains(res.Reason, "host does not resolve") {
		t.Errorf("expected 'host does not resolve' reason, got %q", res.Reason)
	}
}

// TestCheckRejectsEmptyResolverResult covers the "resolver returned no
// IPs" edge case. Real resolvers should never return success with zero
// records, but defensively we treat it as a failure.
func TestCheckRejectsEmptyResolverResult(t *testing.T) {
	r := &fakeResolver{ips: nil}
	res := Check("http://empty.example/", false, r.resolve)
	if res.OK {
		t.Fatal("expected rejection when resolver returns no IPs")
	}
	if !strings.Contains(res.Reason, "host does not resolve") {
		t.Errorf("expected 'host does not resolve' reason, got %q", res.Reason)
	}
}

// TestCheckPreservesPortAndPath verifies the validator doesn't get
// confused by port + path + query + fragment.
func TestCheckPreservesPortAndPath(t *testing.T) {
	r := &fakeResolver{ips: []string{"93.184.216.34"}}
	raw := "https://example.com:8443/api/v1/embeddings?model=foo&token=abc#section"
	res := Check(raw, false, r.resolve)
	if !res.OK {
		t.Fatalf("expected OK for URL with port/path/query/fragment, got %q", res.Reason)
	}
	if res.Host != "example.com" {
		t.Errorf("host=%q, want example.com", res.Host)
	}
	if res.Scheme != "https" {
		t.Errorf("scheme=%q, want https", res.Scheme)
	}
	if len(res.IPs) != 1 || res.IPs[0] != "93.184.216.34" {
		t.Errorf("IPs=%v, want [93.184.216.34]", res.IPs)
	}
}

// TestCheckStripsIPv6Zone ensures zone IDs in resolved IPs are stripped
// before classification. The Python source does `raw.split("%")[0]` for
// the same reason.
func TestCheckStripsIPv6Zone(t *testing.T) {
	r := &fakeResolver{ips: []string{"fe80::1%eth0"}}
	res := Check("http://example/", false, r.resolve)
	if res.OK {
		t.Fatal("expected rejection for link-local v6 with zone id")
	}
	if !strings.Contains(res.Reason, "link-local") {
		t.Errorf("expected link-local rejection, got %q", res.Reason)
	}
	// The reported IP must be the cleaned form (no zone id).
	if len(res.IPs) != 1 || res.IPs[0] != "fe80::1" {
		t.Errorf("IPs=%v, want [fe80::1]", res.IPs)
	}
}

// TestClassifyIPDirect covers the classifier function in isolation. This
// lets us pin the exact behaviour for each IP class without going through
// the URL parsing / resolver path.
func TestClassifyIPDirect(t *testing.T) {
	cases := []struct {
		ip          string
		blockPriv   bool
		wantAllowed bool
	}{
		// Public IPv4 — always allowed.
		{"93.184.216.34", false, true},
		{"93.184.216.34", true, true},

		// Link-local — always rejected.
		{"169.254.169.254", false, false},
		{"169.254.169.254", true, false},
		{"fe80::1", false, false},
		{"fe80::1", true, false},

		// Loopback — rejected only when blockPriv.
		{"127.0.0.1", false, true},
		{"127.0.0.1", true, false},
		{"::1", false, true},
		{"::1", true, false},

		// RFC1918 — rejected only when blockPriv.
		{"10.0.0.1", false, true},
		{"10.0.0.1", true, false},
		{"192.168.1.1", false, true},
		{"192.168.1.1", true, false},
		{"172.16.0.1", false, true},
		{"172.16.0.1", true, false},
		{"172.31.255.254", false, true},
		{"172.31.255.254", true, false},

		// Multicast / reserved / unspecified — always rejected.
		{"224.0.0.1", false, false},
		{"224.0.0.1", true, false},
		{"0.0.0.0", false, false},
		{"::", false, false},

		// IPv4-mapped IPv6.
		{"::ffff:169.254.169.254", false, false},
		{"::ffff:10.0.0.1", false, true},
		{"::ffff:10.0.0.1", true, false},
	}
	for _, tc := range cases {
		ip := net.ParseIP(tc.ip)
		if ip == nil {
			t.Errorf("test bug: cannot parse %q", tc.ip)
			continue
		}
		got := ClassifyIP(ip, tc.blockPriv)
		allowed := got == ""
		if allowed != tc.wantAllowed {
			t.Errorf("ClassifyIP(%s, blockPriv=%t) allowed=%t (reason=%q), want %t",
				tc.ip, tc.blockPriv, allowed, got, tc.wantAllowed)
		}
	}
}

// TestIsAllowedScheme pins the helper-level check.
func TestIsAllowedScheme(t *testing.T) {
	if !IsAllowedScheme("http") {
		t.Error("http should be allowed")
	}
	if !IsAllowedScheme("HTTPS") {
		t.Error("HTTPS (case-insensitive) should be allowed")
	}
	if IsAllowedScheme("file") {
		t.Error("file should not be allowed")
	}
	if IsAllowedScheme("javascript") {
		t.Error("javascript should not be allowed")
	}
	if IsAllowedScheme("") {
		t.Error("empty scheme should not be allowed")
	}
}

// TestStripIPv6Zone pins the zone-strip helper.
func TestStripIPv6Zone(t *testing.T) {
	cases := []struct{ in, want string }{
		{"fe80::1", "fe80::1"},
		{"fe80::1%eth0", "fe80::1"},
		{"fe80::1%25eth0", "fe80::1"},
		{"93.184.216.34", "93.184.216.34"},
		{"", ""},
	}
	for _, tc := range cases {
		if got := StripIPv6Zone(tc.in); got != tc.want {
			t.Errorf("StripIPv6Zone(%q)=%q, want %q", tc.in, got, tc.want)
		}
	}
}

// TestInspectIDNDetectsPunycode confirms the IDN inspector flags
// punycode-encoded labels.
func TestInspectIDNDetectsPunycode(t *testing.T) {
	r := InspectIDN("xn--80akhbyknj4f.example")
	if !r.HasPunycode {
		t.Error("expected HasPunycode=true for xn-- prefix")
	}
	if r.MixedScripts {
		t.Error("pure punycode label has no scripts to mix")
	}
}

// TestInspectIDNDetectsMixedScripts confirms the homograph-attack
// signal: Latin + Cyrillic in the same host.
func TestInspectIDNDetectsMixedScripts(t *testing.T) {
	// "paypaӏ" — Latin "paypa" + Cyrillic "ӏ" (palochka). Trivial
	// homograph example; the inspector only needs to flag the script
	// mix, not validate the label.
	r := InspectIDN("paypaӏ.com")
	if !r.HasNonASCII {
		t.Error("expected HasNonASCII=true for Cyrillic")
	}
	if !r.MixedScripts {
		t.Error("expected MixedScripts=true for Latin + Cyrillic")
	}
}

// TestInspectIDNPureASCII confirms a plain ASCII host has no signals.
func TestInspectIDNPureASCII(t *testing.T) {
	r := InspectIDN("example.com")
	if r.HasNonASCII {
		t.Error("expected HasNonASCII=false for pure ASCII")
	}
	if r.HasPunycode {
		t.Error("expected HasPunycode=false for plain ASCII")
	}
	if r.MixedScripts {
		t.Error("expected MixedScripts=false for pure ASCII")
	}
}

// TestIsPunycodeASCII confirms the prefix helper.
func TestIsPunycodeASCII(t *testing.T) {
	if !IsPunycodeASCII("xn--80akhbyknj4f") {
		t.Error("expected true for xn-- prefix")
	}
	if IsPunycodeASCII("example") {
		t.Error("expected false for plain label")
	}
	if !IsPunycodeASCII("XN--80AKHBYKNJ4F") {
		t.Error("expected case-insensitive match")
	}
}

// TestDefaultResolverIsInjectable confirms that a nil resolver falls back
// to DefaultResolver (so callers don't have to thread one through for
// the "I just want to validate the shape" case). The actual DNS call
// will fail in offline test environments, so we use a syntactically
// valid but non-existent host and assert on the error path.
func TestDefaultResolverIsInjectable(t *testing.T) {
	res := Check("http://this-host-should-not-exist.invalid./", false, nil)
	if res.OK {
		t.Fatal("expected rejection for unresolvable host")
	}
	if !strings.Contains(res.Reason, "host does not resolve") {
		t.Errorf("expected DNS error, got %q", res.Reason)
	}
}
