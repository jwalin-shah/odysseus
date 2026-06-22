package aiinteraction

import (
	"context"
	"fmt"
	"strings"
)

// ResolveModel is the Go port of _resolve_model. The Python source
// loops over the SQL ModelEndpoint rows, resolves each one's runtime
// base/api_key, calls _detect_provider, and either matches against
// ANTHROPIC_MODELS or probes the /v1/models endpoint.
//
// The Go port drives the same flow against the injected
// ModelEndpointStore + EndpointRuntimeResolver. The HTTP probe uses
// the injected HTTPDoer.
//
// Errors mirror the Python ValueError shape:
//
//   - "No enabled endpoints found" (+ optional " matching '<name>'")
//   - "Model '<spec>' not found on any configured endpoint"
func ResolveModel(spec string, opts ResolveOptions) (ResolvedModel, error) {
	parsed, err := ParseModelSpec(spec)
	if err != nil {
		return ResolvedModel{}, err
	}
	if opts.Store == nil {
		return ResolvedModel{}, fmt.Errorf("error: model resolution requires an endpoint store")
	}
	if opts.Runtime == nil {
		return ResolvedModel{}, fmt.Errorf("error: model resolution requires an endpoint runtime resolver")
	}
	if opts.HTTP == nil {
		opts.HTTP = noopHTTPDoer{}
	}

	endpoints := opts.Store.EnabledEndpoints(parsed.EndpointName, opts.Owner)
	if len(endpoints) == 0 {
		msg := "No enabled endpoints found"
		if parsed.EndpointName != "" {
			msg += " matching '" + parsed.EndpointName + "'"
		}
		return ResolvedModel{}, fmt.Errorf("error: %s", msg)
	}

	for _, ep := range endpoints {
		base, apiKey, err := opts.Runtime(ep, opts.Owner)
		if err != nil {
			continue
		}
		provider := detectProvider(base)
		headers := BuildHeaders(apiKey, base)

		if provider == "anthropic" {
			for _, am := range AnthropicModels {
				if strings.Contains(strings.ToLower(parsed.ModelName), strings.ToLower(am)) ||
					strings.Contains(strings.ToLower(am), strings.ToLower(parsed.ModelName)) {
					return ResolvedModel{
						EndpointURL: BuildChatURL(base),
						ModelID:     am,
						Headers:     headers,
					}, nil
				}
			}
			continue
		}

		// OpenAI-compatible and native Ollama: probe the model list.
		var modelIDs []string
		modelsURL := BuildModelsURL(base)
		if modelsURL != "" {
			resp, err := opts.HTTP.Do(&HTTPRequest{
				Method:  "GET",
				URL:     modelsURL,
				Headers: headers,
				Timeout: 5_000_000_000, // 5s; the package uses ns.
			})
			if err == nil && resp.Status >= 200 && resp.Status < 300 {
				modelIDs = parseModelListResponse(resp.Body)
			}
		}
		if len(modelIDs) == 0 && len(ep.CachedModels) > 0 {
			modelIDs = ep.CachedModels
		}
		// Exact match first.
		for _, mid := range modelIDs {
			if strings.EqualFold(mid, parsed.ModelName) {
				return ResolvedModel{
					EndpointURL: BuildChatURL(base),
					ModelID:     mid,
					Headers:     headers,
				}, nil
			}
		}
		// Partial match.
		for _, mid := range modelIDs {
			low := strings.ToLower(mid)
			needle := strings.ToLower(parsed.ModelName)
			if strings.Contains(needle, low) || strings.Contains(low, needle) {
				return ResolvedModel{
					EndpointURL: BuildChatURL(base),
					ModelID:     mid,
					Headers:     headers,
				}, nil
			}
		}
	}
	return ResolvedModel{}, fmt.Errorf("error: Model '%s' not found on any configured endpoint", spec)
}

// ResolveOptions configures ResolveModel. Store and Runtime are
// required; HTTP defaults to a noop transport (which means OpenAI-
// compatible providers won't resolve without one).
type ResolveOptions struct {
	Store   ModelEndpointStore
	Runtime EndpointRuntimeResolver
	HTTP    HTTPDoer
	Owner   string
}

// noopHTTPDoer is the default HTTPDoer used when opts.HTTP is nil.
// Calls to Do always return an error, so ResolveModel falls through
// to the cached-models branch.
type noopHTTPDoer struct{}

func (noopHTTPDoer) Do(*HTTPRequest) (*HTTPResponse, error) {
	return nil, fmt.Errorf("error: no HTTP transport configured")
}

// parseModelListResponse accepts the raw response body from
// /v1/models and returns the model id list. The Python source uses
// data["data"] then falls back to data["models"] with two different
// id-ish field names; the Go port does the same.
func parseModelListResponse(body []byte) []string {
	if len(body) == 0 {
		return nil
	}
	parsed, err := parseJSONObject(body)
	if err != nil {
		return nil
	}
	if data, ok := parsed["data"].([]any); ok {
		out := make([]string, 0, len(data))
		for _, item := range data {
			m, ok := item.(map[string]any)
			if !ok {
				continue
			}
			if id, ok := m["id"].(string); ok {
				out = append(out, id)
			}
		}
		if len(out) > 0 {
			return out
		}
	}
	if models, ok := parsed["models"].([]any); ok {
		out := make([]string, 0, len(models))
		for _, item := range models {
			m, ok := item.(map[string]any)
			if !ok {
				continue
			}
			if name, ok := m["name"].(string); ok {
				out = append(out, name)
				continue
			}
			if id, ok := m["model"].(string); ok {
				out = append(out, id)
			}
		}
		return out
	}
	return nil
}

// LLMCall is the synchronous shape of src.llm_core.llm_call. The
// pipeline driver below uses it to make sure tests can plug a stub
// in without touching the network. ctx is the parent context; the
// stub should respect cancellation.
type LLMCall func(ctx context.Context, endpointURL, model string, headers map[string]string, messages []ChatMessage, timeoutSeconds int) (string, error)
