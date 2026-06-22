package tls_overrides

import (
	"bytes"
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"errors"
	"io"
	"log"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TestBuild_EmptyPath_ReturnsDefaultConfig covers the no-bundle branch.
// Python: bundle path is None → _build_ssl_context returns None, callers
// use httpx verify=True. In Go, an empty bundlePath returns a usable
// *tls.Config with no extension.
func TestBuild_EmptyPath_ReturnsDefaultConfig(t *testing.T) {
	cfg, err := Build("")
	if err != nil {
		t.Fatalf("Build(\"\") returned err = %v, want nil", err)
	}
	if cfg == nil {
		t.Fatalf("Build(\"\") returned nil cfg; want usable default")
	}
	if cfg.RootCAs != nil {
		t.Fatalf("Build(\"\") populated RootCAs; expected nil (no extension)")
	}
	if cfg.MinVersion < tls.VersionTLS12 {
		t.Fatalf("Build(\"\") MinVersion = %x, want at least TLS 1.2", cfg.MinVersion)
	}
}

// TestBuild_NonexistentPath_ReturnsDefaultAndWarns covers the
// "bundle configured but file missing" branch. Python logs a warning and
// returns None; Go logs a warning (captured here) and returns the
// default config plus an error so callers can surface it.
func TestBuild_NonexistentPath_ReturnsDefaultAndWarns(t *testing.T) {
	var buf bytes.Buffer
	old := log.Writer()
	log.SetOutput(&buf)
	t.Cleanup(func() { log.SetOutput(old) })

	missing := filepath.Join(t.TempDir(), "does-not-exist.pem")
	cfg, err := Build(missing)
	if err == nil {
		t.Fatalf("Build(%q) returned err = nil; want non-nil", missing)
	}
	if cfg == nil {
		t.Fatalf("Build(%q) returned nil cfg; want default config", missing)
	}
	if cfg.RootCAs != nil {
		t.Fatalf("Build(%q) populated RootCAs on error path; expected nil", missing)
	}
	logs := buf.String()
	if !strings.Contains(logs, "does not exist") {
		t.Fatalf("warning log missing 'does not exist': %q", logs)
	}
	if !strings.Contains(logs, EnvCABundle) {
		t.Fatalf("warning log missing env var name %q: %q", EnvCABundle, logs)
	}
}

// TestBuild_GarbageFile_ReturnsDefaultAndWarns covers the "file exists
// but is not PEM" branch. AppendCertsFromPEM returns false; Build
// surfaces a non-nil error and logs a warning.
func TestBuild_GarbageFile_ReturnsDefaultAndWarns(t *testing.T) {
	var buf bytes.Buffer
	old := log.Writer()
	log.SetOutput(&buf)
	t.Cleanup(func() { log.SetOutput(old) })

	dir := t.TempDir()
	garbage := filepath.Join(dir, "garbage.pem")
	if err := os.WriteFile(garbage, []byte("this is not a PEM file at all"), 0o600); err != nil {
		t.Fatalf("write garbage: %v", err)
	}
	cfg, err := Build(garbage)
	if err == nil {
		t.Fatalf("Build(garbage) returned err = nil; want non-nil")
	}
	if cfg == nil {
		t.Fatalf("Build(garbage) returned nil cfg; want default config")
	}
	if cfg.RootCAs != nil {
		t.Fatalf("Build(garbage) populated RootCAs on error path; expected nil")
	}
	logs := buf.String()
	if !strings.Contains(logs, "failed to load") {
		t.Fatalf("warning log missing 'failed to load': %q", logs)
	}
}

// TestBuild_ValidPEM_PopulatesRootCAs covers the happy path: a
// well-formed PEM is appended to the cert pool.
func TestBuild_ValidPEM_PopulatesRootCAs(t *testing.T) {
	dir := t.TempDir()
	caCertPEM, _ := mintTestCA(t)
	bundlePath := filepath.Join(dir, "bundle.pem")
	if err := os.WriteFile(bundlePath, caCertPEM, 0o600); err != nil {
		t.Fatalf("write bundle: %v", err)
	}

	cfg, err := Build(bundlePath)
	if err != nil {
		t.Fatalf("Build(valid PEM) err = %v, want nil", err)
	}
	if cfg == nil || cfg.RootCAs == nil {
		t.Fatalf("Build(valid PEM) returned config without RootCAs populated")
	}
}

// TestLLMVerify_ReadsEnvVar covers the cached-entry path: when
// LLM_CA_BUNDLE is unset, LLMVerify returns a config without an
// extension. When set to a valid PEM, the second call (after
// ResetForTest) returns a config with the bundle loaded. This mirrors
// the Python module-level cache semantics.
func TestLLMVerify_ReadsEnvVar(t *testing.T) {
	t.Run("unset returns no-extension config", func(t *testing.T) {
		ResetForTest()
		t.Setenv(EnvCABundle, "")
		cfg := LLMVerify()
		if cfg == nil {
			t.Fatalf("LLMVerify returned nil")
		}
		if cfg.RootCAs != nil {
			t.Fatalf("LLMVerify with unset env populated RootCAs")
		}
	})

	t.Run("valid bundle populates RootCAs", func(t *testing.T) {
		caCertPEM, _ := mintTestCA(t)
		dir := t.TempDir()
		bundlePath := filepath.Join(dir, "ca.pem")
		if err := os.WriteFile(bundlePath, caCertPEM, 0o600); err != nil {
			t.Fatalf("write bundle: %v", err)
		}
		t.Setenv(EnvCABundle, bundlePath)
		ResetForTest()
		cfg := LLMVerify()
		if cfg == nil || cfg.RootCAs == nil {
			t.Fatalf("LLMVerify with valid bundle returned config without RootCAs")
		}
	})

	t.Run("missing bundle file logs warning and returns default", func(t *testing.T) {
		var buf bytes.Buffer
		old := log.Writer()
		log.SetOutput(&buf)
		t.Cleanup(func() { log.SetOutput(old) })

		missing := filepath.Join(t.TempDir(), "nope.pem")
		t.Setenv(EnvCABundle, missing)
		ResetForTest()
		cfg := LLMVerify()
		if cfg == nil {
			t.Fatalf("LLMVerify returned nil")
		}
		if cfg.RootCAs != nil {
			t.Fatalf("LLMVerify with missing bundle populated RootCAs")
		}
		logs := buf.String()
		if !strings.Contains(logs, "does not exist") {
			t.Fatalf("warning log missing 'does not exist': %q", logs)
		}
	})
}

// TestLLMVerify_OneShot verifies the sync.Once cache: after the first
// call, the env var is ignored on subsequent calls (matches the
// Python "edited env var requires restart" semantics).
func TestLLMVerify_OneShot(t *testing.T) {
	caCertPEM, _ := mintTestCA(t)
	dir := t.TempDir()
	bundlePath := filepath.Join(dir, "ca.pem")
	if err := os.WriteFile(bundlePath, caCertPEM, 0o600); err != nil {
		t.Fatalf("write bundle: %v", err)
	}

	t.Setenv(EnvCABundle, bundlePath)
	ResetForTest()
	first := LLMVerify()
	if first.RootCAs == nil {
		t.Fatalf("first LLMVerify did not populate RootCAs")
	}

	// Flip the env var. Without a restart, the cached config should
	// stay populated. This mirrors the Python module-level cache
	// semantics.
	t.Setenv(EnvCABundle, "")
	second := LLMVerify()
	if second.RootCAs == nil {
		t.Fatalf("LLMVerify re-read env after first call; expected cached config")
	}
}

// TestTLSDial_AcceptsBundleSignedCert_RejectsSelfSigned spins up an
// httptest-style TLS server using a private CA, then exercises both
// branches in one test:
//
//  1. With a *tls.Config built from Build(bundlePath) the cert is
//     accepted — verifying the operator's PEM actually extends trust.
//  2. With a stock *tls.Config (no extension) the same cert is
//     rejected — proving the default trust store does NOT trust the
//     private CA, and the rejection is at the handshake layer.
func TestTLSDial_AcceptsBundleSignedCert_RejectsSelfSigned(t *testing.T) {
	caCertPEM, caKeyPEM := mintTestCA(t)
	bundlePath := writePEM(t, "ca.pem", caCertPEM)

	serverCert := mintLeafCert(t, caCertPEM, caKeyPEM, "localhost")

	serverCfg := &tls.Config{
		Certificates: []tls.Certificate{serverCert},
	}

	listener, err := tls.Listen("tcp", "127.0.0.1:0", serverCfg)
	if err != nil {
		t.Fatalf("tls.Listen: %v", err)
	}
	t.Cleanup(func() { _ = listener.Close() })

	// Accept loop running in a goroutine. Each connection is closed
	// after a best-effort handshake read; the test does not send any
	// application data, so we use a short read deadline to prevent
	// the server goroutine from blocking forever on a client that
	// closes immediately.
	doneAccept := make(chan error, 8)
	go func() {
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			tc, ok := conn.(*tls.Conn)
			if !ok {
				doneAccept <- errors.New("non-tls conn")
				_ = conn.Close()
				continue
			}
			if err := tc.Handshake(); err != nil {
				doneAccept <- err
				_ = tc.Close()
				continue
			}
			// Set a tiny read deadline so we don't block waiting for
			// data the client never sends. Either we read EOF (client
			// closed) or the deadline fires — both are acceptable.
			_ = tc.SetReadDeadline(time.Now().Add(50 * time.Millisecond))
			buf := make([]byte, 1)
			_, _ = tc.Read(buf)
			doneAccept <- tc.Close()
		}
	}()

	addr := listener.Addr().String()

	// --- Branch 1: client uses the bundle; handshake must succeed.
	bundleCfg, err := Build(bundlePath)
	if err != nil {
		t.Fatalf("Build: %v", err)
	}
	bundleCfg.ServerName = "localhost"
	bundleCfg.InsecureSkipVerify = false
	if err := tlsDialOnce(addr, bundleCfg); err != nil {
		t.Fatalf("bundle-signed cert rejected with bundle trust: %v", err)
	}

	// --- Branch 2: client uses a stock config (no RootCAs); the same
	// cert must be rejected. The rejection may surface as a handshake
	// error from DialWith, or as a Read EOF — both indicate the
	// default trust store did not validate the private-CA-signed cert.
	stockCfg := &tls.Config{
		ServerName:         "localhost",
		InsecureSkipVerify: false,
		MinVersion:         tls.VersionTLS12,
	}
	// Branch 2 shares the listener with Branch 1. A non-accepted
	// connection can sit in the accept backlog; the server goroutine
	// above only iterates while Accept returns successfully, so an
	// outstanding-but-rejected connection can hold the listener. We
	// also rely on a small client-side deadline so a stuck read never
	// hangs the test for the full package timeout.
	if err := tlsDialOnce(addr, stockCfg); err == nil {
		t.Fatalf("self-signed cert accepted with default trust; expected rejection")
	}
}

// tlsDialOnce opens a TLS connection, waits for the handshake to
// complete, and returns the first error it sees. Returns nil when the
// handshake succeeds and the server side has had a chance to close.
func tlsDialOnce(addr string, cfg *tls.Config) error {
	d := net.Dialer{Timeout: 5 * time.Second}
	conn, err := d.Dial("tcp", addr)
	if err != nil {
		return err
	}
	tc := tls.Client(conn, cfg)
	defer func() {
		_ = tc.Close()
	}()
	if err := tc.Handshake(); err != nil {
		return err
	}
	// Force a single round trip so the server-side handshake also
	// definitively completes.
	if _, err := tc.Read(make([]byte, 1)); err != nil && err != io.EOF {
		return err
	}
	return nil
}

// mintTestCA generates a throwaway RSA CA cert in-memory and returns
// its PEM-encoded certificate and private key. Used by Build / LLMVerify
// tests to exercise the "valid PEM" branch without committing a real
// cert to the repo.
func mintTestCA(t *testing.T) (certPEM []byte, keyPEM []byte) {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa.GenerateKey: %v", err)
	}
	tmpl := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject: pkix.Name{
			CommonName:   "tls_overrides test CA",
			Organization: []string{"odysseus test"},
		},
		NotBefore:             time.Now().Add(-time.Hour),
		NotAfter:              time.Now().Add(24 * time.Hour),
		KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageDigitalSignature,
		BasicConstraintsValid: true,
		IsCA:                  true,
		MaxPathLen:            1,
	}
	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, &key.PublicKey, key)
	if err != nil {
		t.Fatalf("x509.CreateCertificate: %v", err)
	}
	certPEM = pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatalf("x509.MarshalPKCS8PrivateKey: %v", err)
	}
	keyPEM = pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: keyDER})
	return certPEM, keyPEM
}

// mintLeafCert issues a leaf certificate (SAN=localhost) signed by the
// supplied CA. Returns a tls.Certificate ready to hand to a server.
func mintLeafCert(t *testing.T, caCertPEM, caKeyPEM []byte, cn string) tls.Certificate {
	t.Helper()
	caCertBlock, _ := pem.Decode(caCertPEM)
	if caCertBlock == nil {
		t.Fatalf("decode CA cert PEM")
	}
	caCert, err := x509.ParseCertificate(caCertBlock.Bytes)
	if err != nil {
		t.Fatalf("parse CA cert: %v", err)
	}
	caKeyBlock, _ := pem.Decode(caKeyPEM)
	if caKeyBlock == nil {
		t.Fatalf("decode CA key PEM")
	}
	caKeyAny, err := x509.ParsePKCS8PrivateKey(caKeyBlock.Bytes)
	if err != nil {
		t.Fatalf("parse CA key: %v", err)
	}
	caKey, ok := caKeyAny.(*rsa.PrivateKey)
	if !ok {
		t.Fatalf("CA key is not RSA")
	}

	leafKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa.GenerateKey leaf: %v", err)
	}
	leafTmpl := &x509.Certificate{
		SerialNumber: big.NewInt(2),
		Subject: pkix.Name{
			CommonName:   cn,
			Organization: []string{"odysseus test"},
		},
		DNSNames:    []string{cn},
		NotBefore:   time.Now().Add(-time.Hour),
		NotAfter:    time.Now().Add(24 * time.Hour),
		KeyUsage:    x509.KeyUsageDigitalSignature | x509.KeyUsageKeyEncipherment,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	leafDER, err := x509.CreateCertificate(rand.Reader, leafTmpl, caCert, &leafKey.PublicKey, caKey)
	if err != nil {
		t.Fatalf("x509.CreateCertificate leaf: %v", err)
	}
	leafPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: leafDER})
	leafKeyDER, err := x509.MarshalPKCS8PrivateKey(leafKey)
	if err != nil {
		t.Fatalf("x509.MarshalPKCS8PrivateKey leaf: %v", err)
	}
	leafKeyPEM := pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: leafKeyDER})
	cert, err := tls.X509KeyPair(leafPEM, leafKeyPEM)
	if err != nil {
		t.Fatalf("tls.X509KeyPair: %v", err)
	}
	return cert
}

// writePEM drops the supplied bytes into a temp file under name and
// returns the absolute path. Test helper only.
func writePEM(t *testing.T, name string, data []byte) string {
	t.Helper()
	dir := t.TempDir()
	p := filepath.Join(dir, name)
	if err := os.WriteFile(p, data, 0o600); err != nil {
		t.Fatalf("write %s: %v", name, err)
	}
	return p
}

// TestEnvCABundleConstant asserts the env var name is preserved
// exactly — operators and tests depend on the spelling.
func TestEnvCABundleConstant(t *testing.T) {
	if EnvCABundle != "LLM_CA_BUNDLE" {
		t.Fatalf("EnvCABundle = %q, want LLM_CA_BUNDLE", EnvCABundle)
	}
}

// TestExtraBundlePath_StripsAndNormalises mirrors the Python
// `_extra_bundle_path = (os.environ.get("LLM_CA_BUNDLE") or "").strip() or None`
// chain: empty / whitespace-only env vars resolve to "".
func TestExtraBundlePath_StripsAndNormalises(t *testing.T) {
	cases := []struct {
		name string
		set  bool
		val  string
		want string
	}{
		{name: "unset", set: false, want: ""},
		{name: "empty", set: true, val: "", want: ""},
		{name: "whitespace", set: true, val: "   \t  ", want: ""},
		{name: "trimmed path", set: true, val: "  /etc/ca.pem  ", want: "/etc/ca.pem"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if tc.set {
				t.Setenv(EnvCABundle, tc.val)
			} else {
				// t.Setenv cannot unset; remove via os.Unsetenv.
				t.Setenv(EnvCABundle, "")
				_ = os.Unsetenv(EnvCABundle)
			}
			ResetForTest()
			got := extraBundlePath()
			if got != tc.want {
				t.Fatalf("extraBundlePath() = %q, want %q", got, tc.want)
			}
		})
	}
}
