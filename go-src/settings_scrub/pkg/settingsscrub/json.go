package settingsscrub

import "encoding/json"

// jsonUnmarshal is a thin wrapper over encoding/json's Unmarshal. It exists
// so the scrub.go file can be reasoned about without dragging the encoding
// import into every reader's attention — the wrapper is in its own file
// (json.go) so the JSON helper stays colocated with the marshalling code.
//
// Behavior matches json.Unmarshal exactly:
//
//   - invalid JSON returns a non-nil error and leaves dst untouched;
//   - a top-level JSON null decodes to a nil map and returns no error, so
//     the caller must still check dst for nil before walking it.
func jsonUnmarshal(data []byte, dst *map[string]any) error {
	return json.Unmarshal(data, dst)
}
