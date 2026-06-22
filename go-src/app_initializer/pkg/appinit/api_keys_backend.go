package appinit

import (
	"encoding/json"
	"io"
	"os"
	"path/filepath"
)

// decodeKeyFile parses the api_keys.json file into a string→string map. A
// missing or empty file returns an empty map rather than an error so the
// first-run path stays smooth. Corrupt JSON also returns an empty map — same
// tolerance as the Python _load_raw fallback.
func decodeKeyFile(r io.Reader) map[string]string {
	out := map[string]string{}
	dec := json.NewDecoder(r)
	if err := dec.Decode(&out); err != nil {
		return map[string]string{}
	}
	// At this point `out` is already map[string]string because we declared it
	// that way; json.Decode into a typed map only succeeds for matching shapes.
	// We still re-validate each entry to mirror the Python isinstance(key, str)
	// filter — defensive against any future caller decoding into a wider type.
	cleaned := make(map[string]string, len(out))
	for k, v := range out {
		if v == "" {
			continue
		}
		cleaned[k] = v
	}
	return cleaned
}

// writeKeyFile atomically writes keys to path. We use a tmp-file rename so a
// crash mid-write can't leave a half-written api_keys.json behind.
func writeKeyFile(path string, keys map[string]string) error {
	dir := filepath.Dir(path)
	base := filepath.Base(path)
	tmp, err := os.CreateTemp(dir, base+".tmp-*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)

	enc := json.NewEncoder(tmp)
	enc.SetIndent("", "  ")
	if err := enc.Encode(keys); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmpName, path)
}
