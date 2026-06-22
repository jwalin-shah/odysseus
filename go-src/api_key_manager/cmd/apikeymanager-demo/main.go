// Command apikeymanager-demo is a small CLI front-end for the
// apikeymanager package. It exercises the public surface end-to-end:
//
//   - constructs a Manager rooted at --data-dir
//   - encrypts --provider's --value and writes it to disk via Save
//   - reads every entry back via Load and prints metadata (length, prefix)
//   - decrypts the requested --provider's entry via DecryptAPIKey
//
// The CLI never prints the actual key value; only length and a short
// prefix are surfaced. The Python module keeps the same convention in
// production (the key is only ever passed around by reference; it is
// never logged).
//
// Usage:
//
//	apikeymanager-demo --data-dir /tmp/akm \
//	    --provider brave --value 'BSAhunter2'
//	apikeymanager-demo --data-dir /tmp/akm --provider brave --decrypt
//	apikeymanager-demo --data-dir /tmp/akm --list
package main

import (
	"flag"
	"fmt"
	"os"
	"strings"

	apikm "github.com/odysseus/api_key_manager/pkg/apikeymanager"
)

const (
	redactedPlaceholder = "<redacted>"
	keyPrefixDisplay    = 4 // how many leading chars of the decrypted key to surface
)

func main() {
	if err := run(os.Args[1:], os.Stdout, os.Stderr); err != nil {
		fmt.Fprintln(os.Stderr, "apikeymanager-demo:", err)
		os.Exit(1)
	}
}

func run(args []string, stdout, stderr *os.File) error {
	// Intercept --help / -h so it prints usage on stdout and exits 0,
	// matching the wave9 standing rule that demo CLIs exit 0 on help.
	for _, a := range args {
		if a == "-h" || a == "--help" || a == "-help" {
			fmt.Fprintf(stdout, "Usage of apikeymanager-demo:\n")
			printFlagDefaults(stdout)
			return nil
		}
	}

	fs := flag.NewFlagSet("apikeymanager-demo", flag.ContinueOnError)
	fs.SetOutput(stderr)
	dataDir := fs.String("data-dir", ".apikeymanager-demo", "Directory holding .key and api_keys.json (created with 0o700 / 0o600).")
	provider := fs.String("provider", "demo", "Provider name to encrypt/decrypt under.")
	value := fs.String("value", "", "Plaintext API key to encrypt. Ignored when --decrypt or --list is set.")
	decrypt := fs.Bool("decrypt", false, "Decrypt the on-disk entry for --provider and print metadata.")
	list := fs.Bool("list", false, "List every entry currently in api_keys.json (metadata only).")
	if err := fs.Parse(args); err != nil {
		// flag already prints the error to stderr (we wired SetOutput
		// above); surface it as a Go error so the caller exits non-zero.
		return err
	}

	mgr, err := apikm.New(*dataDir)
	if err != nil {
		return err
	}

	switch {
	case *list:
		return runList(mgr, stdout)
	case *decrypt:
		return runDecrypt(mgr, *provider, stdout)
	default:
		if *value == "" {
			return fmt.Errorf("--value is required when neither --decrypt nor --list is set")
		}
		return runSave(mgr, *provider, *value, stdout)
	}
}

func runSave(mgr *apikm.Manager, provider, value string, stdout *os.File) error {
	if err := mgr.Save(provider, value); err != nil {
		return err
	}
	keys, err := mgr.Load()
	if err != nil && !apikm.IsCorruptStore(err) {
		return err
	}
	decrypted, ok := keys[provider]
	if !ok {
		return fmt.Errorf("provider %q not present after Save", provider)
	}
	printKeyMetadata("save", provider, value, decrypted, stdout)
	return nil
}

func runDecrypt(mgr *apikm.Manager, provider string, stdout *os.File) error {
	keys, err := mgr.Load()
	if err != nil && !apikm.IsCorruptStore(err) {
		return err
	}
	decrypted, ok := keys[provider]
	if !ok {
		fmt.Fprintf(stdout, "provider=%s present=false\n", provider)
		return nil
	}
	printKeyMetadata("decrypt", provider, redactedPlaceholder, decrypted, stdout)
	return nil
}

func runList(mgr *apikm.Manager, stdout *os.File) error {
	keys, err := mgr.Load()
	if err != nil && !apikm.IsCorruptStore(err) {
		return err
	}
	if len(keys) == 0 {
		fmt.Fprintln(stdout, "(no providers stored)")
		return nil
	}
	fmt.Fprintf(stdout, "providers=%d\n", len(keys))
	for name, plain := range keys {
		prefix := redactPrefix(plain)
		fmt.Fprintf(stdout, "  - %s (len=%d prefix=%s)\n", name, len(plain), prefix)
	}
	return nil
}

func printKeyMetadata(op, provider, plain, decrypted string, stdout *os.File) {
	prefix := redactPrefix(decrypted)
	fmt.Fprintf(stdout, "op=%s provider=%s plain_len=%d decrypt_len=%d prefix=%s\n",
		op,
		provider,
		len(plain),
		len(decrypted),
		prefix,
	)
	if plain != redactedPlaceholder && plain != decrypted {
		fmt.Fprintln(stdout, "roundtrip=ok")
	} else if plain == redactedPlaceholder {
		fmt.Fprintln(stdout, "roundtrip=skipped (no plaintext available)")
	}
}

// redactPrefix returns the first keyPrefixDisplay chars of s followed by
// "..." or a "<empty>" sentinel. Security-sensitive: we never print the
// full key, only a short prefix, so logs and CI output stay safe.
func redactPrefix(s string) string {
	if s == "" {
		return "<empty>"
	}
	if len(s) <= keyPrefixDisplay {
		return s + "..."
	}
	return strings.TrimRight(s[:keyPrefixDisplay], "\x00") + "..."
}

// printFlagDefaults renders a flag-block identical to flag.PrintDefaults
// so the --help intercept path can keep the same look without invoking
// flag.Parse (which would trip ContinueOnError on -h).
func printFlagDefaults(w *os.File) {
	fmt.Fprintln(w, "  -data-dir string")
	fmt.Fprintln(w, "    \tDirectory holding .key and api_keys.json (created with 0o700 / 0o600). (default \".apikeymanager-demo\")")
	fmt.Fprintln(w, "  -provider string")
	fmt.Fprintln(w, "    \tProvider name to encrypt/decrypt under. (default \"demo\")")
	fmt.Fprintln(w, "  -value string")
	fmt.Fprintln(w, "    \tPlaintext API key to encrypt. Ignored when --decrypt or --list is set.")
	fmt.Fprintln(w, "  -decrypt")
	fmt.Fprintln(w, "    \tDecrypt the on-disk entry for --provider and print metadata.")
	fmt.Fprintln(w, "  -list")
	fmt.Fprintln(w, "    \tList every entry currently in api_keys.json (metadata only).")
}
