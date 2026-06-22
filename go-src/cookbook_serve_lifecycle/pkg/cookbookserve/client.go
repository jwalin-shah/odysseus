// HTTP client interface, pure helpers (URL/command construction), and the
// net/http implementation. Split into this file so lifecycle.go can stay
// focused on the tick loop itself.

package cookbookserve

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"
)

// HeaderName is the request header the lifecycle adds to every internal API
// call. Mirrors INTERNAL_TOOL_HEADER in core.middleware (Python).
const HeaderName = "X-Odysseus-Internal-Tool"

// TokenEnv is the environment variable that supplies the internal-tool
// token. Empty / unset falls back to "dev" to match the Python default used
// in development.
const TokenEnv = "ODY_INTERNAL_TOOL_TOKEN"

// APIBaseEnv is the env var that overrides the internal API base URL for
// endpoint and shell-exec calls. Defaults to http://127.0.0.1:8000.
const APIBaseEnv = "ODY_INTERNAL_API_BASE"

// DefaultAPIBase is used when APIBaseEnv is unset.
const DefaultAPIBase = "http://127.0.0.1:8000"

// Token returns the current internal-tool token. Reading the env at call
// time (rather than at package init) makes tests trivial and matches the
// late-binding behaviour of the Python module.
func Token() string {
	if v := strings.TrimSpace(os.Getenv(TokenEnv)); v != "" {
		return v
	}
	return "dev"
}

// APIBase returns the API base URL, with any trailing slash trimmed.
func APIBase() string {
	v := strings.TrimSpace(os.Getenv(APIBaseEnv))
	if v == "" {
		v = DefaultAPIBase
	}
	return strings.TrimRight(v, "/")
}

// InternalHeaders returns the default header set the lifecycle uses on every
// internal API call.
func InternalHeaders() map[string]string {
	return map[string]string{HeaderName: Token()}
}

// Endpoint is the minimal shape of a /api/model-endpoints row consumed by the
// lifecycle. Extra fields returned by the server are ignored.
type Endpoint struct {
	ID      string `json:"id"`
	BaseURL string `json:"base_url"`
}

// ExecResult mirrors the JSON returned by /api/shell/exec. The exit code is
// a pointer so a missing field stays distinguishable from an explicit zero.
type ExecResult struct {
	ExitCode *int   `json:"exit_code,omitempty"`
	Stderr   string `json:"stderr,omitempty"`
	Stdout   string `json:"stdout,omitempty"`
}

// shellQuote wraps a value in single quotes for safe interpolation into a
// shell command. Mirrors shlex.quote for our inputs (no embedded NULs or
// control characters expected).
func shellQuote(s string) string {
	if s == "" {
		return "''"
	}
	var b strings.Builder
	b.WriteByte('\'')
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c == '\'' {
			b.WriteString(`'"'"'`)
			continue
		}
		b.WriteByte(c)
	}
	b.WriteByte('\'')
	return b.String()
}

// BuildKillCommand returns the shell command the lifecycle pipes through
// /api/shell/exec to kill a tmux session. Local sessions get a plain
// `tmux kill-session`; remote sessions get wrapped in ssh, with -p added
// when the SSH port is set to something other than the default "22".
func BuildKillCommand(sessionID, remoteHost, sshPort string) string {
	if remoteHost == "" {
		return fmt.Sprintf("tmux kill-session -t %s", shellQuote(sessionID))
	}
	portFlag := ""
	if sshPort != "" && sshPort != "22" {
		portFlag = fmt.Sprintf("-p %s ", shellQuote(sshPort))
	}
	return fmt.Sprintf(
		"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no %s%s 'tmux kill-session -t %s'",
		portFlag,
		shellQuote(remoteHost),
		shellQuote(sessionID),
	)
}

// pre-compiled regexes for ExtractPortFromCommand.
var (
	portFlagRe   = regexp.MustCompile(`--port\s+(\d+)`)
	ollamaHostRe = regexp.MustCompile(`OLLAMA_HOST=[^\s]*?:(\d+)`)
)

// ExtractPortFromCommand mirrors the Python regex chain in
// _delete_endpoint_for_task. It prefers an explicit `--port N`, then an
// `OLLAMA_HOST=...:N` env-style hint, then falls back to 11434 for ollama
// commands and finally the supplied defaultPort (Python callers pass 8080).
func ExtractPortFromCommand(cmd string, defaultPort int) int {
	if m := portFlagRe.FindStringSubmatch(cmd); len(m) == 2 {
		if v, err := parseIntStrict(m[1]); err == nil {
			return v
		}
	}
	if m := ollamaHostRe.FindStringSubmatch(cmd); len(m) == 2 {
		if v, err := parseIntStrict(m[1]); err == nil {
			return v
		}
	}
	if strings.Contains(cmd, "ollama") {
		return 11434
	}
	return defaultPort
}

func parseIntStrict(s string) (int, error) {
	n := 0
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c < '0' || c > '9' {
			return 0, fmt.Errorf("invalid integer %q", s)
		}
		n = n*10 + int(c-'0')
	}
	return n, nil
}

// BuildBaseURL constructs the `http://host:port/v1` shape the lifecycle uses
// to look an auto-registered endpoint up by `base_url`.
func BuildBaseURL(host string, port int) string {
	if host == "" {
		host = "host.docker.internal"
	}
	return fmt.Sprintf("http://%s:%d/v1", host, port)
}

// HostFromRemote strips the `user@` prefix the way _auto_register_llm_endpoint
// does so URL matches win when the auto-register and the lifecycle compute the
// same host string. An empty remote returns "host.docker.internal" to match
// the Python fallback used by the same registration path.
func HostFromRemote(remote string) string {
	if remote == "" {
		return "host.docker.internal"
	}
	if i := strings.LastIndex(remote, "@"); i >= 0 {
		return remote[i+1:]
	}
	return remote
}

// StopSucceededFromExec returns true when the tmux kill should be considered
// successful from the lifecycle's POV: exit_code 0 or unset, OR a stderr that
// matches one of the "already gone" patterns the Python module recognises.
func StopSucceededFromExec(res ExecResult) bool {
	if res.ExitCode == nil || *res.ExitCode == 0 {
		return true
	}
	se := strings.ToLower(res.Stderr)
	return strings.Contains(se, "no server") ||
		strings.Contains(se, "can't find session") ||
		strings.Contains(se, "session not found")
}

// HTTPClient implements Client over net/http and APIBase(). It is
// intentionally simple — no retries, no auth beyond the headers passed in —
// because the lifecycle only ever talks to a same-machine internal API.
type HTTPClient struct {
	// BaseURL is the API root the client talks to. Defaults to APIBase().
	BaseURL string
	// Client is the underlying http.Client. Defaults to one with a 15s
	// timeout to match the Python httpx default for shell-exec calls.
	Client *http.Client
	// Headers is added to every request. Defaults to InternalHeaders().
	Headers map[string]string
}

// NewHTTPClient returns an HTTPClient pre-wired to APIBase() with sensible
// per-call timeouts that match the Python defaults (8s for endpoint ops,
// 15s for shell exec).
func NewHTTPClient() *HTTPClient {
	return &HTTPClient{
		BaseURL: APIBase(),
		Client:  &http.Client{Timeout: 15 * time.Second},
		Headers: InternalHeaders(),
	}
}

func (c *HTTPClient) baseURL() string {
	if c == nil || c.BaseURL == "" {
		return APIBase()
	}
	return strings.TrimRight(c.BaseURL, "/")
}

func (c *HTTPClient) httpClient() *http.Client {
	if c == nil || c.Client == nil {
		return &http.Client{Timeout: 15 * time.Second}
	}
	return c.Client
}

func (c *HTTPClient) headers() map[string]string {
	if c == nil || len(c.Headers) == 0 {
		return InternalHeaders()
	}
	return c.Headers
}

// ListEndpoints fetches /api/model-endpoints and decodes the resulting JSON
// array. A 4xx/5xx response is reported as an error so the lifecycle can
// skip the delete step rather than fall through to a misleading "no match".
func (c *HTTPClient) ListEndpoints(ctx context.Context) ([]Endpoint, error) {
	u := c.baseURL() + "/api/model-endpoints"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return nil, err
	}
	applyHeaders(req, c.headers())
	resp, err := c.httpClient().Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("list endpoints: status %d", resp.StatusCode)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if len(bytes.TrimSpace(body)) == 0 {
		return nil, nil
	}
	var eps []Endpoint
	if err := json.Unmarshal(body, &eps); err != nil {
		return nil, fmt.Errorf("decode endpoints: %w", err)
	}
	return eps, nil
}

// DeleteEndpoint issues a DELETE on /api/model-endpoints/{id}. Any non-2xx
// response is surfaced as an error.
func (c *HTTPClient) DeleteEndpoint(ctx context.Context, id string) error {
	if strings.TrimSpace(id) == "" {
		return fmt.Errorf("empty endpoint id")
	}
	u := c.baseURL() + "/api/model-endpoints/" + url.PathEscape(id)
	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, u, nil)
	if err != nil {
		return err
	}
	applyHeaders(req, c.headers())
	resp, err := c.httpClient().Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("delete endpoint %s: status %d", id, resp.StatusCode)
	}
	_, _ = io.Copy(io.Discard, resp.Body)
	return nil
}

// ExecCommand POSTs {command: ...} to /api/shell/exec and decodes the result.
func (c *HTTPClient) ExecCommand(ctx context.Context, command string) (ExecResult, error) {
	u := c.baseURL() + "/api/shell/exec"
	body, err := json.Marshal(map[string]string{"command": command})
	if err != nil {
		return ExecResult{}, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, u, bytes.NewReader(body))
	if err != nil {
		return ExecResult{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	applyHeaders(req, c.headers())
	resp, err := c.httpClient().Do(req)
	if err != nil {
		return ExecResult{}, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return ExecResult{}, fmt.Errorf("exec command: status %d", resp.StatusCode)
	}
	out, err := io.ReadAll(resp.Body)
	if err != nil {
		return ExecResult{}, err
	}
	if len(bytes.TrimSpace(out)) == 0 {
		return ExecResult{}, nil
	}
	var res ExecResult
	if err := json.Unmarshal(out, &res); err != nil {
		return ExecResult{}, fmt.Errorf("decode exec result: %w", err)
	}
	return res, nil
}

func applyHeaders(req *http.Request, headers map[string]string) {
	for k, v := range headers {
		req.Header.Set(k, v)
	}
}
