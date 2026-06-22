// Command aiint is a small demo CLI for the ai_interaction port. It reads
// JSON commands from stdin (one per line) and prints the resulting
// aiint.Result. It is intentionally minimal — the real work lives in
// pkg/aiint. With no dependencies wired (Manager with nil fields) the
// CLI exercises only the pure-parsing code paths: ui_control, manage_memory
// with an in-memory manager, and pipeline parsing/formatting.
package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/odysseus/ai_interaction/pkg/aiint"
)

type cmd struct {
	Tool    string `json:"tool"`
	Content string `json:"content"`
}

type out struct {
	OK          bool           `json:"ok"`
	Action      string         `json:"action,omitempty"`
	Results     string         `json:"results,omitempty"`
	Error       string         `json:"error,omitempty"`
	Details     map[string]any `json:"details,omitempty"`
	Description string         `json:"description,omitempty"`
}

func main() {
	// Seed an in-memory memory manager so the manage_memory tool has
	// something to talk to without touching the network or filesystem.
	mgr := &aiint.Manager{
		Memory: newDemoMemMgr(),
	}

	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 64*1024), 1024*1024)
	enc := json.NewEncoder(os.Stdout)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var c cmd
		if err := json.Unmarshal([]byte(line), &c); err != nil {
			fmt.Fprintf(os.Stderr, "bad input: %v\n", err)
			os.Exit(2)
		}
		desc, res, err := aiint.Dispatch(c.Tool, c.Content, mgr)
		if err != nil {
			fmt.Fprintf(os.Stderr, "dispatch error: %v\n", err)
			os.Exit(1)
		}
		o := out{OK: res.OK, Description: desc}
		if res.Action != "" {
			o.Action = res.Action
		}
		if res.Error != "" {
			o.Error = res.Error
		} else {
			o.Results = res.Results
		}
		if len(res.Details) > 0 {
			o.Details = res.Details
		}
		_ = enc.Encode(o)
	}
	if err := scanner.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "read error: %v\n", err)
		os.Exit(2)
	}
}

// demoMemMgr is a minimal in-memory MemoryManager used by the demo CLI.
type demoMemMgr struct {
	entries []aiint.MemoryEntry
}

func newDemoMemMgr() *demoMemMgr {
	return &demoMemMgr{entries: []aiint.MemoryEntry{
		{ID: "seed0001", Text: "Example memory entry", Category: "fact", Owner: "demo"},
	}}
}

func (d *demoMemMgr) Load(_ string) []aiint.MemoryEntry {
	return d.entries
}
func (d *demoMemMgr) LoadAll() []aiint.MemoryEntry {
	out := make([]aiint.MemoryEntry, len(d.entries))
	copy(out, d.entries)
	return out
}
func (d *demoMemMgr) AddEntry(text, _, category, owner string) (aiint.MemoryEntry, error) {
	id := fmt.Sprintf("mem%04d", len(d.entries)+1)
	e := aiint.MemoryEntry{ID: id, Text: text, Category: category, Owner: owner}
	d.entries = append(d.entries, e)
	return e, nil
}
func (d *demoMemMgr) Save(entries []aiint.MemoryEntry) error {
	d.entries = make([]aiint.MemoryEntry, len(entries))
	copy(d.entries, entries)
	return nil
}
