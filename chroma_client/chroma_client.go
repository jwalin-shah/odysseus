// Package chroma_client is a singleton ChromaDB HTTP client.
//
// It mirrors the Python chroma_client.py in ../src:
//   - One process-wide client, lazily created.
//   - TCP probe before connect (fails fast instead of OS-default timeouts).
//   - Heartbeat health check before caching — failures do NOT poison
//     the singleton so the next call retries (matches Python behavior).
package chroma_client

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

// Client is the minimal ChromaDB surface used by this package.
// Additional methods can be added as consumers require them.
type Client interface {
	Heartbeat(ctx context.Context) error
}

// Config holds connection parameters for a ChromaDB HTTP service.
type Config struct {
	Host           string
	Port           int
	ConnectTimeout time.Duration
}

// HeartbeatPath is the ChromaDB HTTP heartbeat endpoint.
const HeartbeatPath = "/api/v1/heartbeat"

// ConfigFromEnv builds a Config from CHROMADB_HOST / CHROMADB_PORT /
// CHROMADB_CONNECT_TIMEOUT. Defaults match the Python reference:
// localhost:8100 with a 2s connect timeout.
func ConfigFromEnv() (Config, error) {
	cfg := Config{
		Host:           "localhost",
		Port:           8100,
		ConnectTimeout: 2 * time.Second,
	}

	if v := os.Getenv("CHROMADB_HOST"); v != "" {
		cfg.Host = v
	}

	if v := os.Getenv("CHROMADB_PORT"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			return Config{}, fmt.Errorf("invalid CHROMADB_PORT %q: %w", v, err)
		}
		cfg.Port = n
	}

	if v := os.Getenv("CHROMADB_CONNECT_TIMEOUT"); v != "" {
		// Accept both "2", "2s", "500ms", etc. via ParseDuration; fall back
		// to plain seconds if ParseDuration rejects the bare-float form the
		// Python version accepts.
		d, err := time.ParseDuration(v)
		if err != nil {
			f, ferr := strconv.ParseFloat(v, 64)
			if ferr != nil {
				return Config{}, fmt.Errorf("invalid CHROMADB_CONNECT_TIMEOUT %q: %w", v, err)
			}
			d = time.Duration(f * float64(time.Second))
		}
		cfg.ConnectTimeout = d
	}

	return cfg, nil
}

// ProbePort dials host:port with cfg.ConnectTimeout and returns nil if the
// connection succeeds. It honors ctx cancellation if the dialer can observe it.
//
// The error message intentionally matches the Python source so log scrapers
// and existing runbooks still recognize it.
func ProbePort(ctx context.Context, cfg Config) error {
	d := net.Dialer{Timeout: cfg.ConnectTimeout}
	addr := net.JoinHostPort(cfg.Host, strconv.Itoa(cfg.Port))
	conn, err := d.DialContext(ctx, "tcp", addr)
	if err != nil {
		// Surface context errors verbatim (caller expects context.Canceled /
		// context.DeadlineExceeded to propagate).
		if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
			return err
		}
		return fmt.Errorf(
			"ChromaDB is not reachable at %s:%d. Start the ChromaDB service "+
				"(e.g. `docker compose up chromadb`) or set CHROMADB_HOST / "+
				"CHROMADB_PORT to point at a running instance: %w",
			cfg.Host, cfg.Port, err,
		)
	}
	_ = conn.Close()
	return nil
}

// HTTPClient is a thin stdlib HTTP client targeting a ChromaDB service.
type HTTPClient struct {
	BaseURL    string
	HTTPClient *http.Client
}

// NewHTTPClient builds an HTTPClient targeting cfg. The HTTP timeout is set to
// cfg.ConnectTimeout to keep behavior aligned with the Python probe budget.
func NewHTTPClient(cfg Config) *HTTPClient {
	return &HTTPClient{
		BaseURL:    fmt.Sprintf("http://%s:%d", cfg.Host, cfg.Port),
		HTTPClient: &http.Client{Timeout: cfg.ConnectTimeout},
	}
}

// Heartbeat issues GET /api/v1/heartbeat. 2xx -> nil; non-2xx -> status error;
// transport / context errors are wrapped and returned verbatim.
func (c *HTTPClient) Heartbeat(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.BaseURL+HeartbeatPath, nil)
	if err != nil {
		return fmt.Errorf("chroma heartbeat: build request: %w", err)
	}
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("chroma heartbeat: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("chroma heartbeat: unexpected status %d", resp.StatusCode)
	}
	return nil
}

// --- singleton ---------------------------------------------------------------

var (
	globalClient atomic.Pointer[HTTPClient]
	connectMu    sync.Mutex
)

// Get returns the cached client or connects, probes the port, and heartbeats.
// On any failure during connect, the singleton is left unset so a later Get
// retries from scratch — matching the Python implementation's "don't poison
// the cache" contract.
func Get(ctx context.Context) (*HTTPClient, error) {
	if c := globalClient.Load(); c != nil {
		return c, nil
	}

	connectMu.Lock()
	defer connectMu.Unlock()

	// Double-checked: another goroutine may have connected while we waited.
	if c := globalClient.Load(); c != nil {
		return c, nil
	}

	cfg, err := ConfigFromEnv()
	if err != nil {
		return nil, err
	}

	if err := ProbePort(ctx, cfg); err != nil {
		return nil, err
	}

	client := NewHTTPClient(cfg)
	if err := client.Heartbeat(ctx); err != nil {
		// Do not cache — next call retries.
		return nil, err
	}

	globalClient.Store(client)
	return client, nil
}

// Reset clears the singleton. Safe for concurrent use; matches reset_client()
// in the Python source.
func Reset() {
	connectMu.Lock()
	globalClient.Store(nil)
	connectMu.Unlock()
}
