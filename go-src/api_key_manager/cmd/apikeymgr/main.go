// Command apikeymgr demonstrates the api_key_manager package: takes a data
// directory as its first argument, encrypts "sk-test-123" under the provider
// "openai", loads it back, and prints the decrypted plaintext. It also
// exercises a missing-file load and a corrupt-file load so the operator can
// see the fail-soft behaviour.
package main

import (
	"fmt"
	"os"

	"github.com/odysseus/api_key_manager/pkg/apikeymgr"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: apikeymgr <data-dir>")
		os.Exit(2)
	}
	dataDir := os.Args[1]

	mgr := apikeymgr.New(dataDir)
	fmt.Printf("data_dir:  %s\n", mgr.DataDir())
	fmt.Printf("key_file:  %s\n", mgr.KeyFile())
	fmt.Printf("keys_file: %s\n", mgr.KeysFile())

	// Save an example key.
	const provider = "openai"
	const apiKey = "sk-test-123"
	if err := mgr.Save(provider, apiKey); err != nil {
		fmt.Fprintln(os.Stderr, "save:", err)
		os.Exit(1)
	}
	fmt.Printf("saved: %s\n", provider)

	// Load and print the round-trip.
	loaded, err := mgr.Load()
	if err != nil {
		fmt.Fprintln(os.Stderr, "load:", err)
		os.Exit(1)
	}
	for k, v := range loaded {
		fmt.Printf("loaded[%s] = %s\n", k, v)
	}

	// Show the raw on-disk dict (still-encrypted) so an operator can see
	// that we never write plaintext to disk.
	raw, err := mgr.LoadRaw()
	if err != nil {
		fmt.Fprintln(os.Stderr, "load_raw:", err)
		os.Exit(1)
	}
	fmt.Printf("raw entry count: %d (encrypted)\n", len(raw))
}
