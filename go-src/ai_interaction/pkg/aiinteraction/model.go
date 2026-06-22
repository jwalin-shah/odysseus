package aiinteraction

import (
	"fmt"
	"net/url"
	"strings"
)

// ParseModelSpec splits a model specifier into the (model_name,
// endpoint_name) pair _resolve_model expects. The Python source does
// `rsplit("@", 1)`, so:
//
//   - "gpt-4" -> ("gpt-4", "")
//   - "gpt-4@my-endpoint" -> ("gpt-4", "my-endpoint")
//   - "  gpt-4 @ my-endpoint  " -> ("gpt-4", "my-endpoint")
//
// The model name is stripped, but case is preserved (Anthropic model
// ids are lower-case; OpenAI-compatible providers may be mixed case).
func ParseModelSpec(spec string) (ModelSpec, error) {
	trimmed := strings.TrimSpace(spec)
	if trimmed == "" {
		return ModelSpec{}, fmt.Errorf("model specifier is required")
	}
	if !strings.Contains(trimmed, "@") {
		return ModelSpec{ModelName: trimmed}, nil
	}
	idx := strings.LastIndex(trimmed, "@")
	model := strings.TrimSpace(trimmed[:idx])
	endpoint := strings.TrimSpace(trimmed[idx+1:])
	if model == "" {
		return ModelSpec{}, fmt.Errorf("model specifier '%s' is missing the model name before '@'", spec)
	}
	if endpoint == "" {
		return ModelSpec{}, fmt.Errorf("model specifier '%s' is missing the endpoint name after '@'", spec)
	}
	return ModelSpec{ModelName: model, EndpointName: endpoint}, nil
}

// BuildChatURL mirrors src/endpoint_resolver.build_chat_url. The
// Python source uses urlparse-driven path surgery (it strips the
// current path, then appends the provider-specific suffix) — the Go
// port does the same so non-empty paths preserve their semantics.
func BuildChatURL(base string) string {
	base = normalizeBase(base)
	provider := detectProvider(base)
	switch provider {
	case "anthropic":
		return appendPath(anthropicAPIRoot(base), "/v1/messages")
	case "ollama":
		return appendPath(ollamaAPIRoot(base), "/chat")
	}
	// OpenAI-compatible default: insert /v1 only when path is empty AND
	// the host is api.openai.com (mirrors _pathless_host). A trailing
	// slash is pathless because urlparse(...).path == "/" and "/" strips
	// to "". The Python source uses the same `not path.strip("/")`
	// rule.
	if pathlessHost(base, "api.openai.com") {
		base = appendPath(base, "/v1")
	}
	return appendPath(base, "/chat/completions")
}

// BuildModelsURL mirrors src/endpoint_resolver.build_models_url.
// Returns "" when the provider does not expose a model list
// (chatgpt-subscription). Local model servers with no explicit path
// conventionally expose `/v1/models`; non-local unknown hosts do not
// invent `/v1`.
func BuildModelsURL(base string) string {
	base = normalizeBase(base)
	base = prepareBase(base)
	provider := detectProvider(base)
	switch provider {
	case "anthropic":
		return appendPath(anthropicAPIRoot(base), "/v1/models")
	case "ollama":
		return appendPath(ollamaAPIRoot(base), "/tags")
	case "chatgpt-subscription":
		return ""
	}
	u, err := url.Parse(base)
	if err != nil {
		return appendPath(base, "/models")
	}
	host := strings.ToLower(u.Hostname())
	isLocal := host == "localhost" || host == "127.0.0.1" || host == "::1" || host == "host.docker.internal"
	usesV1 := isLocal || host == "api.deepseek.com" || host == "api.openai.com"
	if u.Path == "" && usesV1 {
		base = appendPath(base, "/v1")
	}
	return appendPath(base, "/models")
}

// BuildHeaders mirrors src/endpoint_resolver.build_headers. Anthropic
// gets x-api-key + version; everything else gets Authorization:
// Bearer +api_key (with openrouter getting the additional Referer
// headers).
func BuildHeaders(apiKey, base string) map[string]string {
	headers := map[string]string{}
	provider := detectProvider(base)
	switch provider {
	case "anthropic":
		if apiKey != "" {
			headers["x-api-key"] = apiKey
		}
		headers["anthropic-version"] = "2023-06-01"
		return headers
	case "openrouter":
		if apiKey != "" {
			headers["Authorization"] = "Bearer " + apiKey
		}
		headers["HTTP-Referer"] = "https://github.com/pewdiepie-archdaemon/odysseus"
		headers["X-OpenRouter-Title"] = "Odysseus"
		return headers
	}
	if apiKey != "" {
		headers["Authorization"] = "Bearer " + apiKey
	}
	return headers
}

// detectProvider mirrors src.llm_core._detect_provider for the
// providers the model resolver cares about. It uses the same
// hostname-match logic and the Ollama-native-URL detection so
// OpenAI-compatible vs native Ollama resolution matches Python.
func detectProvider(rawURL string) string {
	base := prepareBase(rawURL)
	if isOllamaNative(base) {
		return "ollama"
	}
	u, err := url.Parse(base)
	if err != nil {
		return "openai"
	}
	host := strings.ToLower(u.Hostname())
	if hostMatch(host, "anthropic.com") {
		return "anthropic"
	}
	if hostMatch(host, "openai.com") {
		return "openai"
	}
	if hostMatch(host, "openrouter.ai") {
		return "openrouter"
	}
	if hostMatch(host, "groq.com") {
		return "groq"
	}
	return "openai"
}

// hostMatch reports whether host equals suffix or is a subdomain of
// it (host == suffix || strings.HasSuffix(host, "."+suffix)). Mirrors
// the Python _host_match helper.
func hostMatch(host, suffix string) bool {
	host = strings.ToLower(host)
	suffix = strings.ToLower(suffix)
	if host == suffix {
		return true
	}
	return strings.HasSuffix(host, "."+suffix)
}

// isOllamaNative mirrors src.llm_core._is_ollama_native_url. A URL is
// native Ollama when:
//
//   - the host is ollama.com; OR
//   - the host is local (localhost / 127.0.0.1 / 0.0.0.0 / ::1) OR the
//     port is 11434, AND the path is empty, /api, or starts with /api/.
//   - the path is /v1* → false (that's the OpenAI-compat surface).
//
// The function accepts a rawURL (with optional trailing slash) so it
// can urlparse internally — matches the Python source signature.
func isOllamaNative(rawURL string) bool {
	u, err := url.Parse(rawURL)
	if err != nil {
		return false
	}
	host := strings.ToLower(u.Hostname())
	path := strings.TrimRight(u.Path, "/")
	if hostMatch(host, "ollama.com") {
		return true
	}
	if strings.HasPrefix(path, "/v1") {
		return false
	}
	local := host == "localhost" || host == "127.0.0.1" || host == "0.0.0.0" || host == "::1"
	if !local {
		return false
	}
	// Port check ONLY applies when the path indicates the native API
	// surface (/api, /api/chat, etc.). A bare localhost URL on a
	// non-standard port without /api is just a generic OpenAI-compatible
	// server. This mirrors the Python short-circuit: the path test is
	// what actually differentiates Ollama from a local llama.cpp.
	if path != "" && path != "/api" && !strings.HasPrefix(path, "/api/") {
		return false
	}
	if path == "" && u.Port() != "" && u.Port() != "11434" {
		return false
	}
	return path == "" || path == "/api" || strings.HasPrefix(path, "/api/")
}

// pathlessHost reports whether base has no path component AND the
// host equals target. Mirrors _pathless_host: a URL like
// "https://api.openai.com/" is pathless (Python strips "/" to ""),
// whereas "https://api.openai.com/v1" is not.
func pathlessHost(base, target string) bool {
	u, err := url.Parse(base)
	if err != nil {
		return false
	}
	host := strings.ToLower(u.Hostname())
	return host == target && strings.Trim(u.Path, "/") == ""
}

// prepareBase strips trailing slashes from rawURL so subsequent path
// appends work cleanly.
func prepareBase(rawURL string) string {
	return strings.TrimRight(rawURL, "/")
}

// normalizeBase strips the suffix segments normalize_base in Python
// strips. The Python source chains normalize_base →
// _validated_endpoint_base → strip trailing slash. The Go port
// implements the same ordering, dropping query/fragment.
func normalizeBase(rawURL string) string {
	s := strings.TrimSpace(rawURL)
	s = strings.TrimRight(s, "/")
	for _, suffix := range []string{"/models", "/chat/completions", "/completions", "/v1/messages", "/responses"} {
		if strings.HasSuffix(s, suffix) {
			s = strings.TrimRight(s[:len(s)-len(suffix)], "/")
		}
	}
	for _, suffix := range []string{"/chat", "/tags", "/generate"} {
		apiSuffix := "/api" + suffix
		if strings.HasSuffix(s, apiSuffix) {
			s = strings.TrimRight(s[:len(s)-len(suffix)], "/")
		}
	}
	if strings.Contains(s, "?") || strings.Contains(s, "#") {
		// _validated_endpoint_base raises on these; the Go port
		// silently strips query/fragment to match urlunparse behaviour.
		if i := strings.Index(s, "?"); i >= 0 {
			s = s[:i]
		}
		if i := strings.Index(s, "#"); i >= 0 {
			s = s[:i]
		}
		s = strings.TrimRight(s, "/")
	}
	return s
}

// appendPath joins base and path. The Python source uses urlparse
// path surgery: it strips the current path, then prepends the new
// path. The Go port reproduces that exactly so a base like
// "https://api.openai.com/v1" + "/chat/completions" stays as
// "https://api.openai.com/v1/chat/completions" (not
// "https://api.openai.com/v1/chat/completions" + path).
func appendPath(base, path string) string {
	if base == "" {
		if !strings.HasPrefix(path, "/") {
			return "/" + path
		}
		return path
	}
	u, err := url.Parse(base)
	if err != nil {
		// Fall back to a simple join.
		sep := ""
		if !strings.HasSuffix(base, "/") && !strings.HasPrefix(path, "/") {
			sep = "/"
		}
		return base + sep + path
	}
	current := strings.TrimRight(u.Path, "/")
	extra := "/" + strings.TrimLeft(path, "/")
	var newPath string
	if current == "" {
		newPath = extra
	} else {
		newPath = current + extra
	}
	u.Path = newPath
	u.RawQuery = ""
	u.Fragment = ""
	return u.String()
}

// anthropicAPIRoot mirrors _anthropic_api_root: if base is an
// Anthropic host AND ends with /v1, strip the /v1. The caller then
// re-appends /v1/messages. The net effect is identical to "always
// re-append /v1" for an Anthropic URL.
func anthropicAPIRoot(base string) string {
	stripped := strings.TrimRight(base, "/")
	if strings.HasSuffix(stripped, "/v1") && hostMatch(base, "anthropic.com") {
		return strings.TrimRight(stripped[:len(stripped)-3], "/")
	}
	return base
}

// ollamaAPIRoot mirrors _ollama_api_root. When the path is empty,
// append /api. When the path already ends with /api, /api/chat, or
// /api/tags, leave it as-is (the caller appends the segment).
func ollamaAPIRoot(rawURL string) string {
	base := strings.TrimRight(rawURL, "/")
	u, err := url.Parse(base)
	if err != nil {
		return base
	}
	path := strings.TrimRight(u.Path, "/")
	switch {
	case strings.HasSuffix(path, "/chat"):
		return base[:len(base)-len("/chat")]
	case strings.HasSuffix(path, "/tags"):
		return base[:len(base)-len("/tags")]
	case strings.HasSuffix(path, "/generate"):
		return base[:len(base)-len("/generate")]
	case path == "":
		return base + "/api"
	}
	return base
}
