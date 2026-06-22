// Command api_key_manager is a small CLI for inspecting the on-disk state of
// the encrypted api_keys.json store and exercising encrypt/decrypt against a
// value supplied on stdin. It exists so operators can sanity-check the store
// and so the port has a runnable binary matching the Python module.
package main

import (
	"bufio"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"odysseus/api_key_manager"
)

func main() {
	if err := run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr); err != nil {
		fmt.Fprintln(os.Stderr, "api_key_manager:", err)
		os.Exit(1)
	}
}

func run(args []string, stdin io.Reader, stdout, stderr io.Writer) error {
	fs := flag.NewFlagSet("api_key_manager", flag.ContinueOnError)
	fs.SetOutput(stderr)
	dataDir := fs.String("data-dir", "./data", "directory holding .key and api_keys.json")
	encrypt := fs.Bool("encrypt", false, "encrypt stdin and print the token")
	decrypt := fs.Bool("decrypt", false, "decrypt stdin (a single token) and print the plaintext")
	list := fs.Bool("list", false, "list decrypted provider -> key pairs from api_keys.json")
	_ = fs.Parse(args)
	_ = list // currently routed via subcommands; kept for symmetry/future use

	mgr := api_key_manager.NewManager(*dataDir)
	fmt.Fprintf(stdout, "data_dir: %s\n", mgr.DataDir())
	fmt.Fprintf(stdout, "key_file: %s\n", mgr.KeyFile())
	fmt.Fprintf(stdout, "keys_file: %s\n", mgr.KeysFile())

	// Ensure the .key exists (so the operator can see the path even on a
	// fresh install) — read-only consumers don't pay any cost.
	if _, err := mgr.GetOrCreateKey(); err != nil {
		return err
	}

	// Reject obviously conflicting mode flags before reading stdin so the
	// failure mode doesn't depend on the operator piping input.
	if *encrypt && *decrypt {
		return fmt.Errorf("pass only one of --encrypt or --decrypt")
	}

	scanner := bufio.NewScanner(stdin)
	scanner.Buffer(make([]byte, 1024*1024), 16*1024*1024)
	if !scanner.Scan() {
		if err := scanner.Err(); err != nil && err != io.EOF {
			return fmt.Errorf("read stdin: %w", err)
		}
		// Empty stdin is fine; just print the paths and exit 0.
		return nil
	}
	line := strings.TrimRight(scanner.Text(), "\r\n")

	switch {
	case *encrypt:
		tok, err := mgr.EncryptAPIKey(line)
		if err != nil {
			return err
		}
		fmt.Fprintf(stdout, "encrypted: %s\n", tok)
	case *decrypt:
		plain, err := mgr.DecryptAPIKey(line)
		if err != nil {
			return err
		}
		fmt.Fprintf(stdout, "decrypted: %s\n", plain)
	default:
		// No mode flag: treat the input as a single provider -> key pair
		// (separated by '=') and save it. Falls back to "list" for an
		// empty/blank line so the binary is useful as a probe.
		if line == "" {
			return printDecrypted(stdout, mgr)
		}
		provider, value, ok := strings.Cut(line, "=")
		if !ok || provider == "" {
			return fmt.Errorf("expected 'provider=api_key' on stdin (or pass --encrypt/--decrypt)")
		}
		if err := mgr.Save(provider, value); err != nil {
			return err
		}
		fmt.Fprintf(stdout, "saved: %s\n", provider)
	}
	return nil
}

func printDecrypted(w io.Writer, mgr *api_key_manager.Manager) error {
	keys, err := mgr.Load()
	if err != nil {
		return err
	}
	if len(keys) == 0 {
		fmt.Fprintln(w, "(no decrypted keys)")
		return nil
	}
	for k, v := range keys {
		fmt.Fprintf(w, "%s=%s\n", k, v)
	}
	return nil
}
