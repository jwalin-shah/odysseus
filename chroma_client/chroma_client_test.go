// chroma_client unit tests.
package chroma_client

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// --- ConfigFromEnv -----------------------------------------------------------

func TestConfigFromEnv_AllUnset(t *testing.T) {
	t.Setenv("CHROMADB_HOST", "")
	t.Setenv("CHROMADB_PORT", "")
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "")

	cfg, err := ConfigFromEnv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Host != "localhost" {
		t.Errorf("Host = %q, want %q", cfg.Host, "localhost")
	}
	if cfg.Port != 8100 {
		t.Errorf("Port = %d, want %d", cfg.Port, 8100)
	}
	if cfg.ConnectTimeout != 2*time.Second {
		t.Errorf("ConnectTimeout = %v, want %v", cfg.ConnectTimeout, 2*time.Second)
	}
}

func TestConfigFromEnv_HostOnly(t *testing.T) {
	t.Setenv("CHROMADB_HOST", "10.0.0.7")
	t.Setenv("CHROMADB_PORT", "")
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "")

	cfg, err := ConfigFromEnv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Host != "10.0.0.7" {
		t.Errorf("Host = %q, want 10.0.0.7", cfg.Host)
	}
	if cfg.Port != 8100 {
		t.Errorf("Port = %d, want 8100", cfg.Port)
	}
	if cfg.ConnectTimeout != 2*time.Second {
		t.Errorf("ConnectTimeout = %v, want 2s", cfg.ConnectTimeout)
	}
}

func TestConfigFromEnv_InvalidPort(t *testing.T) {
	t.Setenv("CHROMADB_HOST", "")
	t.Setenv("CHROMADB_PORT", "not-a-number")
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "")

	if _, err := ConfigFromEnv(); err == nil {
		t.Fatal("expected error for invalid PORT, got nil")
	}
}

func TestConfigFromEnv_InvalidTimeout(t *testing.T) {
	t.Setenv("CHROMADB_HOST", "")
	t.Setenv("CHROMADB_PORT", "")
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "definitely-not-a-duration")

	if _, err := ConfigFromEnv(); err == nil {
		t.Fatal("expected error for invalid TIMEOUT, got nil")
	}
}

func TestConfigFromEnv_CustomPortAndDuration(t *testing.T) {
	t.Setenv("CHROMADB_HOST", "chroma.local")
	t.Setenv("CHROMADB_PORT", "9999")
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "750ms")

	cfg, err := ConfigFromEnv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.Host != "chroma.local" {
		t.Errorf("Host = %q", cfg.Host)
	}
	if cfg.Port != 9999 {
		t.Errorf("Port = %d, want 9999", cfg.Port)
	}
	if cfg.ConnectTimeout != 750*time.Millisecond {
		t.Errorf("ConnectTimeout = %v, want 750ms", cfg.ConnectTimeout)
	}
}

func TestConfigFromEnv_CustomTimeoutSecondsFloat(t *testing.T) {
	t.Setenv("CHROMADB_HOST", "")
	t.Setenv("CHROMADB_PORT", "")
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "1.5")

	cfg, err := ConfigFromEnv()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.ConnectTimeout != 1500*time.Millisecond {
		t.Errorf("ConnectTimeout = %v, want 1.5s", cfg.ConnectTimeout)
	}
}

// --- ProbePort ---------------------------------------------------------------

func TestProbePort_OpenPort(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	defer ln.Close()

	host, port, err := net.SplitHostPort(ln.Addr().String())
	if err != nil {
		t.Fatalf("split host/port: %v", err)
	}
	var p int
	if _, err := fmt.Sscanf(port, "%d", &p); err != nil {
		t.Fatalf("parse port: %v", err)
	}

	cfg := Config{Host: host, Port: p, ConnectTimeout: 2 * time.Second}
	if err := ProbePort(context.Background(), cfg); err != nil {
		t.Errorf("expected nil for open port, got %v", err)
	}
}

func TestProbePort_ClosedPort(t *testing.T) {
	// Bind a listener, capture its port, then close it — guarantees an
	// unused-but-reserved port that refuses connections.
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	host, port, _ := net.SplitHostPort(ln.Addr().String())
	ln.Close()

	var p int
	fmt.Sscanf(port, "%d", &p)

	cfg := Config{Host: host, Port: p, ConnectTimeout: 250 * time.Millisecond}
	err = ProbePort(context.Background(), cfg)
	if err == nil {
		t.Fatal("expected error for closed port, got nil")
	}
	if !strings.Contains(err.Error(), "ChromaDB is not reachable at") {
		t.Errorf("error %q missing expected prefix", err)
	}
	if !strings.Contains(err.Error(), host) || !strings.Contains(err.Error(), port) {
		t.Errorf("error %q missing host:port", err)
	}
}

func TestProbePort_ContextCanceled(t *testing.T) {
	// Reserve a port we won't be listening on so the dial blocks until ctx
	// is canceled (localhost connections to a closed port fail immediately
	// on most kernels, so use a context with an immediate deadline).
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	host, port, _ := net.SplitHostPort(ln.Addr().String())
	ln.Close()

	var p int
	fmt.Sscanf(port, "%d", &p)

	cfg := Config{Host: host, Port: p, ConnectTimeout: 30 * time.Second}

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // cancel immediately

	err = ProbePort(ctx, cfg)
	if err == nil {
		t.Fatal("expected error when ctx canceled, got nil")
	}
	if !errors.Is(err, context.Canceled) {
		t.Errorf("expected context.Canceled, got %v", err)
	}
}

// --- HTTPClient.Heartbeat ----------------------------------------------------

func TestHeartbeat_200(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != HeartbeatPath {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	host, port, _ := splitHostPort(t, srv.URL)
	cfg := Config{Host: host, Port: port, ConnectTimeout: 2 * time.Second}
	c := NewHTTPClient(cfg)

	if err := c.Heartbeat(context.Background()); err != nil {
		t.Errorf("expected nil for 200, got %v", err)
	}
}

func TestHeartbeat_500(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	host, port, _ := splitHostPort(t, srv.URL)
	cfg := Config{Host: host, Port: port, ConnectTimeout: 2 * time.Second}
	c := NewHTTPClient(cfg)

	err := c.Heartbeat(context.Background())
	if err == nil {
		t.Fatal("expected error for 500, got nil")
	}
	if !strings.Contains(err.Error(), "500") {
		t.Errorf("error %q missing status code", err)
	}
}

func TestHeartbeat_ServerClosed(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	host, port, _ := splitHostPort(t, srv.URL)
	srv.Close() // closed -> connection refused on next dial

	cfg := Config{Host: host, Port: port, ConnectTimeout: 250 * time.Millisecond}
	c := NewHTTPClient(cfg)

	if err := c.Heartbeat(context.Background()); err == nil {
		t.Fatal("expected error against closed server, got nil")
	}
}

func TestHeartbeat_ContextCanceled(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	host, port, _ := splitHostPort(t, srv.URL)
	cfg := Config{Host: host, Port: port, ConnectTimeout: 2 * time.Second}
	c := NewHTTPClient(cfg)

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	err := c.Heartbeat(ctx)
	if err == nil {
		t.Fatal("expected error when ctx canceled, got nil")
	}
}

// --- Singleton behavior ------------------------------------------------------

func TestGet_CachesPointer(t *testing.T) {
	// Spin up a listener + http server, point env at it, then run Get twice.
	srv := startProbeServer(t, 200)
	defer srv.Close()

	t.Setenv("CHROMADB_HOST", "127.0.0.1")
	t.Setenv("CHROMADB_PORT", srv.port)
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "2s")
	Reset()

	first, err := Get(context.Background())
	if err != nil {
		t.Fatalf("first Get: %v", err)
	}
	second, err := Get(context.Background())
	if err != nil {
		t.Fatalf("second Get: %v", err)
	}
	if first != second {
		t.Errorf("expected same pointer; got %p vs %p", first, second)
	}
}

func TestGet_ResetsAndRebuilds(t *testing.T) {
	srv1 := startProbeServer(t, 200)
	defer srv1.Close()

	t.Setenv("CHROMADB_HOST", "127.0.0.1")
	t.Setenv("CHROMADB_PORT", srv1.port)
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "2s")
	Reset()

	first, err := Get(context.Background())
	if err != nil {
		t.Fatalf("first Get: %v", err)
	}

	// Switch env to a different server, reset, then re-Get.
	srv2 := startProbeServer(t, 200)
	defer srv2.Close()
	t.Setenv("CHROMADB_PORT", srv2.port)
	Reset()

	second, err := Get(context.Background())
	if err != nil {
		t.Fatalf("post-reset Get: %v", err)
	}
	if first == second {
		t.Errorf("expected different pointer after Reset; got %p", first)
	}
	if second.BaseURL != "http://127.0.0.1:"+srv2.port {
		t.Errorf("BaseURL = %q, want host:%s", second.BaseURL, srv2.port)
	}
}

func TestGet_HeartbeatFailureDoesNotCache(t *testing.T) {
	// Listener is open (so ProbePort succeeds) but heartbeat returns 500.
	srv := startProbeServer(t, 500)
	defer srv.Close()

	t.Setenv("CHROMADB_HOST", "127.0.0.1")
	t.Setenv("CHROMADB_PORT", srv.port)
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "2s")
	Reset()

	if _, err := Get(context.Background()); err == nil {
		t.Fatal("expected error from Get on heartbeat 500, got nil")
	}
	if cached := globalClient.Load(); cached != nil {
		t.Errorf("singleton should not be cached after heartbeat failure; got %p", cached)
	}

	// Flip the server to 200 — next Get should succeed without an extra
	// Reset (Python's "don't poison" contract).
	srv.setStatus(200)
	if _, err := Get(context.Background()); err != nil {
		t.Errorf("retry after heartbeat fix should succeed; got %v", err)
	}
}

func TestGet_ConcurrentSingleConnect(t *testing.T) {
	// Server with a heartbeat counter — verify it only gets hit once across
	// many concurrent Get calls.
	var hits atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits.Add(1)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()

	t.Setenv("CHROMADB_HOST", "127.0.0.1")
	t.Setenv("CHROMADB_PORT", srvPort(t, srv))
	t.Setenv("CHROMADB_CONNECT_TIMEOUT", "2s")
	Reset()

	const N = 32
	var wg sync.WaitGroup
	wg.Add(N)
	results := make([]*HTTPClient, N)

	start := make(chan struct{}) // release all goroutines at once
	for i := 0; i < N; i++ {
		go func(i int) {
			defer wg.Done()
			<-start
			c, err := Get(context.Background())
			if err != nil {
				t.Errorf("goroutine %d: Get: %v", i, err)
				return
			}
			results[i] = c
		}(i)
	}
	close(start)
	wg.Wait()

	// All goroutines should have gotten a non-nil client.
	for i, c := range results {
		if c == nil {
			t.Errorf("goroutine %d: nil client", i)
		}
	}
	// And every non-nil result must point at the same singleton.
	for i := 1; i < N; i++ {
		if results[i] != results[0] {
			t.Errorf("goroutine %d returned different pointer (%p vs %p)",
				i, results[i], results[0])
			break
		}
	}

	// Only one heartbeat should have been observed across the whole burst.
	// Allow a small slack to account for any double-checked-locking retries
	// the OS may force — but the contract is "essentially one", and 1 is the
	// expected answer.
	if got := hits.Load(); got > 1 {
		t.Errorf("expected <=1 heartbeat during burst, got %d", got)
	}
}

// --- helpers -----------------------------------------------------------------

type probeServer struct {
	srv    *httptest.Server
	port   string
	status atomic.Int32
}

func (p *probeServer) Close()             { p.srv.Close() }
func (p *probeServer) setStatus(code int) { p.status.Store(int32(code)) }

func startProbeServer(t *testing.T, initialStatus int) *probeServer {
	t.Helper()
	p := &probeServer{}
	p.status.Store(int32(initialStatus))
	p.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(int(p.status.Load()))
	}))
	_, port, err := net.SplitHostPort(p.srv.URL[7:]) // strip "http://"
	if err != nil {
		p.srv.Close()
		t.Fatalf("split server addr: %v", err)
	}
	p.port = port
	return p
}

func srvPort(t *testing.T, srv *httptest.Server) string {
	t.Helper()
	_, port, err := net.SplitHostPort(srv.URL[7:])
	if err != nil {
		t.Fatalf("split server addr: %v", err)
	}
	return port
}

func splitHostPort(t *testing.T, url string) (string, int, error) {
	t.Helper()
	h, pStr, err := net.SplitHostPort(url[7:])
	if err != nil {
		return "", 0, err
	}
	var p int
	fmt.Sscanf(pStr, "%d", &p)
	return h, p, nil
}
