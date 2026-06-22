// State types and JSON I/O for the cookbook state file. Mirrors the shape
// produced by builtin_actions.py's action_cookbook_serve: a top-level
// `tasks` array plus any extra sibling keys the UI may have written.

package cookbookserve

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Task is a single entry in the cookbook state file. JSON tags mirror the
// camelCase shape produced by the Python writer (see builtin_actions.py's
// action_cookbook_serve), with the synthetic `_scheduledStopAtMs` /
// `_lastStatusFlipAt` underscored fields preserved verbatim.
type Task struct {
	ID                 string         `json:"id,omitempty"`
	SessionID          string         `json:"sessionId,omitempty"`
	RemoteHost         string         `json:"remoteHost,omitempty"`
	SSHPort            string         `json:"sshPort,omitempty"`
	Type               string         `json:"type,omitempty"`
	Status             string         `json:"status,omitempty"`
	ScheduledStopAtMs  *int64         `json:"_scheduledStopAtMs"`
	LastStatusFlipAtMs *int64         `json:"_lastStatusFlipAt,omitempty"`
	Payload            map[string]any `json:"payload,omitempty"`

	// Extra preserves any keys the Python writer added that aren't modelled
	// here, so a round-trip through ReadStateFile + WriteStateFileAtomic
	// does not silently drop them.
	Extra map[string]json.RawMessage `json:"-"`
}

// SessionID returns the canonical session id used by the lifecycle. It
// prefers Task.SessionID and falls back to Task.ID, matching Python's
// `t.get("sessionId") or t.get("id")`.
func (t Task) SessionIDOrID() string {
	if t.SessionID != "" {
		return t.SessionID
	}
	return t.ID
}

// IsTerminalStatus reports whether the task's status is one of the lowercase
// strings the lifecycle treats as "already done — don't try to stop".
func (t Task) IsTerminalStatus() bool {
	switch strings.ToLower(t.Status) {
	case "stopped", "ended", "killed", "crashed":
		return true
	}
	return false
}

// State is the on-disk JSON: `{"tasks": [...], ...}`. Sibling keys that
// aren't `tasks` are preserved in Extra so the lifecycle loop never clobbers
// config bits written by the UI.
type State struct {
	Tasks []*Task                    `json:"tasks"`
	Extra map[string]json.RawMessage `json:"-"`
}

// MarshalJSON merges Extra back into the top-level object alongside the
// canonical Tasks field. This keeps round-trips lossless for any future keys
// the Python writer might add.
func (s *State) MarshalJSON() ([]byte, error) {
	out := map[string]json.RawMessage{}
	for k, v := range s.Extra {
		if k == "tasks" {
			continue
		}
		out[k] = v
	}
	tb, err := json.Marshal(s.Tasks)
	if err != nil {
		return nil, err
	}
	out["tasks"] = tb
	return json.Marshal(out)
}

// UnmarshalJSON splits the top-level object into the canonical Tasks slice
// plus an Extra map of preserved sibling keys.
func (s *State) UnmarshalJSON(data []byte) error {
	raw := map[string]json.RawMessage{}
	if err := json.Unmarshal(data, &raw); err != nil {
		return err
	}
	s.Extra = map[string]json.RawMessage{}
	for k, v := range raw {
		if k == "tasks" {
			continue
		}
		s.Extra[k] = v
	}
	if tb, ok := raw["tasks"]; ok && len(tb) > 0 && string(tb) != "null" {
		var tasks []*Task
		if err := json.Unmarshal(tb, &tasks); err != nil {
			return fmt.Errorf("decode tasks: %w", err)
		}
		s.Tasks = tasks
	} else {
		s.Tasks = nil
	}
	return nil
}

// ReadStateFile reads and decodes the cookbook state JSON. A missing file
// returns (nil, os.ErrNotExist) so callers can treat it as "nothing to do"
// without reaching into the fs error directly.
func ReadStateFile(path string) (*State, error) {
	if path == "" {
		return nil, ErrEmptyStatePath
	}
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if len(b) == 0 {
		return &State{Tasks: nil, Extra: map[string]json.RawMessage{}}, nil
	}
	var s State
	if err := json.Unmarshal(b, &s); err != nil {
		return nil, fmt.Errorf("decode state %s: %w", path, err)
	}
	if s.Extra == nil {
		s.Extra = map[string]json.RawMessage{}
	}
	return &s, nil
}

// WriteStateFileAtomic writes the state JSON to path+".tmp", fsyncs it, then
// renames it over the target. Mirrors core.atomic_io.atomic_write_json in
// Python so a partially-written file never replaces a good one on crash.
func WriteStateFileAtomic(path string, s *State) error {
	if path == "" {
		return ErrEmptyStatePath
	}
	if s == nil {
		s = &State{Tasks: nil, Extra: map[string]json.RawMessage{}}
	}
	dir := filepath.Dir(path)
	if dir == "" {
		dir = "."
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("mkdir %s: %w", dir, err)
	}
	body, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return fmt.Errorf("encode state: %w", err)
	}
	tmp := path + ".tmp"
	f, err := os.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o644)
	if err != nil {
		return fmt.Errorf("open %s: %w", tmp, err)
	}
	if _, err := f.Write(body); err != nil {
		f.Close()
		os.Remove(tmp)
		return fmt.Errorf("write %s: %w", tmp, err)
	}
	if err := f.Sync(); err != nil {
		f.Close()
		os.Remove(tmp)
		return fmt.Errorf("fsync %s: %w", tmp, err)
	}
	if err := f.Close(); err != nil {
		os.Remove(tmp)
		return fmt.Errorf("close %s: %w", tmp, err)
	}
	if err := os.Rename(tmp, path); err != nil {
		os.Remove(tmp)
		return fmt.Errorf("rename %s -> %s: %w", tmp, path, err)
	}
	return nil
}
