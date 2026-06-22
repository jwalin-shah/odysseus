package aiinteraction

import "encoding/json"

// parseJSONObject decodes body into a generic map[string]any. The
// package uses this for hand-rolled JSON parsing where the upstream
// shape varies by provider and we want a permissive decoder that
// doesn't reject extra fields. encoding/json's strict-mode behaviour
// is fine — the package only reads specific keys.
func parseJSONObject(body []byte) (map[string]any, error) {
	var out map[string]any
	if err := json.Unmarshal(body, &out); err != nil {
		return nil, err
	}
	return out, nil
}

// jsonMarshal is a thin shim around encoding/json.Marshal so the
// dispatch layer can use it without re-importing encoding/json.
func jsonMarshal(v any) ([]byte, error) {
	return json.Marshal(v)
}
