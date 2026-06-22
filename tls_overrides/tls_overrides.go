// Package tls_overrides provides an extended TLS trust store for LLM
// providers that serve their API over certificates signed by a private
// root CA which is not part of the standard system bundle.
//
// The Go port of src/tls_overrides.py. See that file for the long-form
// rationale; in short:
//
//   - GigaChat (Sber) uses the Russian Trusted Root CA, not bundled with
//     OpenSSL / certifi / system trust on most non-Russian installs. The
//     chain looks self-signed to a stock Go runtime and the endpoint is
//     unreachable. (See issue #722.)
//   - On-premise enterprise LLM gateways often present a corporate CA
//     that has not been imported into the runtime's trust store.
//
// Operators point LLM_CA_BUNDLE at a PEM file containing the extra CA
// cert(s). The default system trust store is loaded first, then the
// operator's PEM is layered on top, so verification still happens —
// the trust set just gets larger. There is deliberately no
// "verify=off" knob: weakening verification globally (or per-host)
// would expose those endpoints to MITM, and the operator-supplied
// bundle is the correct fix for legitimate private-CA providers.
//
// Scope:
//
//	LLMVerify() is intentionally consumed only by the LLM-provider HTTP
//	client. It is NOT threaded into web_fetch, search providers, gallery
//	downloads, embeddings, webhook delivery, or the app's own browser-facing
//	TLS. Extend that allowlist only with a written justification.
package tls_overrides

import (
	"crypto/tls"
	"crypto/x509"
	"log"
	"os"
	"strings"
	"sync"
)

// EnvCABundle is the env var an operator sets to point at an extra PEM
// trust bundle layered on top of the system roots. Exported so tests
// and operators can reference it by symbol rather than copying the
// string literal.
const EnvCABundle = "LLM_CA_BUNDLE"

// sharedConfig is the lazily-built *tls.Config resolved once per
// process. Matches the Python module-level _SHARED_SSL_CONTEXT: editing
// LLM_CA_BUNDLE at runtime requires a restart, mirroring the existing
// semantics of LLM_HOST, SEARXNG_INSTANCE, etc.
//
// sharedConfig == nil means "no extension; use the system default".
var (
	sharedConfig     *tls.Config
	sharedConfigOnce sync.Once
)

// extraBundlePath reads LLM_CA_BUNDLE and applies the same normalisation
// as the Python module-level _extra_bundle_path: strip whitespace, empty
// after stripping → "". Exported via the unexported name because the
// Python symbol is also module-private; the env var itself is the only
// supported operator handle.
func extraBundlePath() string {
	raw, ok := os.LookupEnv(EnvCABundle)
	if !ok {
		return ""
	}
	return strings.TrimSpace(raw)
}

// Build constructs an *tls.Config that uses the system trust store AND
// trusts the operator-supplied PEM bundle at bundlePath. It is the
// direct Go analogue of the Python _build_ssl_context() helper, with
// the bundle path passed in explicitly so tests can exercise both the
// "no bundle" and "bad bundle" branches without poking the env.
//
// Semantics — every branch matches the Python implementation:
//
//   - bundlePath == ""  → returns a usable default *tls.Config (no
//     extension) and no error. Callers fall through to Go's stock
//     trust behaviour.
//   - bundlePath points at a non-existent file → returns a default
//     *tls.Config and a non-nil error describing the miss. The Python
//     code logs and returns None (i.e. "fall back to default"); the Go
//     port returns the default config plus a warning-style error so the
//     CLI can surface it.
//   - bundlePath is a valid PEM file → returns a config whose
//     RootCAs is the system pool (or a fresh pool when the system pool
//     is nil) with the operator certs appended via AppendCertsFromPEM.
//   - bundlePath is readable but contains garbage PEM → returns a
//     default *tls.Config and a non-nil error from AppendCertsFromPEM.
//
// In every error branch the returned *tls.Config is safe to use as a
// system-default (RootCAs nil), which is what the Python "fall back to
// the default trust store" comment asks for.
func Build(bundlePath string) (*tls.Config, error) {
	if bundlePath == "" {
		// No extension configured. Return a usable default config; callers
		// that want "no override at all" can pass this straight into the
		// http.Transport.
		return &tls.Config{
			MinVersion: tls.VersionTLS12,
		}, nil
	}
	if _, err := os.Stat(bundlePath); err != nil {
		log.Printf(
			"tls_overrides: %s=%q but the file does not exist; falling back to the default trust store: %v",
			EnvCABundle, bundlePath, err,
		)
		return &tls.Config{MinVersion: tls.VersionTLS12}, err
	}
	pool, err := loadBundlePool(bundlePath)
	if err != nil {
		log.Printf(
			"tls_overrides: %s=%q failed to load (%v); falling back to the default trust store.",
			EnvCABundle, bundlePath, err,
		)
		return &tls.Config{MinVersion: tls.VersionTLS12}, err
	}
	log.Printf(
		"tls_overrides: loaded extra CA bundle %q on top of the default trust store.",
		bundlePath,
	)
	return &tls.Config{
		MinVersion: tls.VersionTLS12,
		RootCAs:    pool,
	}, nil
}

// loadBundlePool builds an *x509.CertPool seeded with the system roots
// (when available) and the operator's PEM layered on top. Falls back to
// a fresh pool if the system pool is nil.
func loadBundlePool(bundlePath string) (*x509.CertPool, error) {
	pool, err := x509.SystemCertPool()
	if err != nil {
		// Some restricted environments (sandbox, minimal containers)
		// surface SystemCertPool errors instead of returning (nil, nil).
		// Seed an empty pool rather than dropping the operator's bundle.
		pool = x509.NewCertPool()
	}
	if pool == nil {
		pool = x509.NewCertPool()
	}
	pem, err := os.ReadFile(bundlePath)
	if err != nil {
		return nil, err
	}
	if !pool.AppendCertsFromPEM(pem) {
		return nil, errBundleNotPEM
	}
	return pool, nil
}

// errBundleNotPEM is returned when AppendCertsFromPEM refuses the
// bytes at bundlePath. It is exposed as a sentinel so callers (and
// tests) can distinguish "file unreadable" from "file is not PEM".
var errBundleNotPEM = bundleNotPEMError{}

type bundleNotPEMError struct{}

func (bundleNotPEMError) Error() string {
	return "no certificates found in PEM data"
}

// LLMVerify is the process-wide LLM-provider trust override. It
// mirrors the Python llm_verify(): returns the extended-trust
// *tls.Config when LLM_CA_BUNDLE is set and loaded; otherwise returns
// a default *tls.Config so callers can hand the same shape back to the
// HTTP client regardless of whether an override is active.
//
// The result is computed once per process via sync.Once — editing
// LLM_CA_BUNDLE after the first call requires a restart, matching the
// Python module-level cache and the long-lived process model of the
// httpx clients in src/llm_core.py.
//
// Callers MUST treat the returned *tls.Config as a copy: do not mutate
// its fields, since subsequent callers in the same process will see
// the mutation. The returned config is safe to pass to http.Transport
// directly.
func LLMVerify() *tls.Config {
	sharedConfigOnce.Do(func() {
		cfg, _ := Build(extraBundlePath())
		// The error from Build is logged inside Build itself; we keep
		// the same "fall back to default" contract by storing whatever
		// (possibly default) config Build returned.
		sharedConfig = cfg
	})
	// Defensive copy so a caller mutating one field does not poison
	// every later caller's transport. We rebuild the struct rather than
	// dereference-copy (*sharedConfig) because crypto/tls.Config embeds
	// a sync.RWMutex — a shallow copy would either race on a copied
	// mutex (vet warning) or, worse, let two callers share state.
	cp := tls.Config{
		MinVersion: sharedConfig.MinVersion,
		MaxVersion: sharedConfig.MaxVersion,
		RootCAs:    sharedConfig.RootCAs,
	}
	return &cp
}

// ResetForTest clears the cached config so tests can re-run LLMVerify
// after mutating the env var. Not safe for concurrent use with
// LLMVerify; production code should never call it. Test-only via the
// _test.go file convention.
func ResetForTest() {
	sharedConfigOnce = sync.Once{}
	sharedConfig = nil
}
